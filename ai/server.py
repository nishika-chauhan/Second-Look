"""
Second Look: mock-mode belief/planner API (role B), v2.

Serves the real belief + planner code over FastAPI + WebSocket so the dashboard
(role A) can be built and tested before the simulator is wired in.

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
    "http://localhost:5173", "http://127.0.0.1:5173",      # Vite dev server
    "http://localhost:4173", "http://127.0.0.1:4173",      # Vite preview
]


def allowed_origins() -> list:
    raw = os.environ.get("ALLOWED_ORIGINS", "").strip()
    return [o.strip() for o in raw.split(",") if o.strip()] if raw else list(DEFAULT_ORIGINS)


ORIGINS = allowed_origins()


def origin_ok(origin: str | None) -> bool:
    if "*" in ORIGINS or origin is None:
        return True
    return origin in ORIGINS


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
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["*"], allow_headers=["*"])


@app.get("/")
async def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
async def health():
    return {"ok": True, "allowed_origins": ORIGINS}


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    origin = websocket.headers.get("origin")
    if not origin_ok(origin):
        await websocket.close(code=1008)                   # policy violation
        return
    await websocket.accept()

    async def send(payload: dict):
        await websocket.send_text(json.dumps(payload))

    current: dict = {"episode": None, "task": None}

    async def run_episode(ep: MockEpisode):
        try:
            await ep.run()
        except asyncio.CancelledError:
            raise
        except Exception as e:                             # never let a bug kill the socket silently
            try:
                await send({"type": "error", "why": f"episode failed: {type(e).__name__}: {e}"})
            except Exception:
                pass

    def cancel_current():
        task = current["task"]
        if task and not task.done():
            task.cancel()

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
                engine = cmd.get("engine", "rule")
                if engine not in ("rule", "auto", "llm", "nemotron"):
                    await send({"type": "error", "why": f"unknown engine {engine!r}"})
                    continue
                cancel_current()
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
                current["episode"] = ep
                current["task"] = asyncio.create_task(run_episode(ep))
            elif name == "move_object":
                ep = current["episode"]
                if ep and current["task"] and not current["task"].done():
                    ep.move_requested = True
                else:
                    await send({"type": "error", "why": "no running episode to move the object in"})
            elif name == "reset":
                cancel_current()
                await send({"type": "reset_ack"})
            else:
                await send({"type": "error", "why": f"unknown cmd {name!r}"})
    except WebSocketDisconnect:
        pass
    finally:
        cancel_current()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
