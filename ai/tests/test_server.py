"""
pytest for ai/server.py: message flow, origin check, move_object, error handling.
Runs the app in-process with Starlette's TestClient (no port, no network).

    pip install fastapi httpx
    pytest ai/tests/test_server.py -v
"""

import os
import sys

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import server as S  # noqa: E402

client = TestClient(S.app)
FAST = {"cmd": "start", "sim_speed": 100000, "hidden_seconds": 20, "seed": 1,
        "grasp_fail_prob": 0.0}


def collect(ws, until="episode_end", limit=400):
    msgs = []
    for _ in range(limit):
        m = ws.receive_json()
        msgs.append(m)
        if m["type"] == until:
            return msgs
    raise AssertionError(f"never saw {until}; got {[m['type'] for m in msgs][-5:]}")


def test_health_lists_origins():
    r = client.get("/health").json()
    assert r["ok"] is True and "http://localhost:5173" in r["allowed_origins"]


def test_full_episode_message_flow():
    with client.websocket_connect("/ws") as ws:
        ws.send_json({**FAST, "true_place": "L"})
        msgs = collect(ws)
    types = [m["type"] for m in msgs]
    assert types[0] == "observation" and types[-1] == "episode_end"
    assert {"belief", "decision", "action_result"} <= set(types)
    end = msgs[-1]
    assert end["success"] is True and end["ground_truth_place"] == "L"
    assert end["looks"] == 1 and end["llm_calls"] == 0          # rule engine, remembered place correct


def test_confidence_decays_while_hidden():
    with client.websocket_connect("/ws") as ws:
        ws.send_json({**FAST, "hidden_seconds": 60, "true_place": "R"})
        msgs = collect(ws)
    conf = [m["confidence"] for m in msgs if m["type"] == "belief"][:11]   # t = 0, 6, ..., 60
    assert conf[0] == 1.0 and all(a >= b for a, b in zip(conf, conf[1:]))
    assert conf[10] == pytest.approx(0.5, abs=0.01)             # one half-life (60 s) gone


def test_decision_message_has_stable_shape():
    with client.websocket_connect("/ws") as ws:
        ws.send_json({**FAST, "true_place": "L"})
        msgs = collect(ws)
    dec = [m for m in msgs if m["type"] == "decision"]
    assert dec
    for d in dec:
        for k in ("engine", "action", "target", "command", "why", "latency_ms",
                  "offline", "fallback_reason", "model", "agree_with_rule"):
            assert k in d
        assert d["engine"] == "rule" and d["offline"] is False
    picks = [d for d in dec if d["action"] == "pick"]
    assert picks and picks[0]["command"] == "pick up the blue bottle and place it in the tray"


def test_sensor_alarm_moves_object_and_flips_search_order():
    """Object really moves at the first step, sensor sees it: belief is cut and the
    planner goes to the new place first, so the first look succeeds."""
    with client.websocket_connect("/ws") as ws:
        ws.send_json({**FAST, "true_place": "L", "move_prob": 10, "sensor_detect_rate": 1.0})
        msgs = collect(ws)
    assert any(m["type"] == "observation" and m["sensor_event"] for m in msgs)
    end = msgs[-1]
    assert end["ground_truth_place"] == "R"
    looks = [m for m in msgs if m["type"] == "decision" and m["action"] == "look"]
    assert looks[0]["target"] == "R"
    assert end["looks"] == 1 and end["success"] is True


def test_moved_without_sensor_costs_an_extra_look():
    with client.websocket_connect("/ws") as ws:
        ws.send_json({**FAST, "true_place": "L", "move_prob": 10, "sensor_detect_rate": 0.0})
        msgs = collect(ws)
    end = msgs[-1]
    assert end["ground_truth_place"] == "R" and end["looks"] == 2 and end["success"] is True


def test_move_object_command_while_hidden():
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"cmd": "start", "sim_speed": 50, "hidden_seconds": 100, "seed": 1,
                      "true_place": "L", "sensor_detect_rate": 1.0, "grasp_fail_prob": 0.0})
        assert ws.receive_json()["type"] == "observation"
        ws.send_json({"cmd": "move_object"})
        msgs = collect(ws)
    assert msgs[-1]["ground_truth_place"] == "R"
    assert any(m["type"] == "observation" and m["sensor_event"] for m in msgs)


def test_move_object_without_episode_is_an_error():
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"cmd": "move_object"})
        assert ws.receive_json()["type"] == "error"


def test_unknown_command_bad_json_and_bad_engine():
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"cmd": "dance"})
        assert ws.receive_json()["type"] == "error"
        ws.send_text("not json")
        assert ws.receive_json()["why"] == "bad JSON"
        ws.send_json({"cmd": "start", "engine": "gpt"})
        assert "unknown engine" in ws.receive_json()["why"]


def test_reset_acknowledged():
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"cmd": "reset"})
        assert ws.receive_json()["type"] == "reset_ack"


def test_dashboard_origin_allowed():
    with client.websocket_connect("/ws", headers={"origin": "http://localhost:5173"}) as ws:
        ws.send_json({"cmd": "reset"})
        assert ws.receive_json()["type"] == "reset_ack"


def test_foreign_browser_origin_rejected():
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws", headers={"origin": "http://evil.example"}) as ws:
            ws.receive_json()


def test_cors_header_for_dashboard_origin_on_http():
    r = client.get("/health", headers={"origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    r2 = client.get("/health", headers={"origin": "http://evil.example"})
    assert "access-control-allow-origin" not in r2.headers


def test_auto_engine_without_api_key_falls_back_but_still_finishes(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.setattr(S.PL, "_load_dotenv", lambda: None)
    S._PLANNERS.pop("auto", None)
    with client.websocket_connect("/ws") as ws:
        # sensor fires at the remembered place -> probabilities close -> LLM wanted -> no key -> fallback
        ws.send_json({**FAST, "engine": "auto", "true_place": "L", "move_prob": 10,
                      "sensor_detect_rate": 1.0})
        msgs = collect(ws)
    assert msgs[-1]["success"] is True and msgs[-1]["llm_calls"] >= 1
    looks = [m for m in msgs if m["type"] == "decision" and m["action"] == "look"]
    assert looks[0]["offline"] is True and "NEBIUS_API_KEY" in looks[0]["fallback_reason"]
    S._PLANNERS.pop("auto", None)


def test_belief_messages_carry_sim_time():
    with client.websocket_connect("/ws") as ws:
        ws.send_json({**FAST, "hidden_seconds": 60, "true_place": "R"})
        msgs = collect(ws)
    beliefs = [m for m in msgs if m["type"] == "belief"]
    assert all("t" in b for b in beliefs)
    ts = [b["t"] for b in beliefs]
    assert ts == sorted(ts) and ts[0] == 0.0 and ts[-1] > 60
