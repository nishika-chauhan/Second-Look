"""High-performance LeRobot-compatible Dataset Backend for Second Look (Role C).

Provides:
- LeRobotDataset: Complete drop-in compatible LeRobot dataset writer and reader.
- merge_datasets: Robust dataset merging tool with seed-uniqueness verification.

Saves standard LeRobot format:
- Videos (H.264/MP4) for front and wrist cameras via OpenCV.
- Tabular trajectories in Parquet format via fastparquet / pandas.
- Standard LeRobot metadata (meta/info.json, meta/episodes.jsonl, meta/tasks.jsonl, meta/stats.json).
"""
import json
import os
import shutil
from pathlib import Path
import cv2
import numpy as np
import pandas as pd
import fastparquet


class _EpisodeStatsAccumulator:
    """Accumulates min, max, mean, std across all frames in a dataset."""
    def __init__(self):
        self.state_values = []
        self.action_values = []
        self.total_frames = 0

    def update(self, states, actions):
        self.state_values.append(states)
        self.action_values.append(actions)
        self.total_frames += len(states)

    def compute(self):
        if not self.state_values:
            return {}
        all_states = np.vstack(self.state_values)
        all_actions = np.vstack(self.action_values)
        return {
            "observation.state": {
                "min": all_states.min(axis=0).tolist(),
                "max": all_states.max(axis=0).tolist(),
                "mean": all_states.mean(axis=0).tolist(),
                "std": all_states.std(axis=0).tolist(),
            },
            "action": {
                "min": all_actions.min(axis=0).tolist(),
                "max": all_actions.max(axis=0).tolist(),
                "mean": all_actions.mean(axis=0).tolist(),
                "std": all_actions.std(axis=0).tolist(),
            }
        }


class LeRobotDataset:
    def __init__(self, repo_id: str, root: str | Path | None = None, **kwargs):
        """Read-mode dataset loader."""
        self.repo_id = repo_id
        self.root = Path(root) if root else Path("out/second_look")
        if not self.root.exists():
            raise FileNotFoundError(f"Dataset root does not exist: {self.root}")

        self._load_metadata()

    def _load_metadata(self):
        info_path = self.root / "meta" / "info.json"
        if not info_path.exists():
            raise FileNotFoundError(f"Missing info.json in {self.root / 'meta'}")
        with open(info_path, "r", encoding="utf-8") as f:
            self.info = json.load(f)

        self.num_episodes = self.info.get("total_episodes", 0)
        self.num_frames = self.info.get("total_frames", 0)
        self.fps = self.info.get("fps", 10)
        self.features = self.info.get("features", {})
        self.meta = self.info  # compatibility attribute

        # Load episodes
        self.episodes = []
        ep_path = self.root / "meta" / "episodes.jsonl"
        if ep_path.exists():
            with open(ep_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        self.episodes.append(json.loads(line))

        # Build episode frame index boundaries
        self._ep_starts = []
        curr = 0
        for ep in self.episodes:
            self._ep_starts.append(curr)
            curr += ep["length"]

    def __len__(self):
        return self.num_frames

    def get_episode(self, ep_idx: int):
        """Returns all data for an episode."""
        if ep_idx < 0 or ep_idx >= self.num_episodes:
            raise IndexError(f"Episode index {ep_idx} out of range [0, {self.num_episodes})")
        
        parquet_path = self.root / "data" / "chunk-000" / f"episode_{ep_idx:06d}.parquet"
        df = pd.read_parquet(parquet_path, engine="fastparquet")

        # Load video frames
        front_video = self.root / "videos" / "observation.images.front" / f"episode_{ep_idx:06d}.mp4"
        wrist_video = self.root / "videos" / "observation.images.wrist" / f"episode_{ep_idx:06d}.mp4"
        
        def read_vid(vpath):
            cap = cv2.VideoCapture(str(vpath))
            frames = []
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            cap.release()
            return np.array(frames, dtype=np.uint8)

        front_frames = read_vid(front_video) if front_video.exists() else None
        wrist_frames = read_vid(wrist_video) if wrist_video.exists() else None

        return {
            "df": df,
            "front_frames": front_frames,
            "wrist_frames": wrist_frames,
            "metadata": self.episodes[ep_idx] if ep_idx < len(self.episodes) else {}
        }

    @classmethod
    def create(cls, repo_id: str, fps: int, features: dict, root: str | Path | None = None,
               robot_type: str = "gantry", use_videos: bool = True, **kwargs):
        """Create a write-mode dataset."""
        root_path = Path(root) if root else Path("out/second_look")
        return _DatasetWriter(repo_id, fps, features, root_path, robot_type, use_videos)


class _DatasetWriter:
    """Handles writing episodes, encoding MP4 videos, and writing Parquet tables."""
    def __init__(self, repo_id: str, fps: int, features: dict, root: Path,
                 robot_type: str = "gantry", use_videos: bool = True):
        self.repo_id = repo_id
        self.fps = fps
        self.features = features
        self.root = root
        self.robot_type = robot_type
        self.use_videos = use_videos

        # Setup directory structure
        self.data_dir = self.root / "data" / "chunk-000"
        self.meta_dir = self.root / "meta"
        self.front_video_dir = self.root / "videos" / "observation.images.front"
        self.wrist_video_dir = self.root / "videos" / "observation.images.wrist"

        for d in [self.data_dir, self.meta_dir, self.front_video_dir, self.wrist_video_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self.current_episode_frames = []
        self.total_episodes = 0
        self.total_frames = 0
        self.episodes_meta = []
        self.tasks_set = {}
        self.stats_acc = _EpisodeStatsAccumulator()

    def add_frame(self, frame: dict):
        """Buffers a single frame for the current episode."""
        self.current_episode_frames.append(frame)

    def save_episode(self, seed: int | None = None, target: str | None = None, start: str | None = None):
        """Writes buffered frames to MP4 videos and a Parquet table."""
        if not self.current_episode_frames:
            return

        ep_idx = self.total_episodes
        ep_len = len(self.current_episode_frames)
        start_frame_idx = self.total_frames
        task_text = self.current_episode_frames[0].get("task", "")

        if task_text not in self.tasks_set:
            self.tasks_set[task_text] = len(self.tasks_set)
        task_idx = self.tasks_set[task_text]

        # 1. Encode Videos
        front_frames = [f["observation.images.front"] for f in self.current_episode_frames]
        wrist_frames = [f["observation.images.wrist"] for f in self.current_episode_frames]

        h, w, _ = front_frames[0].shape
        front_vpath = self.front_video_dir / f"episode_{ep_idx:06d}.mp4"
        wrist_vpath = self.wrist_video_dir / f"episode_{ep_idx:06d}.mp4"

        for vpath, f_list in [(front_vpath, front_frames), (wrist_vpath, wrist_frames)]:
            vw = cv2.VideoWriter(str(vpath), cv2.VideoWriter_fourcc(*"mp4v"), self.fps, (w, h))
            for img in f_list:
                vw.write(cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
            vw.release()

        # 2. Extract state, actions, timestamps
        states = np.array([f["observation.state"] for f in self.current_episode_frames], dtype=np.float32)
        actions = np.array([f["action"] for f in self.current_episode_frames], dtype=np.float32)
        timestamps = np.arange(ep_len, dtype=np.float32) / float(self.fps)
        indices = np.arange(start_frame_idx, start_frame_idx + ep_len, dtype=np.int64)

        self.stats_acc.update(states, actions)

        # 3. Write Parquet Trajectory
        state_lists = [list(map(float, row)) for row in states]
        action_lists = [list(map(float, row)) for row in actions]

        df = pd.DataFrame({
            "index": indices,
            "episode_index": np.full(ep_len, ep_idx, dtype=np.int64),
            "frame_index": np.arange(ep_len, dtype=np.int64),
            "timestamp": timestamps,
            "observation.state": state_lists,
            "action": action_lists,
            "task_index": np.full(ep_len, task_idx, dtype=np.int64),
            "task": [task_text] * ep_len,
        })
        parquet_path = self.data_dir / f"episode_{ep_idx:06d}.parquet"
        df.to_parquet(parquet_path, engine="fastparquet")

        # 4. Record Episode Metadata
        meta_entry = {
            "episode_index": ep_idx,
            "length": ep_len,
            "tasks": [task_text],
            "dataset_from_index": start_frame_idx,
            "dataset_to_index": start_frame_idx + ep_len,
        }
        if seed is not None:
            meta_entry["seed"] = seed
        if target is not None:
            meta_entry["target"] = target
        if start is not None:
            meta_entry["start"] = start

        self.episodes_meta.append(meta_entry)
        self.total_episodes += 1
        self.total_frames += ep_len
        self.current_episode_frames.clear()

    def finalize(self):
        """Flushes all metadata files to disk."""
        # 1. meta/episodes.jsonl
        with open(self.meta_dir / "episodes.jsonl", "w", encoding="utf-8") as f:
            for ep in self.episodes_meta:
                f.write(json.dumps(ep) + "\n")

        # 2. meta/tasks.jsonl
        with open(self.meta_dir / "tasks.jsonl", "w", encoding="utf-8") as f:
            for task, idx in sorted(self.tasks_set.items(), key=lambda x: x[1]):
                f.write(json.dumps({"task_index": idx, "task": task}) + "\n")

        # 3. meta/stats.json
        stats = self.stats_acc.compute()
        with open(self.meta_dir / "stats.json", "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2)

        # 4. meta/info.json
        info = {
            "codebase_version": "v2.0",
            "robot_type": self.robot_type,
            "total_episodes": self.total_episodes,
            "total_frames": self.total_frames,
            "total_tasks": len(self.tasks_set),
            "total_videos": 2 * self.total_episodes,
            "total_chunks": 1,
            "chunks_size": 1000,
            "fps": self.fps,
            "splits": {
                "train": f"0[:{self.total_episodes}]"
            },
            "data_path": "data/chunk-000/episode_{episode_index:06d}.parquet",
            "video_path": "videos/{video_key}/episode_{episode_index:06d}.mp4",
            "features": self.features,
        }
        with open(self.meta_dir / "info.json", "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2)

        return LeRobotDataset(self.repo_id, root=self.root)


def merge_datasets(parts: list[LeRobotDataset], output_repo_id: str, output_dir: str | Path) -> LeRobotDataset:
    """Merges multiple dataset shards into a single consolidated dataset.
    Strictly verifies that no seed was reused across shards.
    """
    out_root = Path(output_dir)
    if out_root.exists():
        shutil.rmtree(out_root)

    # 1. Programmatically verify no seed was reused across shards
    all_seeds = []
    for p_idx, shard in enumerate(parts):
        shard_seeds = [ep["seed"] for ep in shard.episodes if "seed" in ep]
        assert len(shard_seeds) == len(set(shard_seeds)), f"Internal duplicate seeds in shard {p_idx}!"
        all_seeds.extend(shard_seeds)
    
    unique_seeds = set(all_seeds)
    if len(all_seeds) > 0:
        assert len(all_seeds) == len(unique_seeds), (
            f"SEED REUSE DETECTED ACROSS SHARDS! Total seeds: {len(all_seeds)}, unique: {len(unique_seeds)}"
        )
        print(f"[VERIFIED] All {len(all_seeds)} seeds are completely unique across all {len(parts)} shards.")

    # 2. Setup target directories
    data_out = out_root / "data" / "chunk-000"
    meta_out = out_root / "meta"
    front_out = out_root / "videos" / "observation.images.front"
    wrist_out = out_root / "videos" / "observation.images.wrist"

    for d in [data_out, meta_out, front_out, wrist_out]:
        d.mkdir(parents=True, exist_ok=True)

    merged_episodes_meta = []
    stats_acc = _EpisodeStatsAccumulator()
    global_ep_idx = 0
    global_frame_idx = 0
    all_tasks = {}

    for shard in parts:
        for ep_info in shard.episodes:
            old_idx = ep_info["episode_index"]
            ep_len = ep_info["length"]
            task_text = ep_info["tasks"][0]
            if task_text not in all_tasks:
                all_tasks[task_text] = len(all_tasks)
            task_idx = all_tasks[task_text]

            # Copy and rename videos
            old_front = shard.root / "videos" / "observation.images.front" / f"episode_{old_idx:06d}.mp4"
            old_wrist = shard.root / "videos" / "observation.images.wrist" / f"episode_{old_idx:06d}.mp4"
            new_front = front_out / f"episode_{global_ep_idx:06d}.mp4"
            new_wrist = wrist_out / f"episode_{global_ep_idx:06d}.mp4"
            shutil.copy2(old_front, new_front)
            shutil.copy2(old_wrist, new_wrist)

            # Read old parquet, update global indices, write new parquet
            old_parquet = shard.root / "data" / "chunk-000" / f"episode_{old_idx:06d}.parquet"
            df = pd.read_parquet(old_parquet, engine="fastparquet")
            
            df["episode_index"] = global_ep_idx
            df["index"] = np.arange(global_frame_idx, global_frame_idx + ep_len, dtype=np.int64)
            df["task_index"] = task_idx

            new_parquet = data_out / f"episode_{global_ep_idx:06d}.parquet"
            df.to_parquet(new_parquet, engine="fastparquet")

            # Update stats
            states = np.array(df["observation.state"].tolist(), dtype=np.float32)
            actions = np.array(df["action"].tolist(), dtype=np.float32)
            stats_acc.update(states, actions)

            # Metadata entry
            new_meta = {
                "episode_index": global_ep_idx,
                "length": ep_len,
                "tasks": [task_text],
                "dataset_from_index": global_frame_idx,
                "dataset_to_index": global_frame_idx + ep_len,
            }
            if "seed" in ep_info:
                new_meta["seed"] = ep_info["seed"]
            if "target" in ep_info:
                new_meta["target"] = ep_info["target"]
            if "start" in ep_info:
                new_meta["start"] = ep_info["start"]

            merged_episodes_meta.append(new_meta)
            global_ep_idx += 1
            global_frame_idx += ep_len

    # Write merged metadata
    with open(meta_out / "episodes.jsonl", "w", encoding="utf-8") as f:
        for ep in merged_episodes_meta:
            f.write(json.dumps(ep) + "\n")

    with open(meta_out / "tasks.jsonl", "w", encoding="utf-8") as f:
        for task, idx in sorted(all_tasks.items(), key=lambda x: x[1]):
            f.write(json.dumps({"task_index": idx, "task": task}) + "\n")

    stats = stats_acc.compute()
    with open(meta_out / "stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    base_info = parts[0].info
    merged_info = {
        "codebase_version": "v2.0",
        "robot_type": base_info.get("robot_type", "gantry"),
        "total_episodes": global_ep_idx,
        "total_frames": global_frame_idx,
        "total_tasks": len(all_tasks),
        "total_videos": 2 * global_ep_idx,
        "total_chunks": 1,
        "chunks_size": 1000,
        "fps": base_info.get("fps", 10),
        "splits": {
            "train": f"0[:{global_ep_idx}]"
        },
        "data_path": "data/chunk-000/episode_{episode_index:06d}.parquet",
        "video_path": "videos/{video_key}/episode_{episode_index:06d}.mp4",
        "features": base_info.get("features", {}),
    }
    with open(meta_out / "info.json", "w", encoding="utf-8") as f:
        json.dump(merged_info, f, indent=2)

    return LeRobotDataset(output_repo_id, root=out_root)
