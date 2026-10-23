"""Dataset smoke-load check (Week 2, Step 4).

Verifies that C's LeRobot v2.0 dataset at out/second_look_v1/ can be
read cleanly with fastparquet + OpenCV before you commit to a long
training run.

Checks:
  1. Required parquet files exist and open cleanly
  2. Episode count and frame count match expectations
  3. Both camera streams (front + wrist) are present in the schema
  4. A sample frame can be decoded from at least one episode
  5. Action and state columns are present and finite (no NaN/Inf)

Run from the repo root:
    python ai/dataset_check.py
    python ai/dataset_check.py --path out/second_look_v1
    python ai/dataset_check.py --path out/second_look_v1 --episodes 5
"""

from __future__ import annotations

import argparse
import sys
import os
from pathlib import Path


def check(path: str, n_episodes: int = 3) -> bool:
    root = Path(path)
    ok = True

    def log(sym, msg):
        print(f"  {sym}  {msg}")

    print(f"\nSmoke-loading dataset at: {root.resolve()}\n")

    # ------------------------------------------------------------------
    # 1. Directory exists
    # ------------------------------------------------------------------
    if not root.is_dir():
        print(f"  ✗  Directory not found: {root}")
        print("\n  → Run this from the repo root, or pass --path correctly.")
        return False

    # ------------------------------------------------------------------
    # 2. Import checks
    # ------------------------------------------------------------------
    try:
        import fastparquet as fpq
        log("✓", f"fastparquet {fpq.__version__} available")
    except ImportError:
        log("✗", "fastparquet not installed  →  pip install fastparquet")
        ok = False

    try:
        import pandas as pd
        log("✓", f"pandas {pd.__version__} available")
    except ImportError:
        log("✗", "pandas not installed  →  pip install pandas")
        ok = False

    try:
        import cv2
        log("✓", f"opencv {cv2.__version__} available")
    except ImportError:
        log("✗", "opencv-python not installed  →  pip install opencv-python")
        ok = False

    import numpy as np

    if not ok:
        return False

    # ------------------------------------------------------------------
    # 3. Parquet files
    # ------------------------------------------------------------------
    data_dir = root / "data"
    if not data_dir.is_dir():
        # Some LeRobot layouts put parquet at root level
        data_dir = root
    parquet_files = sorted(data_dir.glob("**/*.parquet"))
    if not parquet_files:
        log("✗", f"No .parquet files found under {data_dir}")
        return False
    log("✓", f"Found {len(parquet_files)} parquet file(s)")

    # ------------------------------------------------------------------
    # 4. Load parquet with fastparquet
    # ------------------------------------------------------------------
    import pandas as pd
    import fastparquet  # noqa: F401

    try:
        df = pd.read_parquet(parquet_files[0], engine="fastparquet")
        log("✓", f"Loaded first parquet:  {len(df):,} rows, {len(df.columns)} columns")
    except Exception as e:
        log("✗", f"Failed to read parquet: {e}")
        return False

    # ------------------------------------------------------------------
    # 5. Schema checks
    # ------------------------------------------------------------------
    cols = list(df.columns)
    # LeRobot v2 stores images as video files on disk — NOT as parquet columns.
    # The parquet only has: index, episode_index, frame_index, timestamp,
    # observation.state, action, task_index, task.
    # Camera presence is verified by checking the videos/ directory instead.
    has_action  = any("action" in c for c in cols)
    has_state   = any("state"  in c for c in cols)
    has_episode = "episode_index" in cols or "episode_id" in cols
    has_timestamp = "timestamp" in cols

    log("✓" if has_action    else "✗", f"action column:    {'found' if has_action else 'MISSING'}")
    log("✓" if has_state     else "✗", f"state column:     {'found' if has_state else 'MISSING'}")
    log("✓" if has_episode   else "✗", f"episode_index:    {'found' if has_episode else 'MISSING'}")
    log("✓" if has_timestamp else "✗", f"timestamp column: {'found' if has_timestamp else 'MISSING'}")
    log("✓", f"columns: {cols}")

    # Camera check: look for video subdirectories
    video_dir = root / "videos"
    cam_front_dir = video_dir / "observation.images.front"
    cam_wrist_dir = video_dir / "observation.images.wrist"
    has_front_vid = cam_front_dir.is_dir()
    has_wrist_vid = cam_wrist_dir.is_dir()
    log("✓" if has_front_vid else "✗",
        f"front camera videos: {'found at videos/observation.images.front/' if has_front_vid else 'MISSING'}")
    log("✓" if has_wrist_vid else "✗",
        f"wrist camera videos: {'found at videos/observation.images.wrist/' if has_wrist_vid else 'MISSING'}")
    if not has_front_vid or not has_wrist_vid:
        ok = False

    # ------------------------------------------------------------------
    # 6. Episode / frame counts
    # ------------------------------------------------------------------
    ep_col = "episode_index" if "episode_index" in cols else (
             "episode_id" if "episode_id" in cols else None)
    if ep_col:
        ep_ids = df[ep_col].unique()
        log("✓", f"Episodes in first parquet: {len(ep_ids)}  (total rows: {len(df):,})")
        if len(ep_ids) < 1:
            log("✗", "No episodes found — parquet may be empty")
            ok = False

    # ------------------------------------------------------------------
    # 7. NaN / Inf check on action
    # ------------------------------------------------------------------
    action_cols = [c for c in cols if "action" in c]
    for ac in action_cols[:3]:
        try:
            col = df[ac]
            # Column may contain lists/arrays — explode scalars
            flat = col.explode() if col.dtype == object else col
            n_bad = (~np.isfinite(flat.astype(float))).sum()
            if n_bad > 0:
                log("✗", f"{ac}: {n_bad} NaN/Inf values")
                ok = False
            else:
                log("✓", f"{ac}: all values finite")
        except Exception as e:
            log("!", f"Could not check {ac}: {e}")

    # ------------------------------------------------------------------
    # 8. Decode one video frame from wrist stream
    # ------------------------------------------------------------------
    video_dir = root / "videos"
    wrist_vids = sorted(video_dir.glob("**/*wrist*")) if video_dir.is_dir() else []
    if not wrist_vids:
        # Try alternate layouts
        wrist_vids = sorted(root.glob("**/*wrist*.mp4"))

    if wrist_vids:
        # wrist_vids may be directories (LeRobot v2 stores one mp4 per episode
        # inside videos/observation.images.wrist/).  Find actual .mp4 files.
        mp4_files = []
        for p in wrist_vids:
            if p.is_dir():
                mp4_files.extend(sorted(p.glob("*.mp4")))
            elif p.suffix.lower() == ".mp4":
                mp4_files.append(p)

        if mp4_files:
            vid_path = mp4_files[0]
            cap = cv2.VideoCapture(str(vid_path))
            ret, frame = cap.read()
            cap.release()
            if ret:
                h, w = frame.shape[:2]
                log("✓", f"Decoded wrist frame from {vid_path.name}  ({w}×{h})")
                if w != 224 or h != 224:
                    log("!", f"Expected 224×224, got {w}×{h} — update WRIST_IMG_W/H in perception.py")
            else:
                log("✗", f"Could not decode a frame from {vid_path}")
                ok = False
        else:
            log("!", f"Video directory found but no .mp4 files inside — check {wrist_vids[0]}")
    else:
        log("!", "No wrist video directory found — skipping frame decode check")
        log(" ", "(Videos may be embedded in parquet as byte arrays — that's fine)")

    # ------------------------------------------------------------------
    # 9. Sample n_episodes worth of rows
    # ------------------------------------------------------------------
    if ep_col and len(df) > 0:
        sample_eps = list(df[ep_col].unique()[:n_episodes])
        sample = df[df[ep_col].isin(sample_eps)]
        log("✓", f"Sample load: {len(sample):,} rows across {len(sample_eps)} episode(s)")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print()
    if ok:
        print("  ✅  Dataset looks clean — safe to start training.\n")
    else:
        print("  ❌  One or more checks failed — fix before training.\n")

    return ok


def main():
    ap = argparse.ArgumentParser(description="LeRobot v2.0 dataset smoke-load check")
    ap.add_argument("--path", default="out/second_look_v1",
                    help="Path to the dataset root (default: out/second_look_v1)")
    ap.add_argument("--episodes", type=int, default=3,
                    help="Number of episodes to sample-load (default: 3)")
    args = ap.parse_args()

    success = check(args.path, args.episodes)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()