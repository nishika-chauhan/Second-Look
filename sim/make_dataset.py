"""Generate a LeRobot-format dataset of scripted pick-and-place demos (tested with lerobot 0.6.1).

    pip install "lerobot[dataset]"
    python sim/make_dataset.py --episodes 6 --out out/second_look_v0          # tiny smoke test
    python sim/make_dataset.py --episodes 1200 --out out/second_look_v1       # the real one (use a CPU job)

Each episode = one demo of "pick up the <colour> <thing> and place it in the tray".
Half of the episodes start from the HOME pose (target visible to the front camera), the other half start
hovering above a hidden zone (target visible only to the wrist camera - the situation right after a 'look').
Only successful demos are kept. Never demo a target the robot cannot see: it would teach the VLA to guess.
"""
import argparse
import os
import shutil
import sys
import time

os.environ.setdefault("MUJOCO_GL", "osmesa")     # headless Linux. On Windows/macOS delete this line.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np                               # noqa: E402
from lerobot.datasets import LeRobotDataset      # noqa: E402

from expert import TASK_TEXT, run_expert         # noqa: E402
from world import OBJECTS, SecondLookEnv         # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=6)
    ap.add_argument("--out", default="out/second_look_v0")
    ap.add_argument("--seed0", type=int, default=0)
    ap.add_argument("--img", type=int, default=224)
    args = ap.parse_args()

    if os.path.exists(args.out):
        shutil.rmtree(args.out)                  # LeRobot wants an empty or new folder
    env = SecondLookEnv(render=True, img=args.img)
    img = {"dtype": "video", "shape": (args.img, args.img, 3), "names": ["height", "width", "channels"]}
    names = ["x", "y", "z", "gripper"]
    features = {
        "observation.images.front": img,
        "observation.images.wrist": img,
        "observation.state": {"dtype": "float32", "shape": (4,), "names": names},
        "action": {"dtype": "float32", "shape": (4,), "names": names},
    }
    ds = LeRobotDataset.create(repo_id="local/second_look", fps=10, features=features,
                               root=args.out, robot_type="gantry", use_videos=True,
                               streaming_encoding=True, encoder_queue_maxsize=2000)
    kept, tries, frames_total, t0 = 0, 0, 0, time.time()
    while kept < args.episodes:
        seed = args.seed0 + tries
        tries += 1
        rng = np.random.default_rng(10_000 + seed)
        target = OBJECTS[seed % 3]
        start = str(rng.choice(["home", "home", "look_L", "look_R"]))
        env.reset(seed=seed, target=target, start=start)
        ok, frames = run_expert(env, target, rng)
        if not ok:
            continue                             # keep only successful demos
        for obs, action in frames:
            ds.add_frame({"observation.images.front": obs["front"],
                          "observation.images.wrist": obs["wrist"],
                          "observation.state": obs["state"], "action": action,
                          "task": TASK_TEXT[target]})
        ds.save_episode()
        kept += 1
        frames_total += len(frames)
    ds.finalize()
    print(f"kept {kept} of {tries} tries, {frames_total} frames, {time.time() - t0:.1f} s -> {args.out}")


if __name__ == "__main__":
    main()
