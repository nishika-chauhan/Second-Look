"""Generate 30 real wrist-camera PNG frames (224x224) from SecondLookEnv for Teammate B.

Mixed evenly across 6 conditions (5 frames each):
1. cup_red: Hovering above red cup (with random offsets and domain randomization).
2. bottle_blue: Hovering above blue bottle.
3. box_green: Hovering above green box.
4. empty_table: Hovering above an empty table region (only checkerboard pattern visible).
5. look_L: Hovering at the standard look_L search pose above the left screen.
6. look_R: Hovering at the standard look_R search pose above the right screen.

Includes camera calibration metadata (height, FOV, 3D world positions).
"""

import json
import os
import sys
from pathlib import Path

import cv2
import mujoco
import numpy as np

# Ensure sim/ is on sys.path
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from world import OBJECTS, SecondLookEnv, Z_SAFE


def generate_samples(output_dir: Path, base_seed: int = 70000):
    output_dir.mkdir(parents=True, exist_ok=True)
    env = SecondLookEnv(render=True, img=224, randomize=True)
    cam_id = mujoco.mj_name2id(env.m, mujoco.mjtObj.mjOBJ_CAMERA, "wrist")

    samples_meta = []
    sample_idx = 0

    def record_sample(category: str, seed: int, filename: str, extra_info: dict = None):
        nonlocal sample_idx
        obs = env.obs()
        wrist_rgb = obs["wrist"]  # shape (224, 224, 3), RGB uint8
        wrist_bgr = cv2.cvtColor(wrist_rgb, cv2.COLOR_RGB2BGR)

        img_path = output_dir / filename
        cv2.imwrite(str(img_path), wrist_bgr)

        cam_pos = env.d.cam_xpos[cam_id].copy().tolist()
        grip_pos = env.grip_pos().tolist()
        cam_height = cam_pos[2]  # Table surface is at z=0.00 m

        all_obj_positions = {obj: env.obj_pos(obj).tolist() for obj in OBJECTS}

        meta = {
            "index": sample_idx,
            "filename": filename,
            "category": category,
            "seed": seed,
            "image_size": [224, 224],
            "fovy_deg": 60.0,
            "cam_world_pos": [round(v, 4) for v in cam_pos],
            "grip_world_pos": [round(v, 4) for v in grip_pos],
            "cam_height_above_table_m": round(cam_height, 4),
            "object_world_positions": {k: [round(v, 4) for v in pos] for k, pos in all_obj_positions.items()},
        }
        if extra_info:
            meta.update(extra_info)

        samples_meta.append(meta)
        sample_idx += 1
        print(f"[{sample_idx:02d}/30] Saved {filename} ({category})")

    # 1. 5 samples for each of the 3 objects (cup_red, bottle_blue, box_green)
    for obj in OBJECTS:
        for i in range(5):
            seed = base_seed + len(samples_meta)
            rng = np.random.default_rng(seed)
            env.reset(seed=seed, target=obj, start="home", randomize=True)

            # Move robot above the object with slight positional jitter
            p = env.obj_pos(obj)
            jit = rng.uniform(-0.02, 0.02, 2)
            z_hover = Z_SAFE + rng.uniform(-0.02, 0.02)
            env.set_gantry([p[0] + jit[0], p[1] + jit[1], z_hover])
            mujoco.mj_forward(env.m, env.d)

            filename = f"wrist_{obj}_{i:02d}.png"
            record_sample(
                category=obj,
                seed=seed,
                filename=filename,
                extra_info={"target": obj, "target_pos": [round(v, 4) for v in p.tolist()]},
            )

    # 2. 5 samples for empty table (no objects within camera FOV)
    for i in range(5):
        seed = base_seed + len(samples_meta)
        rng = np.random.default_rng(seed)
        env.reset(seed=seed, start="home", randomize=True)

        # Place robot over clean table area (e.g. y around -0.15 to -0.05, away from objects)
        # Search for an xy on table where distance to all 3 objects is > 0.18 m
        found_empty = False
        for _ in range(50):
            cand_x = rng.uniform(-0.35, 0.35)
            cand_y = rng.uniform(-0.18, 0.0)
            cand_pos = np.array([cand_x, cand_y])
            if all(np.linalg.norm(cand_pos - env.obj_pos(o)[:2]) > 0.18 for o in OBJECTS):
                found_empty = True
                break

        if not found_empty:
            cand_x, cand_y = 0.0, -0.05

        z_hover = Z_SAFE + rng.uniform(-0.02, 0.02)
        env.set_gantry([cand_x, cand_y, z_hover])
        mujoco.mj_forward(env.m, env.d)

        filename = f"wrist_empty_table_{i:02d}.png"
        record_sample(category="empty_table", seed=seed, filename=filename)

    # 3. 5 samples for look_L pose (hovering above Left screen)
    for i in range(5):
        seed = base_seed + len(samples_meta)
        env.reset(seed=seed, start="look_L", randomize=True)
        # Robot is automatically positioned at look_L in reset()
        filename = f"wrist_look_L_{i:02d}.png"
        record_sample(category="look_L", seed=seed, filename=filename)

    # 4. 5 samples for look_R pose (hovering above Right screen)
    for i in range(5):
        seed = base_seed + len(samples_meta)
        env.reset(seed=seed, start="look_R", randomize=True)
        # Robot is automatically positioned at look_R in reset()
        filename = f"wrist_look_R_{i:02d}.png"
        record_sample(category="look_R", seed=seed, filename=filename)

    # Save metadata.json
    meta_path = output_dir / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(samples_meta, f, indent=2)

    print(f"\nSuccessfully generated {len(samples_meta)} wrist images in {output_dir}")
    print(f"Metadata written to {meta_path}")


if __name__ == "__main__":
    out_dir = REPO_ROOT / "out" / "wrist_detector_samples"
    generate_samples(out_dir)
