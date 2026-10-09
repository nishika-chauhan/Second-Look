"""Dataset generator for recovery demonstrations (v1b stretch dataset).

Generates 200 episodes where the robot experiences a grasp failure (gripper closes
on nothing, grip drops to 0.0), detects the slip, re-opens the gripper, ascends to
safe height, realigns, executes a secure grasp, and delivers the object to the tray.

Target mix: balanced across cup_red, bottle_blue, box_green and start poses.
Output: out/second_look_v1b (standard LeRobot v2.0 dataset format).
"""
import argparse
import os
import shutil
import time
import numpy as np

from world import SecondLookEnv, OBJECTS, REST_Z, TRAY_XY, Z_SAFE, MAX_STEP
from dataset_backend import LeRobotDataset

TASK_TEXT = {
    "cup_red": "pick up the red cup and place it in the tray",
    "bottle_blue": "pick up the blue bottle and place it in the tray",
    "box_green": "pick up the green box and place it in the tray",
}


def run_recovery_expert(env, target, rng, record=True):
    """Executes a demonstration with an initial grasp failure followed by autonomous recovery.

    Returns:
        (success, frames) where frames is a list of (obs, action).
    """
    frames = []

    def act(a):
        if record:
            frames.append((env.obs(), np.array(a, dtype=np.float32)))
        env.step(a)

    def move(wp, g, speed, tol=0.006, max_steps=90):
        for _ in range(max_steps):
            cur = env.grip_pos()
            err = np.asarray(wp, float) - cur
            if np.linalg.norm(err) < tol:
                return
            act([*(cur + np.clip(err, -MAX_STEP * speed, MAX_STEP * speed)), g])

    def hold(pos, g, n):
        for _ in range(n):
            act([*pos, g])

    p = env.obj_pos(target)
    speed = rng.uniform(0.7, 1.0)
    zs = Z_SAFE + rng.uniform(-0.02, 0.02)
    grasp_z = REST_Z[target] + 0.03

    # Phase 1: Approach with deliberate slight lateral offset (5 cm) to cause slip
    offset_x = float(rng.choice([-0.05, 0.05]))
    move([p[0] + offset_x, p[1], zs], 1.0, speed)
    move([p[0] + offset_x, p[1], grasp_z], 1.0, speed)

    # Phase 2: Close gripper on empty space -> grip drops to 0.0
    cur = env.grip_pos()
    hold(cur, 0.0, 5)

    if env.attached is not None or env.grip > 0.15:
        # Unexpected attachment on slip attempt, abort episode
        return False, []

    # Phase 3: Autonomous Recovery
    # Step A: Re-open gripper
    hold(cur, 1.0, 4)

    # Step B: Retract to safe observation height
    move([cur[0], cur[1], zs], 1.0, speed)

    # Step C: Re-align precisely above target center
    jit = rng.normal(0, 0.002, 2)
    move([p[0] + jit[0], p[1] + jit[1], zs], 1.0, speed)

    # Step D: Descend onto object
    move([p[0] + jit[0], p[1] + jit[1], grasp_z], 1.0, speed)

    # Step E: Close gripper securely onto target
    cur = env.grip_pos()
    hold(cur, 0.0, 5)

    if env.attached != target:
        # Failed second grasp, abort episode
        return False, []

    # Step F: Lift object
    move([cur[0], cur[1], zs], 0.0, speed)

    # Step G: Transport to tray
    move([TRAY_XY[0] + jit[0], TRAY_XY[1] + jit[1], zs], 0.0, speed)

    # Step H: Lower to tray
    move([TRAY_XY[0] + jit[0], TRAY_XY[1] + jit[1], 0.07], 0.0, speed)

    # Step I: Release object into tray
    cur = env.grip_pos()
    hold(cur, 1.0, 4)

    # Step J: Retract gantry
    move([cur[0], cur[1], zs], 1.0, speed)

    return env.in_tray(target), frames


def make_recovery_dataset(episodes=200, seed0=50000, out_dir="out/second_look_v1b", img_size=224):
    """Generate 200 recovery demonstration episodes."""
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)

    env = SecondLookEnv(render=True, img=img_size, randomize=True)
    img_feature = {"dtype": "video", "shape": (img_size, img_size, 3), "names": ["height", "width", "channels"]}
    features = {
        "observation.images.front": img_feature,
        "observation.images.wrist": img_feature,
        "observation.state": {"dtype": "float32", "shape": (4,), "names": ["x", "y", "z", "gripper"]},
        "action": {"dtype": "float32", "shape": (4,), "names": ["x", "y", "z", "gripper"]},
    }

    writer = LeRobotDataset.create(
        repo_id="local/second_look_v1b",
        fps=10,
        features=features,
        root=out_dir,
        robot_type="gantry",
        use_videos=True,
    )

    kept, tries, frames_total, t0 = 0, 0, 0, time.time()
    print(f"Generating {episodes} recovery episodes to {out_dir} starting with seed {seed0}...")

    while kept < episodes:
        seed = seed0 + tries
        tries += 1
        rng = np.random.default_rng(20_000 + seed)

        # Balanced target and start mode
        target = OBJECTS[seed % 3]
        start = ["home", "look_L", "look_R"][(seed // 3) % 3]

        env.reset(seed=seed, target=target, start=start)

        ok, frames = run_recovery_expert(env, target, rng, record=True)
        if not ok or len(frames) == 0:
            continue

        for obs, action in frames:
            writer.add_frame({
                "observation.images.front": obs["front"],
                "observation.images.wrist": obs["wrist"],
                "observation.state": obs["state"],
                "action": action,
                "task": TASK_TEXT[target]
            })

        writer.save_episode(seed=seed, target=target, start=start)
        kept += 1
        frames_total += len(frames)

        if kept % 25 == 0 or kept == episodes:
            elapsed = time.time() - t0
            fps_gen = frames_total / max(elapsed, 0.001)
            print(f"  [{kept}/{episodes}] episodes ({frames_total} frames, {elapsed:.1f}s, {fps_gen:.1f} fps)")

    writer.finalize()
    total_time = time.time() - t0
    print(f"\n[DONE] Kept {kept} of {tries} tries, {frames_total} total frames in {total_time:.1f}s -> {out_dir}")
    return out_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate recovery demonstration dataset (v1b).")
    parser.add_argument("--episodes", type=int, default=200, help="Number of recovery episodes.")
    parser.add_argument("--seed0", type=int, default=50000, help="Starting PRNG seed.")
    parser.add_argument("--out", type=str, default="out/second_look_v1b", help="Output directory path.")
    parser.add_argument("--img", type=int, default=224, help="Image resolution.")
    args = parser.parse_args()

    make_recovery_dataset(episodes=args.episodes, seed0=args.seed0, out_dir=args.out, img_size=args.img)
