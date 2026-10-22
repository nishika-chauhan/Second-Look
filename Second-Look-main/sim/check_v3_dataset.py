"""Validator for REAL LeRobot v3.0 datasets (role B).

Why this exists: sim/validate_lerobot_v3.py looks for meta/episodes.jsonl and
one video per episode. That is the v2 layout. v3.0 stores:
    meta/info.json, meta/stats.json, meta/tasks.parquet
    meta/episodes/chunk-XXX/file-XXX.parquet   (one row per episode)
    data/chunk-XXX/file-XXX.parquet            (many episodes per file)
    videos/<camera>/chunk-XXX/file-XXX.mp4     (many episodes per file)

Run from the repo root:
    python sim/check_v3_dataset.py --dataset out/five_episodes
    python sim/check_v3_dataset.py --dataset out/second_look_v2 --repo-id local/second_look_v2

Exit code 0 = all hard checks passed, 1 = a hard check failed.
Use --no-load to skip the LeRobotDataset load/decode test.
"""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

CAMERAS = ("observation.images.front", "observation.images.wrist")
failures = []


def ok(msg):
    print(f"  [PASS] {msg}")


def warn(msg):
    print(f"  [WARN] {msg}")


def fail(msg):
    print(f"  [FAIL] {msg}")
    failures.append(msg)


def video_frames(path: Path) -> int:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return -1
    n = 0
    while cap.read()[0]:
        n += 1
    cap.release()
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="out/second_look_v2")
    ap.add_argument("--repo-id", default="local/second_look_v2")
    ap.add_argument("--no-load", action="store_true", help="skip LeRobotDataset load test")
    a = ap.parse_args()

    root = Path(a.dataset).resolve()
    print(f"\nChecking v3.0 dataset: {root}\n")
    if not (root / "meta" / "info.json").exists():
        fail(f"{root / 'meta' / 'info.json'} not found")
        return finish()

    info = json.loads((root / "meta" / "info.json").read_text(encoding="utf-8"))
    n_eps, n_frames, fps = info["total_episodes"], info["total_frames"], info["fps"]

    # 1. info.json
    print("1. info.json")
    if info.get("codebase_version") == "v3.0":
        ok("codebase_version v3.0")
    else:
        fail(f"codebase_version is {info.get('codebase_version')!r}")
    feats = info["features"]
    for k in ("observation.state", "action"):
        if k in feats and feats[k]["dtype"] == "float32" and feats[k]["shape"] == [6]:
            ok(f"{k}: float32 (6,)")
        else:
            fail(f"{k} missing or not float32 (6,): {feats.get(k)}")
    for cam in CAMERAS:
        if cam in feats and feats[cam]["dtype"] == "video":
            ok(f"{cam}: video {feats[cam]['shape']}")
        else:
            fail(f"{cam} missing or not a video feature")
    print(f"     fps={fps}  episodes={n_eps}  frames={n_frames}")

    # 2. stats.json
    print("2. stats.json")
    sp = root / "meta" / "stats.json"
    if sp.exists():
        stats = json.loads(sp.read_text(encoding="utf-8"))
        for k in ("observation.state", "action"):
            missing = [m for m in ("min", "max", "mean", "std") if m not in stats.get(k, {})]
            fail(f"stats[{k}] missing {missing}") if missing else ok(f"stats[{k}] has min/max/mean/std")
        for k in ("observation.state", "action"):
            std = np.array(stats.get(k, {}).get("std", []), dtype=float)
            names = feats[k]["names"]
            flat = [n for n, s in zip(names, std) if s < 1e-8]
            if flat:
                warn(f"{k} has zero-variance dims {flat} (expected: roll/pitch are fixed at 0). "
                     "Normalisation divides by std+eps, so these stay 0 -- harmless, but note it.")
    else:
        fail("meta/stats.json missing")

    # 3. tasks
    print("3. tasks.parquet")
    tp = root / "meta" / "tasks.parquet"
    if tp.exists():
        tasks = pd.read_parquet(tp)
        ok(f"{len(tasks)} task(s)")
        print(tasks.to_string().replace("\n", "\n     "))
    else:
        fail("meta/tasks.parquet missing")

    # 4. episodes metadata
    print("4. meta/episodes parquet")
    ep_files = sorted((root / "meta" / "episodes").glob("chunk-*/file-*.parquet"))
    if not ep_files:
        fail("no meta/episodes/chunk-*/file-*.parquet")
        return finish()
    eps = pd.concat([pd.read_parquet(f) for f in ep_files], ignore_index=True)
    ok(f"{len(eps)} episode rows") if len(eps) == n_eps else fail(f"{len(eps)} rows vs total_episodes={n_eps}")
    if "length" in eps.columns:
        ok(f"sum(length)={eps['length'].sum()}") if eps["length"].sum() == n_frames else fail(
            f"sum(length)={eps['length'].sum()} vs total_frames={n_frames}")
    else:
        warn("no 'length' column in episodes metadata; per-episode length check skipped")

    # 5. data parquet
    print("5. data parquet")
    d_files = sorted((root / "data").glob("chunk-*/file-*.parquet"))
    if not d_files:
        fail("no data/chunk-*/file-*.parquet")
        return finish()
    df = pd.concat([pd.read_parquet(f) for f in d_files], ignore_index=True)
    ok(f"{len(df)} rows") if len(df) == n_frames else fail(f"{len(df)} rows vs total_frames={n_frames}")
    for col in ("observation.state", "action", "episode_index", "frame_index", "timestamp", "index", "task_index"):
        if col not in df.columns:
            fail(f"column {col} missing")
    if not failures:
        for col in ("observation.state", "action"):
            arr = np.stack(df[col].to_numpy())
            if arr.shape == (len(df), 6) and np.isfinite(arr).all():
                ok(f"{col}: shape {arr.shape}, all finite, range [{arr.min():.3f}, {arr.max():.3f}]")
            else:
                fail(f"{col}: bad shape {arr.shape} or NaN/Inf")
        counts = df.groupby("episode_index").size()
        if "length" in eps.columns:
            bad = [int(e) for e, l in zip(eps["episode_index"], eps["length"]) if counts.get(e, -1) != l]
            ok("per-episode row counts match metadata") if not bad else fail(f"row-count mismatch in episodes {bad[:10]}")
        if (df["index"].to_numpy() == np.arange(len(df))).all():
            ok("global index is contiguous 0..N-1")
        else:
            fail("global index is not contiguous")
        ts_ok = all(
            np.allclose(g["timestamp"].to_numpy(), g["frame_index"].to_numpy() / fps, atol=1e-4)
            for _, g in df.groupby("episode_index")
        )
        ok(f"timestamps == frame_index/{fps}") if ts_ok else fail("timestamps do not match frame_index/fps")

    # 6. videos: total decoded frames per camera must equal total_frames
    print("6. videos")
    for cam in CAMERAS:
        files = sorted((root / "videos" / cam).glob("chunk-*/file-*.mp4"))
        if not files:
            fail(f"no video files for {cam}")
            continue
        total = 0
        for f in files:
            n = video_frames(f)
            if n < 0:
                fail(f"cannot open {f}")
            total += max(n, 0)
        ok(f"{cam}: {len(files)} file(s), {total} frames") if total == n_frames else fail(
            f"{cam}: decoded {total} frames vs total_frames={n_frames}")

    # 7. the real test: load through LeRobot like training will
    if not a.no_load:
        print("7. LeRobotDataset load + decode (what training actually does)")
        try:
            from lerobot.datasets.lerobot_dataset import LeRobotDataset

            ds = LeRobotDataset(a.repo_id, root=root)
            ok(f"loaded, len={len(ds)}")
            for i in (0, len(ds) // 2, len(ds) - 1):
                item = ds[i]
                for cam in CAMERAS:
                    shp = tuple(item[cam].shape)
                    if shp != (3, 224, 224):
                        fail(f"frame {i} {cam} shape {shp}, expected (3,224,224)")
                for k in ("observation.state", "action"):
                    if tuple(item[k].shape) != (6,):
                        fail(f"frame {i} {k} shape {tuple(item[k].shape)}")
                if not isinstance(item.get("task"), str):
                    fail(f"frame {i} has no task string")
            ok("sampled frames decode with expected shapes") if not failures else None
        except Exception as e:  # noqa: BLE001
            fail(f"LeRobotDataset load/decode failed: {type(e).__name__}: {e}")
    return finish()


def finish():
    print()
    if failures:
        print(f"RESULT: {len(failures)} FAILURE(S)")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("RESULT: ALL CHECKS PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()
