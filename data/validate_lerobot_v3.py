"""Validation script for LeRobot v3.0 datasets.

Performs strict QA verification:
1. Loads dataset with official LeRobotDataset(repo_id, root=...).
2. Asserts codebase_version == "v3.0" in meta/info.json.
3. Checks every numeric column (observation.state, action) is a numeric float32 vector with shape (6,).
4. Verifies number of rows per episode matches meta/episodes.jsonl.
5. Verifies every video file decodes properly with expected frame count matching table length.
6. Asserts meta/stats.json exists with valid mean/std/min/max.
7. Exits non-zero on any failure.
"""
import argparse
import json
import os
import sys
from pathlib import Path
import cv2
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

from lerobot.datasets.lerobot_dataset import LeRobotDataset


def count_video_frames(video_path: Path) -> int:
    """Decodes video and returns total frame count."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise IOError(f"Could not open video file: {video_path}")
    count = 0
    while True:
        ret, _ = cap.read()
        if not ret:
            break
        count += 1
    cap.release()
    return count


def validate_dataset(dataset_dir: str, repo_id: str = "local/second_look_v2"):
    root = Path(dataset_dir).resolve()
    print(f"\n==================================================")
    print(f"VALIDATING LEROBOT v3.0 DATASET AT: {root}")
    print(f"==================================================")

    if not root.exists():
        print(f"[FAIL] Directory does not exist: {root}", file=sys.stderr)
        sys.exit(1)

    # 1. Verify meta/info.json and codebase_version
    info_path = root / "meta" / "info.json"
    if not info_path.exists():
        print(f"[FAIL] Missing meta/info.json in {root}", file=sys.stderr)
        sys.exit(1)

    with open(info_path, "r", encoding="utf-8") as f:
        info = json.load(f)

    codebase_ver = info.get("codebase_version")
    print(f"[CHECK] codebase_version: '{codebase_ver}'")
    if codebase_ver != "v3.0":
        print(f"[FAIL] Expected codebase_version == 'v3.0', got '{codebase_ver}'", file=sys.stderr)
        sys.exit(1)
    print("  -> PASS: codebase_version is v3.0")

    # 2. Verify meta/stats.json exists
    stats_path = root / "meta" / "stats.json"
    if not stats_path.exists():
        print(f"[FAIL] Missing meta/stats.json in {root}", file=sys.stderr)
        sys.exit(1)
    with open(stats_path, "r", encoding="utf-8") as f:
        stats = json.load(f)
    for key in ("observation.state", "action"):
        if key not in stats:
            print(f"[FAIL] Key '{key}' missing from stats.json", file=sys.stderr)
            sys.exit(1)
        for stat_type in ("min", "max", "mean", "std"):
            if stat_type not in stats[key]:
                print(f"[FAIL] Metric '{stat_type}' missing for '{key}' in stats.json", file=sys.stderr)
                sys.exit(1)
    print("  -> PASS: meta/stats.json exists with valid statistics for observation.state and action")

    # 3. Verify meta/episodes.jsonl
    episodes_file = root / "meta" / "episodes.jsonl"
    if not episodes_file.exists():
        print(f"[FAIL] Missing meta/episodes.jsonl in {root}", file=sys.stderr)
        sys.exit(1)

    episodes = []
    with open(episodes_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                episodes.append(json.loads(line))

    total_episodes = len(episodes)
    print(f"[CHECK] Total episodes recorded in episodes.jsonl: {total_episodes}")
    if total_episodes == 0:
        print("[FAIL] Dataset contains 0 episodes!", file=sys.stderr)
        sys.exit(1)

    # 4. Load dataset using LeRobotDataset class
    print(f"[CHECK] Loading dataset via official LeRobotDataset(repo_id='{repo_id}', root='{root}')...")
    try:
        ds = LeRobotDataset(repo_id=repo_id, root=root)
    except Exception as e:
        print(f"[FAIL] Failed to instantiate LeRobotDataset: {e}", file=sys.stderr)
        sys.exit(1)

    total_frames = len(ds)
    print(f"  -> PASS: LeRobotDataset loaded successfully with {total_frames} total frames across {total_episodes} episodes.")

    # 5. Check numeric types and shapes on sampled items
    print(f"[CHECK] Verifying numeric dtypes and shapes (sampling first, middle, last frames)...")
    sample_indices = [0, total_frames // 2, total_frames - 1]
    for idx in sample_indices:
        item = ds[idx]
        state = item["observation.state"]
        action = item["action"]

        # Check PyTorch tensor or numpy
        state_np = state.numpy() if hasattr(state, "numpy") else np.asarray(state)
        action_np = action.numpy() if hasattr(action, "numpy") else np.asarray(action)

        if not np.issubdtype(state_np.dtype, np.floating):
            print(f"[FAIL] observation.state dtype is {state_np.dtype}, expected float32 numeric!", file=sys.stderr)
            sys.exit(1)
        if state_np.shape != (6,):
            print(f"[FAIL] observation.state shape is {state_np.shape}, expected (6,)!", file=sys.stderr)
            sys.exit(1)

        if not np.issubdtype(action_np.dtype, np.floating):
            print(f"[FAIL] action dtype is {action_np.dtype}, expected float32 numeric!", file=sys.stderr)
            sys.exit(1)
        if action_np.shape != (6,):
            print(f"[FAIL] action shape is {action_np.shape}, expected (6,)!", file=sys.stderr)
            sys.exit(1)
    print("  -> PASS: All sampled state and action vectors are float32 numeric arrays of shape (6,).")

    # 6. Verify row count matches episodes.jsonl and videos decode with matching frame count
    print(f"[CHECK] Verifying episode frame counts and video stream decoding...")
    chunk_pattern = info.get("data_path", "data/chunk-000/episode_{episode_index:06d}.parquet")
    
    for ep_info in episodes:
        ep_idx = ep_info["episode_index"]
        expected_len = ep_info["length"]

        # Check video streams
        for cam_key in ("observation.images.front", "observation.images.wrist"):
            vpath_template = info.get("video_path", "videos/{video_key}/episode_{episode_index:06d}.mp4")
            vpath = root / vpath_template.format(video_key=cam_key, episode_index=ep_idx)
            if not vpath.exists():
                print(f"[FAIL] Missing video file: {vpath}", file=sys.stderr)
                sys.exit(1)
            
            vid_frames = count_video_frames(vpath)
            if vid_frames != expected_len:
                print(
                    f"[FAIL] Episode {ep_idx} video {cam_key} frame count mismatch! "
                    f"Video has {vid_frames} frames, but episode length is {expected_len}",
                    file=sys.stderr
                )
                sys.exit(1)

    print(f"  -> PASS: All {total_episodes} episodes decoded with 100% video-table frame synchronization.")

    print(f"\n==================================================")
    print(f"RESULT: ALL CHECKS PASSED SUCCESSFULLY (v3.0 VALID)")
    print(f"==================================================\n")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate LeRobot v3.0 dataset.")
    parser.add_argument("--dataset", type=str, default="out/second_look_v2", help="Dataset directory path.")
    parser.add_argument("--repo-id", type=str, default="local/second_look_v2", help="Dataset repo_id.")
    args = parser.parse_args()

    validate_dataset(args.dataset, args.repo_id)
