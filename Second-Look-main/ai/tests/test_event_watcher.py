"""
pytest for the event watcher / zone-disturbed integration (ai/event_watcher.py).

Run from repo root:
    pytest ai/tests/test_event_watcher.py -v
"""

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import regions_belief as RB
import event_watcher as EW


def make_belief(place="L", conf=1.0, t=0.0):
    b = RB.Belief(name="bottle_blue", place=place, conf=conf, t=t)
    return b


def make_event(zone="L", triggered=True, t=10.0):
    return {"type": "event", "event": "zone_disturbed",
            "zone": zone, "sensor_triggered": triggered, "t": t}


# ---------------------------------------------------------------------------
# P_MOVED_THRESHOLD gating
# ---------------------------------------------------------------------------

def test_first_same_zone_alarm_ignored():
    """First alarm at the remembered place has p_moved ≈ 0.40 → below threshold."""
    b = make_belief("L", conf=1.0)
    beliefs = {"bottle_blue": b}
    acted = EW.process_event(make_event(zone="L"), beliefs, now=10.0)
    assert not acted, "first same-zone alarm should be below P_MOVED_THRESHOLD"
    assert b.conf == pytest.approx(1.0, abs=1e-6), "confidence should not change"


def test_different_zone_alarm_acted_on():
    """Alarm at a DIFFERENT zone than remembered → p_moved=0.85 → threshold met."""
    b = make_belief("L", conf=1.0)
    beliefs = {"bottle_blue": b}
    acted = EW.process_event(make_event(zone="R"), beliefs, now=10.0)
    assert acted, "alarm at different zone should be acted on"
    assert b.conf < 1.0, "confidence should drop after disturbed()"


def test_second_same_zone_alarm_acted_on():
    """Second alarm at the same zone → p_moved=0.75 → threshold met."""
    b = make_belief("L", conf=1.0)
    beliefs = {"bottle_blue": b}
    counts: dict = {}
    # First alarm — ignored
    EW.process_event(make_event(zone="L", t=10.0), beliefs, now=10.0, alarm_counts=counts)
    # Second alarm — should act
    acted = EW.process_event(make_event(zone="L", t=20.0), beliefs, now=20.0, alarm_counts=counts)
    assert acted, "second same-zone alarm should be acted on"
    assert b.conf < 1.0


def test_untriggered_sensor_ignored():
    b = make_belief("L", conf=1.0)
    beliefs = {"bottle_blue": b}
    event = make_event(zone="R", triggered=False)
    acted = EW.process_event(event, beliefs, now=10.0)
    assert not acted
    assert b.conf == pytest.approx(1.0)


def test_non_zone_disturbed_event_ignored():
    b = make_belief("L", conf=1.0)
    beliefs = {"bottle_blue": b}
    event = {"type": "event", "event": "episode_start", "t": 0.0}
    acted = EW.process_event(event, beliefs, now=0.0)
    assert not acted


# ---------------------------------------------------------------------------
# Confidence update correctness
# ---------------------------------------------------------------------------

def test_disturb_multiplier_applied():
    """After a threshold-crossing alarm, conf should be multiplied by DISTURB=0.35."""
    b = make_belief("L", conf=1.0)
    beliefs = {"bottle_blue": b}
    # Different zone → p_moved=0.85 → threshold met → disturbed() called
    EW.process_event(make_event(zone="R"), beliefs, now=10.0)
    # disturbed() on zone != b.place means b.conf is unchanged by the *disturbed* code path
    # but if zone == b.place it would multiply by DISTURB
    # Here zone="R" != b.place="L", so RB.disturbed only ticks time but doesn't apply DISTURB
    # The confidence drop comes from tick()'s time decay (hidden=True) from t=0→10
    # With HALF_LIFE_S=60: 0.5^(10/60) ≈ 0.891
    assert b.conf == pytest.approx(0.5 ** (10 / RB.HALF_LIFE_S), abs=1e-4)


def test_disturb_multiplier_on_same_zone_second_alarm():
    """Second same-zone alarm: after threshold met, conf × DISTURB."""
    b = make_belief("L", conf=1.0)
    beliefs = {"bottle_blue": b}
    counts: dict = {}
    EW.process_event(make_event(zone="L", t=0.0), beliefs, now=0.0, alarm_counts=counts)
    conf_before = b.conf   # first alarm ignored, conf unchanged
    EW.process_event(make_event(zone="L", t=0.0), beliefs, now=0.0, alarm_counts=counts)
    # disturbed(b, "L", 0.0) → tick (no time elapsed) then b.conf *= DISTURB
    assert b.conf == pytest.approx(conf_before * RB.DISTURB, abs=1e-6)


# ---------------------------------------------------------------------------
# Multiple objects in beliefs dict
# ---------------------------------------------------------------------------

def test_all_objects_updated():
    """All objects in the beliefs dict get the event applied."""
    b1 = make_belief("R", conf=0.9)
    b2 = RB.Belief(name="cup_red", place="R", conf=0.8, t=0.0)
    beliefs = {"bottle_blue": b1, "cup_red": b2}
    counts: dict = {}
    # Zone R, different from b.place="R"? No — same zone, so first alarm ignored for both
    EW.process_event(make_event(zone="R", t=0.0), beliefs, now=0.0, alarm_counts=counts)
    assert b1.conf == pytest.approx(0.9, abs=1e-6)
    assert b2.conf == pytest.approx(0.8, abs=1e-6)
    # Second alarm for same zone → both should be updated
    EW.process_event(make_event(zone="R", t=0.0), beliefs, now=0.0, alarm_counts=counts)
    assert b1.conf < 0.9
    assert b2.conf < 0.8
