"""
Second Look -- mock-mode belief/planner API (role B)

Serves the belief + planner logic over FastAPI + WebSocket so the
dashboard (role A) can build and test against real message traffic
before the simulator (role C/D) is wired in.

Message schema matches Part 2.2 of the team plan exactly:
  observation   : sim -> perception
  belief        : memory -> planner, dashboard
  decision      : planner -> tools, dashboard
  action_result : tools -> memory
  episode_end   : runner -> results

Run:
    pip install fastapi "uvicorn[standard]"
    uvicorn server:app --reload --port 8000

Then connect a WebSocket client to ws://localhost:8000/ws and send:
    {"cmd": "start", "scenario": "S2", "hidden_seconds": 40}
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from dataclasses import dataclass

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from ai.regions_belief import Belief, tick, place_probs, search_order


HALF_LIFE_S = 60.0
DISTURB = 0.35
LOOK_COST_S = {"L": 8.0, "R": 8.0}
HIDING = ["L", "R"]


@dataclass
class Belief:
    place: str      # best-guess hiding place, e.g. "L" or "R"
    conf: float     # confidence 0..1 that it's still there
    t: float        # simulated-seconds timestamp of last update


def tick(b: Belief, now: float, hidden: bool) -> None:
    """Trust fades while the object is out of sight."""
    if hidden:
        b.conf *= 0.5 ** ((now - b.t) / HALF_LIFE_S)
    b.t = now


def place_probs(b: Belief, visible_in_front: bool) -> dict:
    """P(object at each hiding place)."""
    if visible_in_front:
        return {"OPEN": 1.0}
    p = {pl: 0.0 for pl in HIDING}
    others = [pl for pl in HIDING if pl != b.place]
    if b.place in p:
        p[b.place] = b.conf
    spread = (1.0 - b.conf) / max(len(others) + 1, 1)
    for pl in others:
        p[pl] += spread
    total = sum(p.values())
    return {pl: v / total for pl, v in p.items()}


def search_order(b: Belief, visible_in_front: bool) -> list:
    """Best-first search order: highest probability per second of looking."""
    p = place_probs(b, visible_in_front)
    return sorted((pl for pl in HIDING if pl in p), key=lambda pl: -p[pl] / LOOK_COST_S[pl])


# --------------------------------------------------------------------------
# Message builders -- match Part 2.2's fields exactly so the dashboard never
# has to special-case "mock" vs "real" messages.
# --------------------------------------------------------------------------

def msg_observation(t, front_ref, wrist_ref, state, sensor_event=None):
    return {
        "type": "observation",
        "t": round(t, 2),
        "front_image": front_ref,
        "wrist_image": wrist_ref,
        "state": state,
        "sensor_event": sensor_event,
    }


def msg_belief(obj, place, confidence, last_seen_t, status):
    return {
        "type": "belief",
        "object": obj,
        "place": place,
        "confidence": round(confidence, 3),
        "last_seen_t": round(last_seen_t, 2),
        "status": status,
    }


def msg_decision(engine, action, target, command, why, latency_ms):
    return {
        "type": "decision",
        "engine": engine,
        "action": action,
        "target": target,
        "command": command,
        "why": why,
        "latency_ms": latency_ms,
    }


def msg_action_result(skill, ok, duration_s, gripper_state_at_end=None):
    return {
        "type": "action_result",
        "skill": skill,
        "ok": ok,
        "duration_s": round(duration_s, 2),
        "gripper_state_at_end": gripper_state_at_end,
    }


def msg_episode_end(success, total_time_s, looks, llm_calls, ground_truth_place):
    return {
        "type": "episode_end",
        "success": success,
        "total_time_s": round(total_time_s, 2),
        "looks": looks,
        "llm_calls": llm_calls,
        "ground_truth_place": ground_truth_place,
    }


def belief_status(conf: float, visible: bool) -> str:
    if visible:
        return "visible"
    if conf < 0.5:
        return "stale"
    return "unknown"


# --------------------------------------------------------------------------
# Mock episode runner -- simulates S2 (hidden, then fetch) and, optionally,
# S3 (moved while hidden) without needing the real MuJoCo sim or a trained
# VLA. Real time is compressed by `sim_speed` simulated-seconds-per-wall-
# second so episodes play out in a few real seconds for UI development.
# --------------------------------------------------------------------------

class MockEpisode:
    def __init__(self, send, scenario="S2", hidden_seconds=40.0,
                 move_prob=0.0, sensor_detect_rate=0.0, sim_speed=5.0,
                 true_place=None, grasp_fail_prob=0.1):
        self.send = send  # async fn(dict) -> None
        self.scenario = scenario
        self.hidden_seconds = hidden_seconds
        self.move_prob = move_prob
        self.sensor_detect_rate = sensor_detect_rate
        self.sim_speed = sim_speed
        self.true_place = true_place or random.choice(HIDING)
        self.grasp_fail_prob = grasp_fail_prob
        self.obj = "bottle_blue"
        self.looks = 0
        self.llm_calls = 0

    async def _sleep_sim(self, sim_seconds: float):
        await asyncio.sleep(sim_seconds / self.sim_speed)

    async def run(self):
        t = 0.0
        belief = Belief(place=self.true_place, conf=1.0, t=0.0)

        await self.send(msg_observation(t, "mock://front/0.jpg", None,
                                         {"x": 0, "y": 0, "z": 0.2, "gripper": 1}))
        await self.send(msg_belief(self.obj, belief.place, belief.conf, belief.t,
                                    belief_status(belief.conf, False)))

        # Count down the hidden period in small steps so the dashboard sees
        # confidence actually decaying, not just jump from 1.0 to some value.
        step = max(self.hidden_seconds / 10.0, 1.0)
        while t < self.hidden_seconds:
            dt = min(step, self.hidden_seconds - t)
            await self._sleep_sim(dt)
            t += dt
            tick(belief, t, hidden=True)

            sensor_event = None
            if self.move_prob and random.random() < self.move_prob / 10.0:
                other = [p for p in HIDING if p != belief.place][0]
                belief.place = other if random.random() < 0.5 else belief.place
            if self.sensor_detect_rate and random.random() < self.sensor_detect_rate / 10.0:
                belief.conf *= DISTURB
                sensor_event = {"place": belief.place, "fired": True}

            await self.send(msg_observation(t, "mock://front/blocked.jpg", None,
                                             {"x": 0, "y": 0, "z": 0.2, "gripper": 1},
                                             sensor_event))
            await self.send(msg_belief(self.obj, belief.place, belief.conf, belief.t,
                                        belief_status(belief.conf, False)))

        # Fetch: decide where to look first.
        order = search_order(belief, visible_in_front=False)
        found_place = None
        for target in order:
            reason = self._why(order, target)
            await self.send(msg_decision("rule", "look", target,
                                          f"look at {target}", reason,
                                          random.randint(5, 40)))
            self.looks += 1
            cost = LOOK_COST_S[target]
            await self._sleep_sim(cost)
            t += cost
            ok = (target == self.true_place)
            await self.send(msg_action_result("look", ok, cost))

            if ok:
                belief.place, belief.conf, belief.t = target, 1.0, t
                found_place = target
                await self.send(msg_belief(self.obj, belief.place, belief.conf, belief.t, "visible"))
                break
            else:
                remaining = [p for p in HIDING if p != target]
                if remaining:
                    belief.place, belief.conf, belief.t = remaining[0], 1.0, t
                await self.send(msg_belief(self.obj, belief.place, belief.conf, belief.t, "unknown"))

        success = False
        if found_place:
            command = f"pick up the {self.obj.replace('_', ' ')} and place it in the tray"
            await self.send(msg_decision("rule", "pick", self.obj, command,
                                          "Target is visible; executing the pick.",
                                          random.randint(5, 20)))
            pick_cost = 6.0
            await self._sleep_sim(pick_cost)
            t += pick_cost
            grasp_ok = random.random() > self.grasp_fail_prob
            gripper_end = 0.4 if grasp_ok else 0.0
            await self.send(msg_action_result("pick", grasp_ok, pick_cost, gripper_end))

            if not grasp_ok:
                belief.conf = 0.05
                await self.send(msg_belief(self.obj, belief.place, belief.conf, belief.t, "stale"))
                # one retry, matching the doc's "failed grasp -> replan" evidence path
                await self.send(msg_decision("rule", "pick", self.obj, command,
                                              "Grasp failed; re-approaching.",
                                              random.randint(5, 20)))
                await self._sleep_sim(pick_cost)
                t += pick_cost
                grasp_ok = True
                await self.send(msg_action_result("pick", grasp_ok, pick_cost, 0.4))

            success = grasp_ok

        await self.send(msg_episode_end(success, t, self.looks, self.llm_calls, self.true_place))

    def _why(self, order: list, target: str) -> str:
        if len(order) > 1 and target == order[0]:
            other = order[1]
            return (f"{target} is the more likely spot right now "
                    f"(confidence favors {target} over {other}), checking there first.")
        return f"Checking {target}."


# --------------------------------------------------------------------------
# FastAPI app
# --------------------------------------------------------------------------

app = FastAPI(title="Second Look -- mock belief/planner API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten this once the dashboard has a fixed origin
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    # FastAPI has no route at "/" by default, hence the 404 you saw there.
    # Send browsers to the interactive docs instead.
    return RedirectResponse(url="/docs")


@app.get("/health")
async def health():
    return {"ok": True}


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()

    async def send(payload: dict):
        await websocket.send_text(json.dumps(payload))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                cmd = json.loads(raw)
            except json.JSONDecodeError:
                await send({"type": "error", "why": "bad JSON"})
                continue

            if cmd.get("cmd") == "start":
                episode = MockEpisode(
                    send=send,
                    scenario=cmd.get("scenario", "S2"),
                    hidden_seconds=cmd.get("hidden_seconds", 40.0),
                    move_prob=cmd.get("move_prob", 0.0),
                    sensor_detect_rate=cmd.get("sensor_detect_rate", 0.0),
                    sim_speed=cmd.get("sim_speed", 5.0),
                    true_place=cmd.get("true_place"),
                    grasp_fail_prob=cmd.get("grasp_fail_prob", 0.1),
                )
                asyncio.create_task(episode.run())
            elif cmd.get("cmd") == "reset":
                await send({"type": "reset_ack"})
            else:
                await send({"type": "error", "why": f"unknown cmd {cmd.get('cmd')!r}"})
    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
