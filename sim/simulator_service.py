"""HTTP service exposing the real SecondLookEnv to the API container."""
from __future__ import annotations

import base64
import os
import sys
import threading
import time
from io import BytesIO
from pathlib import Path

_SIM_DIR = str(Path(__file__).resolve().parent)
if _SIM_DIR not in sys.path:
    sys.path.insert(0, _SIM_DIR)

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from PIL import Image

from sim.expert import run_expert
from sim.world import OBJECTS, Z_SAFE, SecondLookEnv

app = FastAPI(title="Second Look Simulator Service")
_sim_lock = threading.RLock()
_env: SecondLookEnv | None = None
_target = "cup_red"
_episode_started = time.monotonic()


class ResetRequest(BaseModel):
    target: str = "cup_red"
    start: str = "home"
    seed: int = 0
    hidden_place: str | None = None


class ActionRequest(BaseModel):
    action: str = "pick"
    target: str = "cup_red"
    command: str | None = None
    seed: int = 0


def _image_data_uri(frame) -> str | None:
    if frame is None:
        return None
    arr = np.asarray(frame)
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    image = Image.fromarray(arr)
    buff = BytesIO()
    image.save(buff, format="JPEG", quality=82, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buff.getvalue()).decode("ascii")


def _get_env() -> SecondLookEnv:
    global _env
    if _env is None:
        _env = SecondLookEnv(render=True, img=224)
    return _env


def _observation(env: SecondLookEnv) -> dict:
    obs = env.obs()
    target_visible_front = bool(env.front_visible(_target))
    target_visible_wrist = bool(env.wrist_sees(_target))
    return {
        "front": _image_data_uri(obs.get("front")),
        "wrist": _image_data_uri(obs.get("wrist")),
        "state": [float(x) for x in obs["state"]],
        "simulation_time": round(float(env.d.time), 3),
        "target_visible": target_visible_front or target_visible_wrist,
        "front_visible": target_visible_front,
        "wrist_visible": target_visible_wrist,
    }


def _reset(req: ResetRequest) -> dict:
    global _target, _episode_started
    if req.target not in OBJECTS:
        raise ValueError(f"target must be one of {OBJECTS}")
    if req.hidden_place not in (None, "L", "R"):
        raise ValueError("hidden_place must be 'L', 'R', or None")
    with _sim_lock:
        env = _get_env()
        _target = req.target
        _episode_started = time.monotonic()
        env.reset(
            seed=req.seed,
            target=req.target,
            start=req.start,
            hidden_place=req.hidden_place,
        )

        return {"ok": True, "target": req.target, "start": req.start,
                "observation": _observation(env)}


@app.get("/health")
async def health():
    return {"ok": True, "service": "simulator", "environment": "SecondLookEnv"}


@app.post("/simulator/reset")
@app.post("/reset")
async def reset(req: ResetRequest):
    try:
        return await run_in_threadpool(_reset, req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Simulator reset failed: {type(exc).__name__}: {exc}") from exc


def _execute(req: ActionRequest) -> dict:
    global _target
    action = req.action.lower().strip()
    target = req.target or _target
    if target not in OBJECTS:
        raise ValueError(f"target must be one of {OBJECTS}")
    with _sim_lock:
        env = _get_env()
        _target = target
        before = float(env.d.time)
        if action in ("look", "relook", "peek"):
            if target not in OBJECTS:
                raise ValueError("look requires an object target")
            place = req.command if req.command in ("L", "R") else None
            if place is None and "right" in (req.command or "").lower():
                place = "R"
            elif place is None and "left" in (req.command or "").lower():
                place = "L"
            if place is None:
                # If the robot is already hovering over a screen, inspect that area;
                # otherwise use the target's current hidden zone inferred from its position.
                p = env.obj_pos(target)
                place = "L" if p[0] < 0 else "R"
            center = env.hide_center(place)
            arrived = env.goto([float(center[0]), float(center[1]), Z_SAFE], g=1.0, max_steps=100)
            found = bool(env.wrist_sees(target))
            obs = _observation(env)
            return {"ok": bool(arrived), "action": "look", "target": target, "place": place,
                    "found": found, "duration_s": round(float(env.d.time) - before, 3),
                    "observation": obs}
        if action in ("disturb", "move_object"):
            # This is an explicitly simulated disturbance event. The current MuJoCo
            # scene has no physical pressure sensor, so do not label it as hardware data.
            old_pos = env.obj_pos(target).copy()
            old_zone = "L" if old_pos[0] < 0 else "R"
            new_zone = "R" if old_zone == "L" else "L"
            center = env.hide_center(new_zone)
            rng = np.random.default_rng(req.seed)
            new_xy = [float(center[0] + rng.uniform(-0.025, 0.025)), float(rng.uniform(0.11, 0.17))]
            env.move_object(target, new_xy)
            event = {"type": "event", "kind": "zone_disturbed", "zone": old_zone,
                     "sensor_triggered": True, "simulated": True,
                     "t": round(float(env.d.time), 3)}
            return {"ok": True, "action": "disturb", "target": target,
                    "old_zone": old_zone, "new_zone": new_zone, "event": event,
                    "duration_s": round(float(env.d.time) - before, 3),
                    "observation": _observation(env)}
        if action in ("pick", "place", "pick_place"):
            obs = _observation(env)
            if not (env.front_visible(target) or env.wrist_sees(target)):
                return {"ok": False, "action": "pick", "target": target,
                        "message": "Target is not visible to the front or wrist camera; look first.",
                        "duration_s": round(float(env.d.time) - before, 3),
                        "observation": obs}
            success, _ = run_expert(env, target, np.random.default_rng(req.seed), record=False)
            obs = _observation(env)
            return {"ok": bool(success), "action": "pick", "target": target,
                    "in_tray": bool(env.in_tray(target)),
                    "duration_s": round(float(env.d.time) - before, 3),
                    "observation": obs}
        raise ValueError("action must be 'look' or 'pick'")


@app.post("/command")
@app.post("/action")
async def command(req: ActionRequest):
    try:
        return await run_in_threadpool(_execute, req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Simulator action failed: {type(exc).__name__}: {exc}") from exc
