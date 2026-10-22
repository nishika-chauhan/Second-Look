import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import eval as E
import planner as PL

def sc(initial="L", moved=False, sensor=False, delay=40.0):
    true = {"L": "R", "R": "L"}[initial] if moved else initial
    return {"eval_id": "x", "scenario": "S3", "seed": 1, "target": "bottle_blue", "delay_s": delay,
            "initial_place": initial, "moved": moved, "true_place": true, "sensor_fired": sensor}

rule = PL.Planner(mode="rule")

def test_p0_gives_up_when_object_moved():
    r = E.run_fixed(sc(moved=True), E.order_p0(sc(moved=True)))
    assert r["found"] is False and r["looks"] == 1

def test_sweep_always_finds_it():
    for s in (sc(moved=False), sc(moved=True), sc("R", True)):
        assert E.run_fixed(s, E.order_p1(s))["found"] is True

def test_rule_goes_straight_to_new_place_when_sensor_fired():
    r = E.run_planner(sc(moved=True, sensor=True, delay=40.0), rule)
    assert r["found"] and r["looks"] == 1

def test_rule_pays_one_extra_look_on_missed_move():
    r = E.run_planner(sc(moved=True, sensor=False, delay=40.0), rule)
    assert r["found"] and r["looks"] == 2

def test_false_alarm_costs_a_second_look():
    r = E.run_planner(sc(moved=False, sensor=True, delay=40.0), rule)
    assert r["found"] and r["looks"] == 2

def test_calm_case_one_look_and_time_budget():
    r = E.run_planner(sc(delay=10.0), rule)
    assert r["looks"] == 1 and r["t"] == 8.0 + E.PICK_COST_S

def test_timeline_matches_c_spec():
    d, t_sensor = E.timeline(sc(sensor=True, delay=40.0))
    assert d == 40.0 and t_sensor == 30.0
    assert E.timeline(sc(sensor=False))[1] is None
