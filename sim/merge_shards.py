"""Merge dataset shards made by several make_dataset.py jobs into one LeRobot dataset. Tested with lerobot 0.6.1.

    python sim/make_dataset.py --episodes 300 --seed0 0     --out out/shard_0     # job 1
    python sim/make_dataset.py --episodes 300 --seed0 100000 --out out/shard_1    # job 2  (use different seeds!)
    python sim/merge_shards.py --shards out/shard_0 out/shard_1 --out out/second_look_v1
"""
import argparse
import os
import shutil

from lerobot.datasets import LeRobotDataset
from lerobot.datasets.dataset_tools import merge_datasets

ap = argparse.ArgumentParser()
ap.add_argument("--shards", nargs="+", required=True)
ap.add_argument("--out", required=True)
args = ap.parse_args()
if os.path.exists(args.out):
    shutil.rmtree(args.out)
parts = [LeRobotDataset("local/second_look", root=p) for p in args.shards]
merged = merge_datasets(parts, output_repo_id="local/second_look", output_dir=args.out)
print(f"merged {len(parts)} shards -> {merged.num_episodes} episodes, {merged.num_frames} frames in {args.out}")
