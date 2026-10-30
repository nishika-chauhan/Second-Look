"""
Second Look: mock-mode belief/planner API (role B), v2.

Serves the belief + planner code over FastAPI + WebSocket and routes actions to the live MuJoCo simulator.

Run (from the ai/ folder):
    pip install fastapi "uvicorn[standard]" openai
    uvicorn server:app --reload --port 8000

Frontend origin: only http://localhost:5173 (Vite dev) and a few siblings may
connect from a browser. Override with an environment variable, comma separated:
    ALLOWED_ORIGINS="http://localhost:5173,https://demo.example.com"
    ALLOWED_ORIGINS="*"            # anything (not for the final demo)
Note that browsers do not apply CORS to WebSockets, so the /ws handler checks
the Origin header itself. Non-browser clients (no Origin header) are accepted.

Client -> server commands (JSON over ws://localhost:8000/ws):
    {"cmd":"start", "scenario":"S2", "hidden_seconds":40, "sim_speed":5,
     "true_place":"L", "engine":"rule"|"auto"|"llm", "move_prob":0,
     "sensor_detect_rate":0, "false_alarm_rate":0, "grasp_fail_prob":0.1, "seed":1}
    {"cmd":"move_object"}      # "move it while hidden" button
    {"cmd":"reset"}

Server -> client message types (plan Part 2.2):
    observation, belief, decision, action_result, episode_end, plus
    reset_ack and error.
"""

from __future__ import annotations

import os
import time
import httpx
from fastapi import HTTPException
import asyncio
import json
import os
import random
import sys

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import event_watcher as EW  # noqa: E402
import planner as PL  # noqa: E402
import regions_belief as RB  # noqa: E402

DEFAULT_ORIGINS = [
    "http://localhost:3000", "http://127.0.0.1:3000",
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:4173", "http://127.0.0.1:4173",
]


def allowed_origins() -> list:
    raw = os.environ.get("ALLOWED_ORIGINS", "").strip()
    return [o.strip() for o in raw.split(",") if o.strip()] if raw else list(DEFAULT_ORIGINS)


ORIGINS = allowed_origins()
_SERVER_START_TIME = time.time()
_NEBIUS_CACHE = {"last_check": 0, "verified": False, "detail": ""}
_LAST_SIM_OK = False
VERCEL_ORIGIN_RE = r"https://[a-zA-Z0-9-]+(?:-[a-zA-Z0-9-]+)*\.vercel\.app"


def origin_ok(origin: str | None) -> bool:
    if origin is None or "*" in ORIGINS:
        return True
    if origin in ORIGINS:
        return True
    from urllib.parse import urlparse
    parsed = urlparse(origin)
    return parsed.scheme == "https" and parsed.hostname is not None and parsed.hostname.endswith(".vercel.app")


# --------------------------------------------------------------------------
# Message builders (same fields as plan Part 2.2; extras are additive)
# --------------------------------------------------------------------------

def msg_observation(t, front_ref, wrist_ref, state, sensor_event=None):
    return {"type": "observation", "t": round(t, 2), "front_image": front_ref,
            "wrist_image": wrist_ref, "state": state, "sensor_event": sensor_event}


def msg_belief(obj, place, confidence, last_seen_t, status, t=None):
    """`t` is the simulation time of this belief (x-axis for a confidence chart);
    `last_seen_t` is when the object was last actually seen."""
    return {"type": "belief", "t": round(last_seen_t if t is None else t, 2),
            "object": obj, "place": place,
            "confidence": round(confidence, 3), "last_seen_t": round(last_seen_t, 2),
            "status": status}


def msg_decision(dec: dict) -> dict:
    """Planner decision with a stable shape: every field is always present."""
    return {
        "type": "decision",
        "engine": dec["engine"],
        "action": dec["action"],
        "target": dec["target"],
        "command": dec["command"],
        "why": dec["why"],
        "latency_ms": dec["latency_ms"],
        "offline": bool(dec.get("offline", False)),
        "fallback_reason": dec.get("fallback_reason", ""),
        "model": dec.get("model", ""),
        "agree_with_rule": dec.get("agree_with_rule"),
    }


def msg_action_result(skill, ok, duration_s, gripper_state_at_end=None):
    return {"type": "action_result", "skill": skill, "ok": ok,
            "duration_s": round(duration_s, 2), "gripper_state_at_end": gripper_state_at_end}


def msg_episode_end(success, total_time_s, looks, llm_calls, ground_truth_place):
    return {"type": "episode_end", "success": success, "total_time_s": round(total_time_s, 2),
            "looks": looks, "llm_calls": llm_calls, "ground_truth_place": ground_truth_place}


def belief_status(conf: float, visible: bool) -> str:
    if visible:
        return "visible"
    return "stale" if conf < 0.5 else "unknown"


# One planner per mode, shared, so the Nemotron client and model list are
# set up once and the CSV/stat log keeps accumulating.
_PLANNERS: dict = {}


def get_planner(mode: str) -> PL.Planner:
    mode = {"nemotron": "llm"}.get(mode, mode)
    if mode not in _PLANNERS:
        _PLANNERS[mode] = PL.Planner(mode=mode)
        if mode != "rule":
            # first use: warm the connection in the background so the first decision is fast
            import threading
            threading.Thread(target=_PLANNERS[mode].warm_up, daemon=True).start()
    return _PLANNERS[mode]


# --------------------------------------------------------------------------
# Mock episode: S2 (hide, then fetch) and S3 (object may move while hidden)
# --------------------------------------------------------------------------

class MockEpisode:
    def __init__(self, send, scenario="S2", hidden_seconds=40.0, move_prob=0.0,
                 sensor_detect_rate=0.0, false_alarm_rate=0.0, sim_speed=5.0,
                 true_place=None, grasp_fail_prob=0.1, engine="rule", seed=None):
        self.send = send
        self.scenario = scenario
        self.hidden_seconds = float(hidden_seconds)
        self.move_prob = move_prob
        self.sensor_detect_rate = sensor_detect_rate
        self.false_alarm_rate = false_alarm_rate
        self.sim_speed = float(sim_speed)
        self.rng = random.Random(seed)
        self.true_place = true_place or self.rng.choice(RB.HIDING)
        self.grasp_fail_prob = grasp_fail_prob
        self.planner = get_planner(engine)
        self.obj = "bottle_blue"
        self.looks = 0
        self.move_requested = False       # set by the dashboard's "move it" button
        self.auto_moved = False           # the scripted move happens at most once

    async def _sleep_sim(self, sim_seconds: float):
        await asyncio.sleep(sim_seconds / self.sim_speed)

    def _other(self, place):
        return [p for p in RB.HIDING if p != place][0]

    async def run(self):
        t = 0.0
        belief = RB.Belief(self.obj, self.true_place, 1.0, 0.0)
        ctx = PL.PlanContext(obj=self.obj, now=0.0, last_seen_t=0.0)
        log_start = len(self.planner.log)
        state = {"x": 0, "y": 0, "z": 0.2, "gripper": 1}

        await self.send(msg_observation(t, "mock://front/0.jpg", None, state))
        await self.send(msg_belief(self.obj, belief.place, belief.conf, belief.t,
                                   belief_status(belief.conf, False), t=t))

        # Hidden period, in small steps so the dashboard sees confidence decay.
        step = max(self.hidden_seconds / 10.0, 1.0)
        while t < self.hidden_seconds:
            dt = min(step, self.hidden_seconds - t)
            await self._sleep_sim(dt)
            t += dt
            RB.tick(belief, t, hidden=True)

            alarm_zone, truly_moved = None, False
            # S3: the "person" moves the object at most once on their own; the
            # dashboard's button can move it again whenever it is pressed.
            auto_move = (not self.auto_moved and self.move_prob
                         and self.rng.random() < self.move_prob / 10.0)
            if self.move_requested or auto_move:
                self.auto_moved = self.auto_moved or bool(auto_move)
                self.move_requested = False
                old = self.true_place
                self.true_place, truly_moved = self._other(old), True
                if self.rng.random() < self.sensor_detect_rate:
                    alarm_zone = old                       # sensor under the place it left
            elif self.false_alarm_rate and self.rng.random() < self.false_alarm_rate / 10.0:
                alarm_zone = belief.place                  # false alarm

            sensor_event = None
            if alarm_zone:
                ev = {"type": "event", "event": "zone_disturbed", "zone": alarm_zone,
                      "sensor_triggered": True, "t": t, "is_false_alarm": not truly_moved}
                EW.process_event(ev, {self.obj: belief}, t)
                ctx.sensor_events.append((t, alarm_zone))
                sensor_event = {"place": alarm_zone, "fired": True}
            ctx.now = t

            await self.send(msg_observation(t, "mock://front/blocked.jpg", None, state, sensor_event))
            await self.send(msg_belief(self.obj, belief.place, belief.conf, belief.t,
                                       belief_status(belief.conf, False), t=t))

        # Fetch: let the planner choose where to look until the object is found.
        found = False
        for _ in range(len(RB.HIDING) + 1):
            dec = await asyncio.to_thread(self.planner.decide, belief, ctx, False)
            await self.send(msg_decision(dec))
            if dec["action"] != "look":
                break                                      # ask / finish: stop searching
            target = dec["target"]
            self.looks += 1
            cost = RB.LOOK_COST_S[target]
            await self._sleep_sim(cost)
            t += cost
            found = target == self.true_place
            await self.send(msg_action_result("look", found, cost))
            PL.note_look_result(belief, ctx, target, found, t)
            if found:
                await self.send(msg_belief(self.obj, belief.place, belief.conf, belief.t, "visible", t=t))
                break
            await self.send(msg_belief(self.obj, belief.place, belief.conf, belief.t, "unknown", t=t))

        success = False
        if found:
            dec = await asyncio.to_thread(self.planner.decide, belief, ctx, True)
            await self.send(msg_decision(dec))
            pick_cost = 6.0
            await self._sleep_sim(pick_cost)
            t += pick_cost
            grasp_ok = self.rng.random() >= self.grasp_fail_prob
            await self.send(msg_action_result("pick", grasp_ok, pick_cost, 0.4 if grasp_ok else 0.0))
            if not grasp_ok:
                PL.note_grasp_result(belief, ctx, False, t)
                await self.send(msg_belief(self.obj, belief.place, belief.conf, belief.t, "stale", t=t))
                retry = await asyncio.to_thread(self.planner.decide, belief, ctx, True)
                retry["why"] = "Grasp failed; re-approaching the visible object."
                await self.send(msg_decision(retry))
                await self._sleep_sim(pick_cost)
                t += pick_cost
                grasp_ok = True                            # mock: the retry always works
                await self.send(msg_action_result("pick", True, pick_cost, 0.4))
            success = grasp_ok
            ctx.delivered = success

        llm_calls = sum(1 for r in self.planner.log[log_start:] if r["llm_attempted"])
        await self.send(msg_episode_end(success, t, self.looks, llm_calls, self.true_place))


# --------------------------------------------------------------------------
# FastAPI app
# --------------------------------------------------------------------------

app = FastAPI(title="Second Look: mock belief/planner API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_origin_regex=VERCEL_ORIGIN_RE,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
async def health():
    return {"ok": True, "allowed_origins": ORIGINS}


@app.get("/api/status")
async def api_status(check: bool = False):
    now = time.time()
    backend_info = {
        "status": "connected",
        "service": "FastAPI",
        "version": "2.1.0",
        "uptime_s": round(now - _SERVER_START_TIME, 1),
    }

    simulator_url = os.getenv("SIMULATOR_URL", "http://127.0.0.1:8001").rstrip("/")
    sim_status = "connected" if _LAST_SIM_OK else "standby"
    sim_detail = "Live simulation service configured"

    nebius_key = os.getenv("NEBIUS_API_KEY", "").strip()
    configured_model = os.getenv("NEMOTRON_MODEL", "nvidia/nemotron-4-340b-instruct")

    nebius_info = {
        "status": "configured" if nebius_key else "unconfigured",
        "base_url": "https://api.tokenfactory.nebius.com/v1/",
        "configured": bool(nebius_key),
        "detail": "Nebius API key configured in environment" if nebius_key else "NEBIUS_API_KEY environment variable not set",
    }

    nemotron_info = {
        "status": "ready" if nebius_key else "offline",
        "model": configured_model,
        "detail": "NVIDIA Nemotron available for AI reasoning" if nebius_key else "AI inference endpoint offline. Fast rule-based planner active as backup.",
        "fallback_active": not bool(nebius_key),
    }

    if check:
        # Check simulator with strict connect timeout
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(0.5, connect=0.2)) as client:
                res = await client.get(f"{simulator_url}/health")
                if res.status_code == 200:
                    sim_status = "connected"
                    sim_detail = res.json().get("environment", "SecondLookEnv")
        except Exception:
            sim_status = "offline"
            sim_detail = "Simulator service unreachable"

        # Check Nebius with cache
        if nebius_key and (now - _NEBIUS_CACHE.get("last_check", 0) > 30):
            try:
                from openai import OpenAI
                client = OpenAI(base_url=nebius_info["base_url"], api_key=nebius_key, timeout=2.0)
                models = client.models.list()
                model_ids = [m.id for m in models.data]
                has_nemotron = any("nemotron" in m.lower() for m in model_ids)
                _NEBIUS_CACHE["last_check"] = now
                _NEBIUS_CACHE["verified"] = True
                _NEBIUS_CACHE["has_nemotron"] = has_nemotron
                _NEBIUS_CACHE["detail"] = f"Verified: {len(model_ids)} models available via Token Factory"
            except Exception as exc:
                _NEBIUS_CACHE["last_check"] = now
                _NEBIUS_CACHE["verified"] = False
                _NEBIUS_CACHE["detail"] = f"Inference check failed: {type(exc).__name__}"

    if _NEBIUS_CACHE.get("last_check", 0) > 0:
        if _NEBIUS_CACHE.get("verified"):
            nebius_info["status"] = "verified"
            nebius_info["detail"] = _NEBIUS_CACHE.get("detail")
            nemotron_info["status"] = "ready"
        else:
            nebius_info["status"] = "degraded"
            nebius_info["detail"] = _NEBIUS_CACHE.get("detail")
            nemotron_info["status"] = "offline"

    return {
        "ok": True,
        "backend": backend_info,
        "simulator": {
            "status": sim_status,
            "url": simulator_url,
            "detail": sim_detail,
        },
        "nebius": nebius_info,
        "nemotron": nemotron_info,
        "timestamp": now,
        "mode": "live" if (sim_status == "connected" or nebius_info["status"] in ("configured", "verified")) else "demo",
    }


@app.post("/simulator/command")
async def simulator_command(payload: dict):
    simulator_url = os.getenv(
        "SIMULATOR_URL",
        "http://127.0.0.1:8001",
    ).rstrip("/")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{simulator_url}/command",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=exc.response.text,
        ) from exc

    except (httpx.RequestError, httpx.TimeoutException) as exc:
        raise HTTPException(
            status_code=503,
            detail="Simulator service is unavailable or timed out.",
        ) from exc


@app.post("/simulator/reset")
async def simulator_reset(payload: dict):
    simulator_url = os.getenv("SIMULATOR_URL", "http://127.0.0.1:8001").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{simulator_url}/simulator/reset", json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text) from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Simulator service is unavailable or timed out.") from exc


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    origin = websocket.headers.get("origin")
    if not origin_ok(origin):
        await websocket.close(code=1008)
        return
    await websocket.accept()

    simulator_url = os.getenv("SIMULATOR_URL", "http://127.0.0.1:8001").rstrip("/")
    current_task: asyncio.Task | None = None
    current_episode_id = ""
    active_episode: dict = {"episode_id": None, "belief": None, "ctx": None, "target": None, "t": 0.0}
    active_mock: dict = {"episode": None}

    async def send(payload: dict):
        await websocket.send_text(json.dumps(payload))

    async def sim_post(path: str, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(f"{simulator_url}{path}", json=payload)
            response.raise_for_status()
            return response.json()

    async def run_live_episode(cmd: dict, episode_id: str):
        engine = cmd.get("engine", "rule")
        if engine not in ("rule", "auto", "llm", "nemotron"):
            await send({"type": "error", "why": f"unknown engine {engine!r}"})
            return
        target = cmd.get("target", "bottle_blue")
        if target not in PL.OBJECTS:
            await send({"type": "error", "why": f"unknown target {target!r}"})
            return
        true_place = cmd.get("true_place", "L")
        if true_place not in RB.HIDING:
            true_place = "L"
        start = cmd.get("start", "home")
        hidden_place = true_place

        seed = int(cmd.get("seed", 0))
        planner = get_planner(engine)
        log_start = len(planner.log)
        t0 = 0.0
        looks = 0
        sensor_events: list[tuple[float, str]] = []

        belief = RB.Belief(target, "L", 1.0 / 3.0, 0.0)
        ctx = PL.PlanContext(obj=target, now=0.0, last_seen_t=0.0)

        try:
            reset_result = await sim_post(
                "/simulator/reset",
                {
                    "target": target,
                    "start": start,
                    "seed": seed,
                    "hidden_place": hidden_place,
                },
            )
            obs = reset_result.get("observation", {})
            t0 = float(obs.get("simulation_time", 0.0))
            active_episode.update({"episode_id": episode_id, "belief": belief, "ctx": ctx,
                                   "target": target, "t": t0})
            state = obs.get("state", [])
            visible = bool(obs.get("target_visible", False))
            await send({
                "type": "observation", "episode_id": episode_id, "t": t0,
                "front_image": obs.get("front"), "wrist_image": obs.get("wrist"),
                "state": state, "detections": [], "occluders": [], "events": [], "sensor_event": None,
            })
            await send({"type": "belief", "episode_id": episode_id, "t": t0,
                        "object": target, "place": belief.place, "confidence": belief.conf,
                        "last_seen_t": belief.t, "status": belief_status(belief.conf, visible)})

            success = False
            for _ in range(len(RB.HIDING) + 2):
                ctx.now = t0
                
                sensor_event_count = len(ctx.sensor_events)

                dec = await asyncio.to_thread(planner.decide, belief, ctx, visible)
                decision = msg_decision(dec)
                decision.update({"episode_id": episode_id, "t": round(t0, 2)})
                await send(decision)

                action = dec.get("action")
                if action in ("ask", "finish"):
                    break
                if action == "look":
                    action_result = await sim_post("/command", {
                        "action": "look", "target": target, "command": dec.get("target", "L"), "seed": seed
                    })
                    looks += 1
                    duration = float(action_result.get("duration_s", 0.0))
                    t0 += duration
                    active_episode["t"] = t0
                    found = bool(action_result.get("found", False))
                    await send({"type": "action_result", "episode_id": episode_id, "t": round(t0, 2),
                                "skill": "look", "ok": bool(action_result.get("ok")) and found,
                                "duration_s": round(duration, 2), "target": target,
                                "place": dec.get("target")})
                    PL.note_look_result(belief, ctx, dec.get("target", "L"), found, t0)
                    
                    # If an object disturbance occurred during this look,
                    # do not keep the location ruled out using stale information.
                    if len(ctx.sensor_events) > sensor_event_count:
                        ctx.ruled_out.clear()

                    obs = action_result.get("observation", {})
                    visible = bool(obs.get("target_visible", False))
                    await send({"type": "observation", "episode_id": episode_id, "t": round(t0, 2),
                                "front_image": obs.get("front"), "wrist_image": obs.get("wrist"),
                                "state": obs.get("state", []), "detections": [], "occluders": [], "events": [],
                                "sensor_event": None})
                    await send({"type": "belief", "episode_id": episode_id, "t": round(t0, 2),
                                "object": target, "place": belief.place, "confidence": belief.conf,
                                "last_seen_t": belief.t,
                                "status": belief_status(belief.conf, visible)})
                    if not found:
                        continue
                elif action == "pick":
                    action_result = await sim_post("/command", {
                        "action": "pick", "target": target, "seed": seed
                    })
                    duration = float(action_result.get("duration_s", 0.0))
                    t0 += duration
                    active_episode["t"] = t0

                    success = (
                        bool(action_result.get("ok"))
                        and bool(action_result.get("in_tray", False))
                    )

                    await send({
                        "type": "action_result",
                        "episode_id": episode_id,
                        "t": round(t0, 2),
                        "skill": "pick",
                        "ok": success,
                        "in_tray": bool(action_result.get("in_tray", False)),
                        "duration_s": round(duration, 2),
                        "target": target,
                        "gripper_state_at_end": action_result.get(
                            "observation", {}
                        ).get("state", [None, None, None, None])[-1],
                    })
                    
                    ctx.delivered = success
                    if not success:
                        PL.note_grasp_result(belief, ctx, False, t0)
                    break
                else:
                    await send({"type": "error", "episode_id": episode_id,
                                "why": f"unsupported planner action {action!r}"})
                    break

            llm_calls = sum(1 for row in planner.log[log_start:] if row.get("llm_attempted"))
            await send({"type": "episode_end", "episode_id": episode_id, "success": success,
                        "total_time_s": round(t0, 2), "looks": looks, "llm_calls": llm_calls,
                        "ground_truth_place": true_place if start.startswith("look_") else None})
        except asyncio.CancelledError:
            raise
        except httpx.HTTPStatusError as exc:
            await send({"type": "error", "episode_id": episode_id,
                        "why": f"simulator returned HTTP {exc.response.status_code}: {exc.response.text[:300]}"})
        except (httpx.RequestError, asyncio.TimeoutError) as exc:
            await send({"type": "error", "episode_id": episode_id,
                        "why": f"simulator unavailable: {type(exc).__name__}"})
        except Exception as exc:
            await send({"type": "error", "episode_id": episode_id,
                        "why": f"live episode failed: {type(exc).__name__}: {exc}"})

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                cmd = json.loads(raw)
            except json.JSONDecodeError:
                await send({"type": "error", "why": "bad JSON"})
                continue
            name = cmd.get("cmd")
            if name == "start":
                if current_task and not current_task.done():
                    current_task.cancel()
                
                # Check whether to run MockEpisode or real live simulator episode
                is_mock = (
                    cmd.get("mode") == "mock"
                    or "scenario" in cmd
                    or "hidden_seconds" in cmd
                    or "grasp_fail_prob" in cmd
                ) and cmd.get("mode") != "live"

                if is_mock:
                    engine = cmd.get("engine", "rule")
                    if engine not in ("rule", "auto", "llm", "nemotron"):
                        await send({"type": "error", "why": f"unknown engine {engine!r}"})
                        continue
                    if str(cmd.get("true_place", "L")) not in RB.HIDING:
                        await send({"type": "error", "why": f"unknown true_place {cmd.get('true_place')!r}; use one of {RB.HIDING}"})
                        continue
                    ep = MockEpisode(
                        send=send,
                        scenario=cmd.get("scenario", "S2"),
                        hidden_seconds=cmd.get("hidden_seconds", 40.0),
                        move_prob=cmd.get("move_prob", 0.0),
                        sensor_detect_rate=cmd.get("sensor_detect_rate", 0.0),
                        false_alarm_rate=cmd.get("false_alarm_rate", 0.0),
                        sim_speed=cmd.get("sim_speed", 5.0),
                        true_place=cmd.get("true_place"),
                        grasp_fail_prob=cmd.get("grasp_fail_prob", 0.1),
                        engine=engine,
                        seed=cmd.get("seed"),
                    )
                    active_mock["episode"] = ep
                    current_task = asyncio.create_task(ep.run())
                else:
                    active_mock["episode"] = None
                    current_episode_id = str(cmd.get("episode_id") or f"live-{random.randint(100000, 999999)}")
                    current_task = asyncio.create_task(run_live_episode(cmd, current_episode_id))
            elif name == "reset":
                if current_task and not current_task.done():
                    current_task.cancel()
                active_mock["episode"] = None
                try:
                    result = await sim_post("/simulator/reset", {
                        "target": cmd.get("target", "bottle_blue"),
                        "start": cmd.get("start", "home"), "seed": int(cmd.get("seed", 0))
                    })
                    await send({"type": "reset_ack", "observation": result.get("observation")})
                except Exception:
                    # In mock mode or when simulator is offline, respond with clean reset_ack
                    await send({"type": "reset_ack"})
            elif name == "move_object":
                mock_ep = active_mock.get("episode")
                if mock_ep and current_task and not current_task.done():
                    mock_ep.move_requested = True
                    continue
                target = active_episode.get("target") or cmd.get("target", "bottle_blue")
                try:
                    result = await sim_post("/command", {"action": "disturb", "target": target,
                                                          "seed": int(cmd.get("seed", 0))})
                    event = result.get("event")
                    belief = active_episode.get("belief")
                    ctx = active_episode.get("ctx")
                    now = float(active_episode.get("t", 0.0))
                    if event and belief is not None and ctx is not None:
                        event = dict(event)
                        event["t"] = now
                        EW.process_event(event, {target: belief}, now)
                        ctx.sensor_events.append((now, event.get("zone", "L")))
                        # A disturbance invalidates previous negative search results.
                        ctx.ruled_out.clear()
                        ctx.now = now
                    obs = result.get("observation", {})
                    await send({"type": "observation", "episode_id": active_episode.get("episode_id"),
                                "t": round(now, 2), "front_image": obs.get("front"),
                                "wrist_image": obs.get("wrist"), "state": obs.get("state", []),
                                "detections": [], "occluders": [], "events": [event] if event else [],
                                "sensor_event": event})
                    if belief is not None:
                        await send({"type": "belief", "episode_id": active_episode.get("episode_id"),
                                    "t": round(now, 2), "object": target, "place": belief.place,
                                    "confidence": belief.conf, "last_seen_t": belief.t,
                                    "status": belief_status(belief.conf, bool(obs.get("target_visible", False)))})
                except Exception as exc:
                    await send({"type": "error", "why": f"simulated disturbance failed: {type(exc).__name__}: {exc}"})
            else:
                await send({"type": "error", "why": f"unknown cmd {name!r}"})
    except WebSocketDisconnect:
        pass
    finally:
        if current_task and not current_task.done():
            current_task.cancel()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
