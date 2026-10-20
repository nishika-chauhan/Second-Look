"""Tiny WebSocket client: run one episode against the local server and print what a dashboard would see.

    pip install websockets
    python ai/ws_try.py --engine llm            # server must be running (uvicorn server:app --port 8000)
"""
import argparse, asyncio, json

import websockets


async def main(a):
    async with websockets.connect(a.url) as ws:
        await ws.send(json.dumps({
            "cmd": "start", "engine": a.engine, "seed": a.seed, "hidden_seconds": 20,
            "true_place": "L", "move_prob": 10, "sensor_detect_rate": 1.0,   # object moves, sensor fires -> non-routine
            "sim_speed": a.speed, "grasp_fail_prob": 0.0}))
        while True:
            m = json.loads(await ws.recv())
            t = m["type"]
            if t == "decision":
                print(f"DECISION engine={m['engine']:4s} action={m['action']:6s} target={m['target']:12s} "
                      f"offline={m['offline']} latency={m['latency_ms']}ms model={m['model'] or '-'}"
                      f"{'  fallback: ' + m['fallback_reason'] if m['fallback_reason'] else ''}")
                print(f"         why: {m['why']}")
            elif t == "observation" and m["sensor_event"]:
                print(f"SENSOR   t={m['t']}  {m['sensor_event']}")
            elif t in ("action_result", "episode_end", "error"):
                print(t.upper(), {k: v for k, v in m.items() if k != "type"})
            if t in ("episode_end", "error"):
                break


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="ws://localhost:8000/ws")
    ap.add_argument("--engine", default="llm", choices=["rule", "auto", "llm"])
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--speed", type=float, default=50)
    asyncio.run(main(ap.parse_args()))
