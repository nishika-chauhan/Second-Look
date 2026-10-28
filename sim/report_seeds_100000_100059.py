"""Generate Tier 2 expert sweep and initial-position / visibility report for seeds 100000–100059.

Produces:
1. out/expert_seeds_100000_100059.csv
2. out/expert_seeds_100000_100059.json
"""

import csv
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from sim.expert import TASK_TEXT, run_expert
from sim.world import OBJECTS, SecondLookEnv

STARTS = ["home", "look_L", "look_R"]


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / d
    import math

    half = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def determine_hiding_place(env, obj_name: str) -> str:
    pos = env.obj_pos(obj_name)
    # Check screen L and screen R distance
    cL = env.hide_center("L")
    cR = env.hide_center("R")
    dL = np.linalg.norm(pos[:2] - cL)
    dR = np.linalg.norm(pos[:2] - cR)
    if not env.front_visible(obj_name):
        return "L" if dL < dR else "R"
    return "OPEN"


def run_sweep(seed0: int = 100000, num_episodes: int = 60):
    out_dir = REPO / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"======================================================================")
    print(f"TIER 2 EXPERT SWEEP & VISIBILITY REPORT: SEEDS {seed0}..{seed0 + num_episodes - 1}")
    print(f"======================================================================\n")

    env = SecondLookEnv(render=True, img=224, randomize=True)

    records = []
    t_start_total = time.time()

    for idx in range(num_episodes):
        seed = seed0 + idx
        target = OBJECTS[seed % 3]
        start = STARTS[(seed // 3) % 3]
        task = TASK_TEXT[target]

        t0 = time.time()
        # Reset environment with specified seed and start condition
        env.reset(seed=seed, target=target, start=start, randomize=True)

        # Record initial positions & visibility BEFORE any actions
        init_positions = {obj: [round(float(v), 4) for v in env.obj_pos(obj)] for obj in OBJECTS}
        front_vis = {obj: bool(env.front_visible(obj)) for obj in OBJECTS}
        wrist_vis = {obj: bool(env.wrist_sees(obj)) for obj in OBJECTS}
        target_place = determine_hiding_place(env, target)
        init_grip = [round(float(v), 4) for v in env.grip_pos()]

        # Run scripted expert policy
        rng = np.random.default_rng(10_000 + seed)
        ok, frames = run_expert(env, target, rng, record=True)
        wall_s = round(time.time() - t0, 3)

        rec = {
            "seed": seed,
            "target": target,
            "start_pose": start,
            "target_initial_place": target_place,
            "target_front_visible": front_vis[target],
            "target_wrist_visible": wrist_vis[target],
            "cup_red_pos": init_positions["cup_red"],
            "bottle_blue_pos": init_positions["bottle_blue"],
            "box_green_pos": init_positions["box_green"],
            "front_visible_cup_red": front_vis["cup_red"],
            "front_visible_bottle_blue": front_vis["bottle_blue"],
            "front_visible_box_green": front_vis["box_green"],
            "init_grip_pos": init_grip,
            "success": int(bool(ok)),
            "steps": len(frames),
            "sim_time_s": round(len(frames) * 0.1, 2),
            "wall_time_s": wall_s,
        }
        records.append(rec)

        status_str = "PASS" if ok else "FAIL"
        vis_str = "VISIBLE" if front_vis[target] else f"HIDDEN ({target_place})"
        print(
            f"[{idx+1:02d}/{num_episodes}] Seed {seed} | Target: {target:<11} | Start: {start:<6} | "
            f"Front: {vis_str:<12} | Steps: {len(frames):>3} ({rec['sim_time_s']:>4.1f}s) | "
            f"{status_str} ({wall_s:.2f}s)"
        )

    total_wall_s = round(time.time() - t_start_total, 2)
    n_success = sum(r["success"] for r in records)
    ci_lo, ci_hi = wilson_ci(n_success, num_episodes)

    # Save CSV
    csv_path = out_dir / f"expert_seeds_{seed0}_{seed0 + num_episodes - 1}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = list(records[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    # Save JSON
    json_path = out_dir / f"expert_seeds_{seed0}_{seed0 + num_episodes - 1}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "seed_range": [seed0, seed0 + num_episodes - 1],
                "episodes": num_episodes,
                "total_success": n_success,
                "success_rate": round(n_success / num_episodes, 4),
                "wilson_95_ci": [round(ci_lo, 4), round(ci_hi, 4)],
                "total_wall_time_s": total_wall_s,
                "records": records,
            },
            f,
            indent=2,
        )

    print(f"\n======================================================================")
    print(f"SUMMARY STATISTICS FOR SEEDS {seed0}..{seed0 + num_episodes - 1}")
    print(f"======================================================================")
    print(f"Total Episodes:        {num_episodes}")
    print(f"Expert Success:        {n_success}/{num_episodes} ({n_success / num_episodes:.1%})")
    print(f"95% Wilson Score CI:   [{ci_lo:.1%}, {ci_hi:.1%}]")
    print(f"Total Execution Time:  {total_wall_s} s (mean {total_wall_s / num_episodes:.2f} s/ep)")
    steps_list = [r["steps"] for r in records]
    print(
        f"Control Steps:         Mean {np.mean(steps_list):.1f} | Min {min(steps_list)} | Max {max(steps_list)}"
    )

    print(f"\nBreakdown by Target Object:")
    for obj in OBJECTS:
        sub = [r for r in records if r["target"] == obj]
        k = sum(r["success"] for r in sub)
        print(f"  {obj:<12}: {k}/{len(sub)} = {k / len(sub):.1%}")

    print(f"\nBreakdown by Start Pose:")
    for st in STARTS:
        sub = [r for r in records if r["start_pose"] == st]
        k = sum(r["success"] for r in sub)
        print(f"  {st:<12}: {k}/{len(sub)} = {k / len(sub):.1%}")

    print(f"\nBreakdown by Target Front Visibility:")
    vis_count = sum(1 for r in records if r["target_front_visible"])
    hid_L_count = sum(1 for r in records if not r["target_front_visible"] and r["target_initial_place"] == "L")
    hid_R_count = sum(1 for r in records if not r["target_front_visible"] and r["target_initial_place"] == "R")
    print(f"  Initially Visible from Front: {vis_count}/{num_episodes} ({vis_count/num_episodes:.1%})")
    print(f"  Initially Hidden Behind Screen L: {hid_L_count}/{num_episodes} ({hid_L_count/num_episodes:.1%})")
    print(f"  Initially Hidden Behind Screen R: {hid_R_count}/{num_episodes} ({hid_R_count/num_episodes:.1%})")

    print(f"\nArtifacts saved:")
    print(f"  - {csv_path}")
    print(f"  - {json_path}")


if __name__ == "__main__":
    run_sweep(seed0=100000, num_episodes=60)
