"""Official LeRobot v3.0 Dataset Exporter for Second Look (Role C).

Uses official LeRobot 0.6.1 LeRobotDataset API directly:
- Codebase version: v3.0
- Explicit feature schema:
    - observation.state: float32, shape (6,), names: [gx, gy, gz, roll, pitch, gripper]
    - action: float32, shape (6,), names: [gx, gy, gz, roll, pitch, gripper]
    - observation.images.front: video, 224x224, 10 fps
    - observation.images.wrist: video, 224x224, 10 fps
    - task: string in standard LeRobot task metadata
- Hard validation assertions before writing every frame.
"""
import argparse
import os
import shutil
import sys
import time
import numpy as np

# Ensure scipy.io dummy exists on Windows if blocked by WDAC
try:
    import scipy.io  # noqa: F401
except ImportError:
    import types
    mock_scipy_io = types.ModuleType("scipy.io")
    mock_scipy_io.__version__ = "1.0.0"
    mock_scipy_io.loadmat = lambda *args, **kwargs: {}
    mock_scipy_io.savemat = lambda *args, **kwargs: None
    mock_scipy_io.whosmat = lambda *args, **kwargs: []
    sys.modules["scipy.io"] = mock_scipy_io

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sim"))
from world import SecondLookEnv, OBJECTS
from expert import run_expert, TASK_TEXT

from lerobot.datasets.lerobot_dataset import LeRobotDataset
from lerobot.configs.video import RGBEncoderConfig

JOINT_NAMES = ["gx", "gy", "gz", "roll", "pitch", "gripper"]


def state_4_to_6(arr_4: np.ndarray) -> np.ndarray:
    """Converts 4D gantry state/action [x, y, z, gripper] to 6D [gx, gy, gz, roll, pitch, gripper].
    
    The gantry robot has 3 linear slide axes and a parallel gripper (roll=0, pitch=0).
    """
    assert len(arr_4) == 4, f"Expected 4 elements, got {len(arr_4)}"
    # [gx, gy, gz, roll, pitch, gripper]
    return np.array([arr_4[0], arr_4[1], arr_4[2], 0.0, 0.0, arr_4[3]], dtype=np.float32)


def main():
    parser = argparse.ArgumentParser(description="Export Second Look demos to official LeRobot v3.0 format.")
    parser.add_argument("--episodes", type=int, default=50, help="Number of episodes to generate.")
    parser.add_argument("--seed0", type=int, default=0, help="Starting PRNG seed.")
    parser.add_argument("--out", type=str, default="out/second_look_v2", help="Target output directory.")
    parser.add_argument("--img", type=int, default=224, help="Camera frame resolution.")
    parser.add_argument("--fps", type=int, default=10, help="Dataset frame rate.")
    args = parser.parse_args()

    out_path = os.path.abspath(args.out)
    if os.path.exists(out_path):
        print(f"Removing existing directory: {out_path}")
        shutil.rmtree(out_path)

    # Explicit feature schema
    features = {
        "observation.state": {
            "dtype": "float32",
            "shape": (6,),
            "names": JOINT_NAMES,
        },
        "action": {
            "dtype": "float32",
            "shape": (6,),
            "names": JOINT_NAMES,
        },
        "observation.images.front": {
            "dtype": "video",
            "shape": (args.img, args.img, 3),
            "names": ["height", "width", "channels"],
        },
        "observation.images.wrist": {
            "dtype": "video",
            "shape": (args.img, args.img, 3),
            "names": ["height", "width", "channels"],
        },
    }

    # Standard H.264 video encoding config
    encoder_cfg = RGBEncoderConfig(vcodec="h264")

    print(f"Initializing LeRobotDataset at {out_path} (target episodes: {args.episodes})...")
    ds = LeRobotDataset.create(
        repo_id="local/second_look_v2",
        fps=args.fps,
        features=features,
        root=out_path,
        robot_type="gantry",
        use_videos=True,
        rgb_encoder=encoder_cfg,
    )

    env = SecondLookEnv(render=True, img=args.img, randomize=True)
    kept, tries, total_frames, t0 = 0, 0, 0, time.time()

    while kept < args.episodes:
        seed = args.seed0 + tries
        tries += 1
        rng = np.random.default_rng(10_000 + seed)
        target = OBJECTS[seed % 3]
        start = ["home", "look_L", "look_R"][(seed // 3) % 3]

        env.reset(seed=seed, target=target, start=start)
        ok, frames = run_expert(env, target, rng)
        if not ok or len(frames) == 0:
            continue

        task_str = TASK_TEXT[target]

        for obs, action in frames:
            state_6 = state_4_to_6(obs["state"])
            action_6 = state_4_to_6(action)
            front_img = obs["front"]
            wrist_img = obs["wrist"]

            # HARD CHECKS: Assert dtype and shape before writing each frame
            assert isinstance(state_6, np.ndarray), f"State must be a numpy array, got {type(state_6)}"
            assert state_6.dtype == np.float32, f"State dtype must be float32, got {state_6.dtype}"
            assert state_6.shape == (6,), f"State shape must be (6,), got {state_6.shape}"

            assert isinstance(action_6, np.ndarray), f"Action must be a numpy array, got {type(action_6)}"
            assert action_6.dtype == np.float32, f"Action dtype must be float32, got {action_6.dtype}"
            assert action_6.shape == (6,), f"Action shape must be (6,), got {action_6.shape}"

            assert isinstance(front_img, np.ndarray) and front_img.dtype == np.uint8 and front_img.shape == (args.img, args.img, 3), (
                f"Front image invalid shape or dtype: {front_img.shape}, {front_img.dtype}"
            )
            assert isinstance(wrist_img, np.ndarray) and wrist_img.dtype == np.uint8 and wrist_img.shape == (args.img, args.img, 3), (
                f"Wrist image invalid shape or dtype: {wrist_img.shape}, {wrist_img.dtype}"
            )
            assert isinstance(task_str, str) and len(task_str) > 0, "Task string must be a non-empty string"

            ds.add_frame({
                "observation.state": state_6,
                "action": action_6,
                "observation.images.front": front_img,
                "observation.images.wrist": wrist_img,
                "task": task_str,
            })

        ds.save_episode()
        kept += 1
        total_frames += len(frames)
        elapsed = time.time() - t0
        print(f"  [Episode {kept}/{args.episodes}] Seed {seed} ({len(frames)} frames) | Total: {total_frames} frames ({elapsed:.1f}s)")

    print(f"Finalizing dataset at {out_path}...")
    ds.finalize()
    total_time = time.time() - t0
    print(f"[DONE] Successfully exported {kept} episodes ({total_frames} frames) in {total_time:.1f}s -> {out_path}")


if __name__ == "__main__":
    main()
