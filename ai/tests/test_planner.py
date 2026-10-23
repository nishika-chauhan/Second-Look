"""
pytest for ai/planner.py. Uses a fake LLM client, so no network or API key is needed.

Run from the repo root:
    pytest ai/tests/test_planner.py -v
"""

import json
import os
import sys
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import regions_belief as RB
import planner as PL

pytestmark = pytest.mark.skipif(PL.NC is None, reason="needs `pip install openai` (nemotron_client import)")


# ---------------------------------------------------------------------------
# Fake LLM client
# ---------------------------------------------------------------------------

class FakeClient:
    """Mimics client.chat.completions.create(...) returning a forced tool call."""

    def __init__(self, decision=None, raises=None, delay=0.0, content_only=None):
        self.decision, self.raises, self.delay, self.content_only = decision, raises, delay, content_only
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        if self.delay:
            time.sleep(self.delay)
        if self.raises:
            raise self.raises
        if self.content_only is not None:
            msg = SimpleNamespace(tool_calls=None, content=self.content_only)
        else:
            tc = SimpleNamespace(function=SimpleNamespace(arguments=json.dumps(self.decision)))
            msg = SimpleNamespace(tool_calls=[tc], content=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)],
                               usage=SimpleNamespace(total_tokens=123))


MODELS = {"small": "nvidia/fake-nano", "big": "nvidia/fake-ultra"}


def planner(client, mode="auto", **kw):
    return PL.Planner(mode=mode, client=client, models=MODELS, **kw)


def clear_belief():          # 0.75 conf at L: L is the clear favourite (0.86 / 0.14)
    return RB.Belief("bottle_blue", "L", 0.75, 25.0)


def close_belief():          # sensor fired: 0.42 / 0.58, gap 0.16 < margin
    return RB.Belief("bottle_blue", "L", 0.75 * RB.DISTURB, 25.0)


def ctx(**kw):
    return PL.PlanContext(now=25.0, last_seen_t=0.0, **kw)


GOOD_LOOK_R = {"action": "look", "target": "R", "command": "whatever", "why": "Sensor says left was disturbed."}


# ---------------------------------------------------------------------------
# Rule planner
# ---------------------------------------------------------------------------

def test_rule_picks_when_visible_with_training_phrase():
    d = PL.rule_decide(clear_belief(), ctx(), visible=True)
    assert d["action"] == "pick" and d["target"] == "bottle_blue"
    assert d["command"] == "pick up the blue bottle and place it in the tray"


def test_rule_looks_at_remembered_place_when_clear():
    d = PL.rule_decide(clear_belief(), ctx(), visible=False)
    assert (d["action"], d["target"]) == ("look", "L")


def test_rule_flips_after_sensor():
    d = PL.rule_decide(close_belief(), ctx(sensor_events=[(13.0, "L")]), visible=False)
    assert d["target"] == "R"
    assert "disturbed" in d["why"]


def test_rule_matches_search_order():
    for conf in (0.2, 0.5, 0.9):
        b = RB.Belief("bottle_blue", "L", conf, 0.0)
        assert PL.rule_decide(b, ctx(), False)["target"] == RB.search_order(b, False)[0]


def test_ruled_out_place_is_never_chosen():
    d = PL.rule_decide(clear_belief(), ctx(ruled_out={"L"}), visible=False)
    assert d["target"] == "R"


def test_memory_certain_but_place_empty_falls_through_to_other_place():
    b = RB.Belief("bottle_blue", "L", 1.0, 0.0)       # place_probs gives R probability 0
    d = PL.rule_decide(b, ctx(ruled_out={"L"}), visible=False)
    assert (d["action"], d["target"]) == ("look", "R")


def test_all_places_empty_asks_user():
    d = PL.rule_decide(clear_belief(), ctx(ruled_out={"L", "R"}), visible=False)
    assert d["action"] == "ask"


def test_unresolved_goal_asks():
    d = PL.rule_decide(clear_belief(), ctx(obj=None, goal_text="bring me my medicine"), False)
    assert d["action"] == "ask"


def test_effective_probs_sum_to_one():
    p = PL.effective_probs(close_belief(), ctx(), False)
    assert sum(p.values()) == pytest.approx(1.0)


def test_decision_has_contract_fields():
    d = PL.rule_decide(clear_belief(), ctx(), False)
    for k in ("engine", "action", "target", "command", "why", "latency_ms"):
        assert k in d
    assert d["engine"] == "rule" and d["offline"] is False


# ---------------------------------------------------------------------------
# is_routine / when the LLM is called
# ---------------------------------------------------------------------------

def test_routine_clear_favourite():
    assert PL.is_routine(clear_belief(), ctx(), False)[0] is True


def test_not_routine_when_close():
    assert PL.is_routine(close_belief(), ctx(), False)[0] is False


def test_not_routine_after_empty_look():
    assert PL.is_routine(clear_belief(), ctx(ruled_out={"R"}), False)[0] is False


def test_auto_mode_skips_llm_for_routine_cases():
    c = FakeClient(GOOD_LOOK_R)
    d = planner(c).decide(clear_belief(), ctx(), False)
    assert c.calls == [] and d["engine"] == "rule" and d["offline"] is False


def test_rule_mode_never_calls_llm():
    c = FakeClient(GOOD_LOOK_R)
    planner(c, mode="rule").decide(close_belief(), ctx(), False)
    assert c.calls == []


def test_auto_mode_calls_llm_when_unclear():
    c = FakeClient(GOOD_LOOK_R)
    d = planner(c).decide(close_belief(), ctx(sensor_events=[(13.0, "L")]), False)
    assert len(c.calls) == 1
    assert d["engine"] == "llm" and d["target"] == "R" and d["offline"] is False
    assert d["model"] == MODELS["small"]


def test_llm_mode_calls_on_routine_case_but_not_when_visible():
    c = FakeClient(GOOD_LOOK_R)
    p = planner(c, mode="llm")
    p.decide(clear_belief(), ctx(), False)
    assert len(c.calls) == 1
    p.decide(clear_belief(), ctx(), True)
    assert len(c.calls) == 1


def test_nemotron_alias_means_llm():
    assert PL.Planner(mode="nemotron", client=FakeClient(), models=MODELS).mode == "llm"


def test_big_model_used_for_hard_case():
    c = FakeClient(GOOD_LOOK_R)
    b = close_belief()
    planner(c).decide(b, ctx(ruled_out={"L"}, sensor_events=[(13.0, "L")]), False)  # R left, but LLM asked
    assert c.calls[0]["model"] == MODELS["big"]


def test_prompt_does_not_leak_rule_answer():
    c = FakeClient(GOOD_LOOK_R)
    planner(c).decide(close_belief(), ctx(sensor_events=[(13.0, "L")]), False)
    user = c.calls[0]["messages"][1]["content"]
    assert "Estimated probability" in user
    assert "rule planner" not in user.lower() and "fly the wrist camera" not in user


# ---------------------------------------------------------------------------
# Fallback behaviour
# ---------------------------------------------------------------------------

def test_exception_falls_back_to_rule_and_flags_offline():
    d = planner(FakeClient(raises=ConnectionError("boom"))).decide(close_belief(), ctx(), False)
    assert d["engine"] == "rule" and d["offline"] is True
    assert "ConnectionError" in d["fallback_reason"]
    assert d["action"] == "look"


def test_timeout_falls_back_within_budget():
    p = planner(FakeClient(GOOD_LOOK_R, delay=1.0), timeout_s=0.2)
    t0 = time.perf_counter()
    d = p.decide(close_belief(), ctx(), False)
    assert time.perf_counter() - t0 < 0.8
    assert d["offline"] is True and "TimeoutError" in d["fallback_reason"]


@pytest.mark.parametrize("bad", [
    {"action": "dance", "target": "L", "command": "", "why": "x"},                 # unknown action
    {"action": "pick", "target": "bottle_blue", "command": "", "why": "x"},        # pick while hidden
    {"action": "look", "target": "M", "command": "", "why": "x"},                  # not a place
    {"action": "look", "target": "L", "command": "", "why": ""},                   # empty why
    {"action": "finish", "target": "", "command": "", "why": "x"},                 # finish before delivery
])
def test_invalid_llm_output_falls_back(bad):
    d = planner(FakeClient(bad)).decide(close_belief(), ctx(), False)
    assert d["engine"] == "rule" and d["offline"] is True


def test_llm_cannot_look_at_place_found_empty():
    bad = {"action": "look", "target": "R", "command": "", "why": "x"}
    d = planner(FakeClient(bad)).decide(close_belief(), ctx(ruled_out={"R"}), False)
    assert d["offline"] is True and d["target"] == "L"


def test_llm_pick_command_is_overridden_with_training_phrase():
    # visible case in llm mode is rule-only, so test the validator directly
    clean = PL._validate({"action": "pick", "target": "bottle_blue", "command": "grab the thing", "why": "Visible."},
                         ctx(), visible=True)
    assert clean["command"] == "pick up the blue bottle and place it in the tray"


def test_llm_json_in_content_is_accepted():
    c = FakeClient(content_only=json.dumps(GOOD_LOOK_R))
    d = planner(c).decide(close_belief(), ctx(), False)
    assert d["engine"] == "llm" and d["target"] == "R"


def test_missing_api_key_falls_back(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.setattr(PL, "_load_dotenv", lambda: None)
    p = PL.Planner(mode="auto")                 # real client path, no key
    d = p.decide(close_belief(), ctx(), False)
    assert d["offline"] is True and "NEBIUS_API_KEY" in d["fallback_reason"]


# ---------------------------------------------------------------------------
# Evidence helpers and stats
# ---------------------------------------------------------------------------

def test_note_look_result_empty_then_found():
    b, c = clear_belief(), ctx()
    PL.note_look_result(b, c, "L", found=False, now=33.0)
    assert c.ruled_out == {"L"}
    PL.note_look_result(b, c, "R", found=True, now=41.0)
    assert c.ruled_out == set() and b.place == "R" and b.conf == 1.0


def test_failed_grasp_drops_confidence():
    b = RB.Belief("bottle_blue", "L", 0.9, 0.0)
    PL.note_grasp_result(b, ctx(), ok=False, now=50.0)
    assert b.conf == pytest.approx(0.05)


def test_stats_count_calls_fallbacks_and_agreement():
    good = planner(FakeClient(GOOD_LOOK_R))
    b, c = close_belief(), ctx(sensor_events=[(13.0, "L")])
    good.decide(b, c, False)
    s = good.stats()
    assert s["llm_calls"] == 1 and s["llm_ok"] == 1 and s["fallbacks"] == 0
    assert s["agreement_rate"] == 1.0 and s["tokens"] == 123

    bad = planner(FakeClient(raises=RuntimeError("x")))
    bad.decide(close_belief(), ctx(), False)
    s = bad.stats()
    assert s["llm_calls"] == 1 and s["fallbacks"] == 1 and s["agreement_rate"] is None


def test_log_csv_written(tmp_path):
    p = planner(FakeClient(GOOD_LOOK_R))
    p.decide(close_belief(), ctx(), False)
    out = tmp_path / "planner_log.csv"
    p.write_log_csv(str(out))
    assert out.read_text().splitlines()[0].startswith("t,mode")
