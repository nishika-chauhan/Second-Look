"""
pytest for the belief/search-order module (role B, Week 1 deliverable).

Targets ai/regions_belief.py -- the multi-hiding-place model (place_probs,
search_order) described in the team plan's Part 6.2. This repo also has
ai/belief.py, a different, single-object relook/act model with its own
__main__ demo (that's the one the Week 1 checklist's "python ai/belief.py"
line runs) -- it is NOT what this file tests, and the two aren't
interchangeable: belief.py has no place_probs/search_order, and its
tick() takes no `hidden` argument.

ai/toy_check.py already proves the 20,000-episode policy numbers from the
plan's Part 1.1 (81.8% / 100% / 100%). This file covers the smaller unit
claims underneath that: does confidence actually decay the way the plan
says, does a sensor event disturb it correctly, does the probability
renormalize right after a place is ruled out, and does search_order pick
the cheaper-probability-per-second place first.

It also reproduces the plan's own worked example from Part 1.1 as an
exact regression test (bottle at LEFT, hidden 25s, half-life 60s):
confidence 0.75, P(left)/P(right) = 0.86/0.14 with no sensor evidence,
and 0.42/0.58 once the touch sensor fires -- so a change that breaks
those numbers fails loudly here, not just in the doc.

Run from the repo root:
    pip install pytest
    pytest ai/tests/test_belief.py -v
"""

import math
import os
import sys
from types import SimpleNamespace

# ai/regions_belief.py has no package __init__.py, so pytest won't put it
# on sys.path by default from a subdirectory like ai/tests/. Add ai/
# itself (the parent of this file's directory) so `import regions_belief`
# resolves the same way it does for the existing test_regions_belief.py.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import regions_belief as B  # noqa: E402


def make_belief(place, conf, t=0.0):
    """Belief objects only need attribute access (.place/.conf/.t), so a
    SimpleNamespace works regardless of the real Belief dataclass's other
    fields (it also has `name`, unused by these functions)."""
    return SimpleNamespace(place=place, conf=conf, t=t)


# --------------------------------------------------------------------
# tick(): confidence decay while hidden
# --------------------------------------------------------------------

def test_tick_no_decay_when_visible():
    b = make_belief("L", 1.0, t=0.0)
    B.tick(b, now=30.0, hidden=False)
    assert b.conf == 1.0, "confidence must not fade while the object is not hidden"
    assert b.t == 30.0, "timestamp should still advance"


def test_tick_half_life_decay():
    b = make_belief("L", 1.0, t=0.0)
    B.tick(b, now=B.HALF_LIFE_S, hidden=True)
    assert b.conf == pytest.approx(0.5, abs=1e-6), (
        "after exactly one half-life hidden, confidence should drop to ~0.5"
    )


def test_tick_two_half_lives():
    b = make_belief("L", 1.0, t=0.0)
    B.tick(b, now=2 * B.HALF_LIFE_S, hidden=True)
    assert b.conf == pytest.approx(0.25, abs=1e-6), (
        "after two half-lives hidden, confidence should drop to ~0.25"
    )


def test_tick_is_incremental():
    """Calling tick repeatedly in small steps should match one big jump,
    since the episode runner ticks every sim step, not once per episode."""
    b_stepped = make_belief("L", 1.0, t=0.0)
    for now in (10, 20, 30, 40, 50, 60):
        B.tick(b_stepped, now=now, hidden=True)

    b_direct = make_belief("L", 1.0, t=0.0)
    B.tick(b_direct, now=60, hidden=True)

    assert b_stepped.conf == pytest.approx(b_direct.conf, abs=1e-6)


# --------------------------------------------------------------------
# place_probs(): visible case, renormalization, sensor disturbance
# --------------------------------------------------------------------

def test_place_probs_visible_returns_open():
    b = make_belief("L", 0.9, t=0.0)
    assert B.place_probs(b, visible_in_front=True) == {"OPEN": 1.0}


def test_place_probs_sums_to_one():
    for conf in (0.0, 0.25, 0.5, 0.75, 1.0):
        b = make_belief("L", conf, t=0.0)
        probs = B.place_probs(b, visible_in_front=False)
        assert math.isclose(sum(probs.values()), 1.0, abs_tol=1e-9), (
            f"probabilities must renormalize to 1.0 at confidence={conf}"
        )


def test_place_probs_zero_confidence_rules_out_remembered_place():
    """conf is 'how sure we are it's still at `place`', not a generic
    uncertainty knob -- p[place] is set directly to conf (not folded into
    the spread), so conf=0 means the remembered place gets probability
    0 and everything else absorbs it. With only one other hiding place,
    that other place gets probability 1.0."""
    b = make_belief("L", 0.0, t=0.0)
    probs = B.place_probs(b, visible_in_front=False)
    assert probs["L"] == pytest.approx(0.0, abs=1e-9)
    assert probs["R"] == pytest.approx(1.0, abs=1e-9)


def test_place_probs_is_not_linear_in_confidence():
    """Known non-linearity: the '+1' in spread = (1-conf)/(len(others)+1)
    reserves weight as if there were one more, unlisted hiding place.
    With only two real places, that means conf=0.5 does NOT produce a
    50/50 split -- the remembered place still comes out ahead 2:1. True
    parity needs conf=1/3. This isn't a bug, but it means 'confidence'
    as displayed on the dashboard isn't the same number the planner
    treats as probability -- worth knowing before tuning HALF_LIFE_S
    against a target probability."""
    b = make_belief("L", 0.5, t=0.0)
    probs = B.place_probs(b, visible_in_front=False)
    assert probs["L"] == pytest.approx(2 / 3, abs=0.01)
    assert probs["R"] == pytest.approx(1 / 3, abs=0.01)

    b_tied = make_belief("L", 1 / 3, t=0.0)
    probs_tied = B.place_probs(b_tied, visible_in_front=False)
    assert probs_tied["L"] == pytest.approx(0.5, abs=0.01)
    assert probs_tied["R"] == pytest.approx(0.5, abs=0.01)


def test_place_probs_matches_doc_worked_example_no_sensor():
    """Reproduces Part 1.1 of the team plan exactly: bottle at LEFT,
    hidden 25s, half-life 60s -> confidence 0.75 -> P(left)/P(right)
    should be 0.86 / 0.14."""
    b = make_belief("L", 0.75, t=0.0)
    probs = B.place_probs(b, visible_in_front=False)
    assert probs["L"] == pytest.approx(0.857, abs=0.01)
    assert probs["R"] == pytest.approx(0.143, abs=0.01)


def test_place_probs_matches_doc_worked_example_sensor_fired():
    """Same scenario, but the touch sensor under the left screen just
    fired: confidence x0.35 = 0.2625 -> P(left)/P(right) should flip
    to roughly 0.42 / 0.58 per the doc."""
    b = make_belief("L", 0.75 * B.DISTURB, t=0.0)
    probs = B.place_probs(b, visible_in_front=False)
    assert probs["L"] == pytest.approx(0.42, abs=0.01)
    assert probs["R"] == pytest.approx(0.58, abs=0.01)


# --------------------------------------------------------------------
# search_order(): picks the higher-probability-per-second place first
# --------------------------------------------------------------------

def test_search_order_prefers_remembered_place_with_no_evidence():
    b = make_belief("L", 0.75, t=0.0)
    order = B.search_order(b, visible_in_front=False)
    assert order == ["L", "R"], "with no disturbing evidence, check the remembered place first"


def test_search_order_flips_after_sensor_fires():
    b = make_belief("L", 0.75 * B.DISTURB, t=0.0)
    order = B.search_order(b, visible_in_front=False)
    assert order == ["R", "L"], (
        "once the sensor disturbs the remembered place enough, memory is "
        "probably stale -- the other place should be checked first"
    )


def test_search_order_cheaper_place_wins_ties():
    """If both places are equally likely but one costs less time to look
    at, the cheaper one should be searched first. True parity between two
    hiding places happens at conf=1/3, not 0.5 -- see
    test_place_probs_is_not_linear_in_confidence for why."""
    b = make_belief("L", 1 / 3, t=0.0)
    original_costs = dict(B.LOOK_COST_S)
    try:
        B.LOOK_COST_S["L"] = 8.0
        B.LOOK_COST_S["R"] = 4.0  # R is cheaper to check
        order = B.search_order(b, visible_in_front=False)
        assert order[0] == "R", "equal probability should break the tie toward the cheaper look"
    finally:
        B.LOOK_COST_S.clear()
        B.LOOK_COST_S.update(original_costs)