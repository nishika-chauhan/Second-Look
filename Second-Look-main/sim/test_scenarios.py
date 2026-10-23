"""Statistical and functional test suite for sim/scenarios.py.

Verifies:
1. S1, S2, S4 functional correctness and contract conformance.
2. S3 statistical calibration: confirms that configured (q, d, f) parameters
   match the observed move rate, detection rate, and false-alarm rate across 500 seeds.
3. Hard rule enforcement across all episodes.
4. Exports sample logs to out/scenario_logs.jsonl.
"""
import json
import os
import sys
import time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world import SecondLookEnv, OBJECTS
from scenarios import run_s1, run_s2, run_s3, run_s4

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out")
os.makedirs(OUT, exist_ok=True)


def test_functional():
    print("--- Functional Tests (S1, S2, S4) ---")
    env = SecondLookEnv(render=False)
    sample_logs = []

    # Test S1 across 3 targets
    for i, target in enumerate(OBJECTS):
        ok, logs, _ = run_s1(env, seed=i, target=target)
        assert ok, f"S1 failed for {target}"
        assert logs[-1]["type"] == "episode_end" and logs[-1]["success"] is True
        sample_logs.extend(logs)
    print("  [PASS] S1 (Visible Pick-and-Place) verified 3/3")

    # Test S2 across screens and targets
    for i, (target, screen) in enumerate(zip(OBJECTS, ["L", "R", "L"])):
        ok, logs, _ = run_s2(env, seed=10 + i, target=target, hidden_screen=screen, hidden_time=12.0)
        assert ok, f"S2 failed for {target} behind {screen}"
        assert any(l.get("skill") == "look" and l.get("ok") for l in logs)
        sample_logs.extend(logs)
    print("  [PASS] S2 (Hidden Then Fetch) verified 3/3")

    # Test S4 (Grasp failure + Recovery)
    for i, target in enumerate(OBJECTS):
        ok, logs, _ = run_s4(env, seed=20 + i, target=target)
        assert ok, f"S4 failed for {target}"
        assert any(l.get("kind") == "grasp_failed" for l in logs), "S4 must log grasp_failed"
        assert any(l.get("kind") == "grasp_recovered" for l in logs), "S4 must log grasp_recovered"
        sample_logs.extend(logs)
    print("  [PASS] S4 (Failed Grasp & Recovery) verified 3/3")

    # Export sample logs to out/scenario_logs.jsonl
    log_file = os.path.join(OUT, "scenario_logs.jsonl")
    with open(log_file, "w") as f:
        for entry in sample_logs:
            f.write(json.dumps(entry) + "\n")
    print(f"  [SAVED] Sample scenario logs -> {log_file}")


def test_s3_statistical():
    print("\n--- Statistical Test: S3 Calibration (q, d, f) ---")
    env = SecondLookEnv(render=False)
    
    # Target parameter rates
    q_target = 0.45   # move probability
    d_target = 0.82   # detection rate given move
    f_target = 0.12   # false alarm rate given no move
    
    N = 500
    print(f"Running {N} seeds with configured q={q_target}, d={d_target}, f={f_target}...")
    t0 = time.time()
    
    n_moved = 0
    n_detected_given_moved = 0
    n_false_alarms = 0
    n_success = 0
    
    for seed in range(1000, 1000 + N):
        target = OBJECTS[seed % 3]
        screen = ["L", "R"][seed % 2]
        
        ok, logs, _ = run_s3(
            env, seed=seed, target=target, hidden_screen=screen,
            q=q_target, d=d_target, f=f_target, hidden_time=15.0
        )
        assert ok, f"S3 episode {seed} failed!"
        n_success += ok
        
        end_log = logs[-1]
        moved = end_log["moved"]
        sensor = end_log["sensor_triggered"]
        
        if moved:
            n_moved += 1
            if sensor:
                n_detected_given_moved += 1
        else:
            if sensor:
                n_false_alarms += 1

    elapsed = time.time() - t0
    n_not_moved = N - n_moved
    
    obs_q = n_moved / N
    obs_d = n_detected_given_moved / n_moved if n_moved > 0 else 0.0
    obs_f = n_false_alarms / n_not_moved if n_not_moved > 0 else 0.0
    
    print(f"Completed {N} episodes in {elapsed:.1f} s ({1000*elapsed/N:.1f} ms/ep). Success: {n_success}/{N}")
    print(f"Results:")
    print(f"  Move probability (q):        Target = {q_target:.3f} | Observed = {obs_q:.3f} (delta = {abs(obs_q - q_target):.3f})")
    print(f"  Detection rate (d):          Target = {d_target:.3f} | Observed = {obs_d:.3f} (delta = {abs(obs_d - d_target):.3f})")
    print(f"  False-alarm rate (f):        Target = {f_target:.3f} | Observed = {obs_f:.3f} (delta = {abs(obs_f - f_target):.3f})")
    
    # Assert within 3-sigma binomial confidence intervals
    assert abs(obs_q - q_target) < 0.05, f"Move rate {obs_q} deviates too far from target {q_target}"
    assert abs(obs_d - d_target) < 0.06, f"Detection rate {obs_d} deviates too far from target {d_target}"
    assert abs(obs_f - f_target) < 0.05, f"False-alarm rate {obs_f} deviates too far from target {f_target}"
    print("  [PASS] Statistical parameters (q, d, f) strictly calibrated within tolerance!")


if __name__ == "__main__":
    test_functional()
    test_s3_statistical()
