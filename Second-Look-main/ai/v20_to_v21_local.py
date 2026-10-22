"""Local LeRobot dataset v2.0 -> v2.1 shim (offline, no Hub, no LeRobot import).

Why this exists
---------------
C's dataset (out/second_look_v1) is LeRobot format v2.0. Current LeRobot
(0.6.x) only reads v3.0, and its official converter (v2.1 -> v3.0) needs the
v2.1 per-episode stats file `meta/episodes_stats.jsonl`. LeRobot removed the
official v2.0 -> v2.1 converter in v0.4.0, and the old one needs the Hub.
This script does that one missing step locally:

  1. computes per-episode stats (min/max/mean/std/count) for every feature
  2. writes meta/episodes_stats.jsonl
  3. sets info.json codebase_version to "v2.1"

Then you run LeRobot's official v2.1 -> v3.0 converter (see the Kaggle
notebook). Only needs numpy, pandas, fastparquet-or-pyarrow, opencv.

Stats conventions (match LeRobot's compute_stats):
  * image/video features: sampled frames, per-channel, scaled to [0,1],
    arrays shaped (3,1,1), count = number of sampled frames
  * everything else: per-dimension over all frames, shape (D,), count (1,)
    (count = episode length)

Usage:
    python v20_to_v21_local.py --root /kaggle/working/second_look_v2   # works IN PLACE
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


def estimate_num_samples(dataset_len: int, min_num_samples=100, max_num_samples=10_000, power=0.75) -> int:
    """Same sampling rule LeRobot uses for image/video stats."""
    if dataset_len < min_num_samples:
        min_num_samples = min(min_num_samples, dataset_len)
    return max(min_num_samples, min(int(dataset_len**power), max_num_samples))


def sample_indices(n: int) -> list[int]:
    k = estimate_num_samples(n)
    return np.round(np.linspace(0, n - 1, k)).astype(int).tolist()


def read_jsonl(p: Path) -> list[dict]:
    with p.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def vec_stats(arr: np.ndarray) -> dict:
    """arr: (N, D) or (N,) -> stats with shape (D,) (or (1,))."""
    a = np.asarray(arr, dtype=np.float64)
    if a.ndim == 1:
        a = a[:, None]
    return {
        "min": a.min(axis=0).tolist(),
        "max": a.max(axis=0).tolist(),
        "mean": a.mean(axis=0).tolist(),
        "std": a.std(axis=0).tolist(),
        "count": [int(a.shape[0])],
    }


def video_stats(video_path: Path, ep_len: int) -> dict:
    """Per-channel stats over sampled frames, RGB scaled to [0,1], shape (3,1,1)."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open video {video_path}")
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or ep_len
    n = min(n_frames, ep_len) if ep_len else n_frames
    want = set(sample_indices(n))
    px = []  # list of (H*W,3) float arrays
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i in want:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).astype(np.float64) / 255.0
            px.append(rgb.reshape(-1, 3))
        i += 1
    cap.release()
    if not px:
        raise RuntimeError(f"decoded 0 sampled frames from {video_path}")
    # Per-frame channel means so std reflects pooled pixel variance
    allpx = np.concatenate(px, axis=0)  # (S*H*W, 3)
    shape = (3, 1, 1)
    return {
        "min": allpx.min(axis=0).reshape(shape).tolist(),
        "max": allpx.max(axis=0).reshape(shape).tolist(),
        "mean": allpx.mean(axis=0).reshape(shape).tolist(),
        "std": allpx.std(axis=0).reshape(shape).tolist(),
        "count": [len(px)],
    }


def find_video(root: Path, info: dict, key: str, ep: int) -> Path:
    chunks_size = info.get("chunks_size", 1000)
    tpl = info.get("video_path") or "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4"
    return root / tpl.format(episode_chunk=ep // chunks_size, video_key=key, episode_index=ep)


def find_parquet(root: Path, info: dict, ep: int) -> Path:
    chunks_size = info.get("chunks_size", 1000)
    tpl = info.get("data_path") or "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet"
    return root / tpl.format(episode_chunk=ep // chunks_size, episode_index=ep)


def fix_columns(df: pd.DataFrame, features: dict) -> tuple[pd.DataFrame, bool]:
    """C's export stores vector columns as JSON strings like "[0.0,-0.28,0.3,1.0]".
    LeRobot needs real float lists, so parse them and cast scalars to the dtype in info.json."""
    changed = False
    for key, ft in features.items():
        if ft["dtype"] in ("video", "image") or key not in df.columns:
            continue
        col = df[key]
        first = col.iloc[0] if len(col) else None
        np_dtype = np.dtype(ft["dtype"]) if ft["dtype"] != "string" else None
        if isinstance(first, str):
            parsed = [json.loads(v) for v in col]
            if len(ft["shape"]) == 1 and ft["shape"][0] == 1 and not isinstance(parsed[0], list):
                df[key] = np.asarray(parsed, dtype=np_dtype)
            else:
                df[key] = [np.asarray(v, dtype=np_dtype) for v in parsed]
            changed = True
        elif col.dtype == object and np_dtype is not None:
            df[key] = [np.asarray(v, dtype=np_dtype) for v in col]
            changed = True
        elif np_dtype is not None and col.dtype != np_dtype and col.dtype != object:
            df[key] = col.astype(np_dtype)
            changed = True
    return df, changed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="dataset root containing meta/, data/, videos/ (modified IN PLACE)")
    args = ap.parse_args()
    root = Path(args.root)

    info_path = root / "meta" / "info.json"
    info = json.loads(info_path.read_text())
    ver = info.get("codebase_version")
    if ver == "v2.1" and (root / "meta" / "episodes_stats.jsonl").exists():
        print("Already v2.1 with episodes_stats.jsonl - nothing to do.")
        return 0
    if ver not in ("v2.0", "v2.1"):
        print(f"ERROR: expected codebase_version v2.0/v2.1, found {ver!r}", file=sys.stderr)
        return 1

    # C's export puts videos at videos/<camera>/episode_N.mp4 (no chunk folder); LeRobot's converter
    # only looks in videos/chunk-XXX/<camera>/episode_N.mp4. Move them and fix info.json.
    vtpl = info.get("video_path") or ""
    if vtpl and "{episode_chunk" not in vtpl:
        import shutil
        cs = info.get("chunks_size", 1000)
        moved = 0
        for key, ft in info["features"].items():
            if ft["dtype"] not in ("video", "image"):
                continue
            for f in sorted((root / "videos" / key).glob("episode_*.mp4")):
                ep = int(f.stem.split("_")[1])
                dst = root / "videos" / f"chunk-{ep // cs:03d}" / key / f.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(f), str(dst))
                moved += 1
        info["video_path"] = "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4"
        print(f"moved {moved} videos into chunk folders")

    episodes = read_jsonl(root / "meta" / "episodes.jsonl")
    episodes.sort(key=lambda e: e["episode_index"])
    features = info["features"]
    print(f"{len(episodes)} episodes, features: {list(features)}")

    out_path = root / "meta" / "episodes_stats.jsonl"
    with out_path.open("w") as out:
        for n, ep in enumerate(episodes):
            idx = ep["episode_index"]
            length = ep["length"]
            pq_path = find_parquet(root, info, idx)
            df = pd.read_parquet(pq_path)
            df, changed = fix_columns(df, features)
            if changed:
                df.to_parquet(pq_path, index=False)   # rewrite with proper numeric list columns
            if len(df) != length:
                print(f"WARNING ep {idx}: parquet has {len(df)} rows but episodes.jsonl says {length}")
            stats = {}
            for key, ft in features.items():
                if ft["dtype"] in ("video", "image"):
                    stats[key] = video_stats(find_video(root, info, key, idx), length)
                else:
                    col = df[key]
                    arr = np.stack(col.to_numpy()) if col.dtype == object else col.to_numpy()
                    stats[key] = vec_stats(arr)
            out.write(json.dumps({"episode_index": idx, "stats": stats}) + "\n")
            if (n + 1) % 100 == 0 or n + 1 == len(episodes):
                print(f"  stats {n + 1}/{len(episodes)}")

    # The official v2.1 -> v3.0 converter does `del info["total_chunks"]` / `["total_videos"]` and
    # reads info["video_path"], so make sure those v2.x fields exist.
    n_cams = sum(1 for f in features.values() if f["dtype"] == "video")
    info.setdefault("chunks_size", 1000)
    info.setdefault("total_chunks", math.ceil(len(episodes) / info["chunks_size"]))
    info.setdefault("total_videos", n_cams * len(episodes))
    info.setdefault("data_path", "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet")
    if n_cams:
        info.setdefault("video_path", "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4")
    else:
        info.setdefault("video_path", None)

    info["codebase_version"] = "v2.1"
    info_path.write_text(json.dumps(info, indent=4))
    print(f"Wrote {out_path} and set codebase_version=v2.1 in {info_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
