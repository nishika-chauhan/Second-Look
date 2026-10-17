"""
pytest for ai/event_watcher.py. One alarm at the remembered place cuts confidence
by DISTURB, exactly as in plan Part 6.1 / the worked example in Part 1.1.

    pytest ai/tests/test_event_watcher.py -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import regions_belief as RB
import event_watcher as EW


def belief(place="L", conf=1.0, t=0.0, name="bottle_blue"):
    return RB.Belief(name=name, place=place, conf=conf, t=t)


def alarm(zone="L", t=10.0, triggered=True):
    return {"type": "event", "event": "zone_disturbed", "zone": zone,
            "sensor_triggered": triggered, "t": t}


def test_single_alarm_at_remembered_place_cuts_confidence():
    b = belief("L", conf=1.0, t=10.0)
    assert EW.process_event(alarm("L", 10.0), {"o": b}, now=10.0) is True
    assert b.conf == pytest.approx(RB.DISTURB)


def test_alarm_at_other_place_only_advances_clock():
    b = belief("L", conf=1.0, t=0.0)
    cut = EW.process_event(alarm("R", 10.0), {"o": b}, now=10.0)
    assert cut is False
    assert b.conf == pytest.approx(0.5 ** (10.0 / RB.HALF_LIFE_S))   # decay only
    assert b.t == 10.0


def test_untriggered_sensor_ignored():
    b = belief("L")
    assert EW.process_event(alarm("L", triggered=False), {"o": b}, now=10.0) is False
    assert b.conf == 1.0 and b.t == 0.0


def test_other_event_types_ignored():
    b = belief("L")
    assert EW.process_event({"type": "event", "event": "episode_start", "t": 0}, {"o": b}, 0.0) is False
    assert EW.process_event({"type": "observation"}, {"o": b}, 0.0) is False
    assert b.conf == 1.0


def test_repeated_alarms_compound():
    b = belief("L", conf=1.0, t=0.0)
    EW.process_event(alarm("L", 0.0), {"o": b}, now=0.0)
    EW.process_event(alarm("L", 0.0), {"o": b}, now=0.0)
    assert b.conf == pytest.approx(RB.DISTURB ** 2)


def test_every_belief_at_that_place_is_cut():
    a = belief("R", 0.9, name="cup_red")
    c = belief("L", 0.8, name="box_green")
    EW.process_event(alarm("R", 0.0), {"cup_red": a, "box_green": c}, now=0.0)
    assert a.conf == pytest.approx(0.9 * RB.DISTURB)
    assert c.conf == pytest.approx(0.8)


def test_plan_worked_example_order_flips_after_alarm():
    """Plan 1.1: hidden 25 s -> conf 0.75; sensor fires -> 0.2625; P(L)/P(R) = 0.42/0.58."""
    b = belief("L", conf=0.75, t=25.0)
    assert RB.search_order(b, False)[0] == "L"
    EW.process_event(alarm("L", 25.0), {"o": b}, now=25.0)
    assert b.conf == pytest.approx(0.2625, abs=1e-4)
    p = RB.place_probs(b, False)
    assert p["L"] == pytest.approx(0.42, abs=0.01) and p["R"] == pytest.approx(0.58, abs=0.01)
    assert RB.search_order(b, False)[0] == "R"
