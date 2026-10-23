"""Closed-loop rollout of the fine-tuned SmolVLA in the MuJoCo sim (role B, Tier 1 skill test).

Runs N episodes with seeds that were NOT used for training, lets the policy
drive SecondLookEnv, and reports success with a 95% confidence interval, split
by target object and start pose. `--policy expert` runs C's scripted expert on
the same seeds, which gives the "executor gap" comparison from plan Part 7.

Interface facts (from D's reading of sim/world.py and C's export script):
  env.reset(seed, target, start) -> obs dict {state(4), front, wrist}
  env.step([x, y, z, gripper], obs=True) -> obs   (absolute xyz in metres, 10 Hz,
                                                   gripper < 0.5 closes)
  env.in_tray(target) -> bool                     (success)
  The dataset (and so the policy) is 6-dim: [x, y, z, 0, 0, gripper], so we pad
  the state going in and take dims 0, 1, 2, 5 of the action coming out.

Run from the repo root, with the Python that has lerobot AND mujoco installed:
    MUJOCO_GL=osmesa python ai/rollout.py --checkpoint /path/to/final_model --episodes 3
    MUJOCO_GL=osmesa python ai/rollout.py --checkpoint /path/to/final_model --episodes 60
    MUJOCO_GL=osmesa python ai/rollout.py --policy expert --episodes 60      # same seeds

Pure helpers are tested in ai/tests/test_rollout.py (no sim or GPU needed).
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

STARTS = ["home", "look_L", "look_R"]
# Same cycling as C's export script, so every target/start combination is covered evenly.
RENAME = {"front": "observation.images.camera1", "wrist": "observation.images.camera2"}


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def state4_to_6(s4) -> np.ndarray:
    s4 = np.asarray(s4, dtype=np.float32).reshape(-1)
    assert s4.shape == (4,), f"expected 4-dim sim state, got {s4.shape}"
    return np.array([s4[0], s4[1], s4[2], 0.0, 0.0, s4[3]], dtype=np.float32)


def action6_to_4(a6) -> np.ndarray:
    a6 = np.asarray(a6, dtype=np.float32).reshape(-1)
    assert a6.shape == (6,), f"expected 6-dim policy action, got {a6.shape}"
    return np.array([a6[0], a6[1], a6[2], float(np.clip(a6[5], 0.0, 1.0))], dtype=np.float32)


def seed_to_case(seed: int, objects) -> tuple[str, str]:
    """(target, start) for a seed; identical cycling to export_lerobot_v3.py."""
    return objects[seed % 3], STARTS[(seed // 3) % 3]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for k successes out of n."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def run_episode(env, act_fn, seed: int, target: str, start: str, task: str,
                max_steps: int = 400) -> dict:
    """One closed-loop episode. act_fn(obs, task) -> 4-vector [x, y, z, gripper]."""
    obs = env.reset(seed=seed, target=target, start=start)
    if hasattr(act_fn, "reset"):
        act_fn.reset()
    lat, success, steps = [], False, 0
    for steps in range(1, max_steps + 1):
        t0 = time.perf_counter()
        a4 = act_fn(obs, task)
        lat.append((time.perf_counter() - t0) * 1000)
        obs = env.step([float(v) for v in a4], obs=True)
        if env.in_tray(target):
            success = True
            break
    final = None
    if hasattr(env, "obj_pos"):          # ground truth: scoring only, never shown to the policy
        try:
            final = [round(float(v), 3) for v in env.obj_pos(target)]
        except Exception:
            final = None
    return {
        "seed": seed, "target": target, "start": start, "success": int(success),
        "steps": steps, "sim_seconds": round(steps / 10.0, 1),
        "mean_policy_ms": round(float(np.mean(lat)), 1) if lat else 0.0,
        "max_policy_ms": round(float(np.max(lat)), 1) if lat else 0.0,
        "final_obj_pos": final,
    }


def summarize(rows: list) -> list[str]:
    def line(name, sub):
        k, n = sum(r["success"] for r in sub), len(sub)
        lo, hi = wilson(k, n)
        return f"{name:<18} {k:>3}/{n:<3} = {k / n:6.1%}   95% CI [{lo:.1%}, {hi:.1%}]" if n else f"{name:<18} no episodes"

    out = [line("ALL", rows)]
    for key in ("target", "start"):
        for v in sorted({r[key] for r in rows}):
            out.append(line(f"{key}={v}", [r for r in rows if r[key] == v]))
    return out


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------

class SmolVLARunner:
    """Wraps the checkpoint the same way ai/offline_check.py did (that check passed)."""

    def __init__(self, checkpoint: str, device: str | None = None,
                 n_action_steps: int | None = None):
        import torch
        from lerobot.policies.factory import make_pre_post_processors
        from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy

        self.torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        ckpt = Path(checkpoint)
        if ckpt.is_file():
            ckpt = ckpt.parent
        self.policy = SmolVLAPolicy.from_pretrained(str(ckpt)).to(self.device).eval()
        self.pre, self.post = make_pre_post_processors(self.policy.config, pretrained_path=str(ckpt))
        cfg = self.policy.config
        print(f"policy chunk_size={getattr(cfg, 'chunk_size', '?')} "
              f"n_action_steps={getattr(cfg, 'n_action_steps', '?')}")
        if n_action_steps is not None:
            # execute only the first N actions of each predicted chunk, then re-plan
            cfg.n_action_steps = int(n_action_steps)
            self.policy.reset()
            print(f"n_action_steps overridden to {cfg.n_action_steps}")

    def reset(self) -> None:
        self.policy.reset()          # clears the queued action chunk between episodes

    def _img(self, arr):
        t = self.torch.from_numpy(np.ascontiguousarray(arr)).permute(2, 0, 1).float() / 255.0
        return t.unsqueeze(0).to(self.device)

    def __call__(self, obs, task: str) -> np.ndarray:
        torch = self.torch
        batch = {
            RENAME["front"]: self._img(obs["front"]),
            RENAME["wrist"]: self._img(obs["wrist"]),
            "observation.state": torch.from_numpy(state4_to_6(obs["state"])).unsqueeze(0).to(self.device),
            "task": [task],
        }
        batch = self.pre(batch)
        with torch.no_grad():
            act = self.policy.select_action(batch)
        act = self.post(act)
        return action6_to_4(act.squeeze(0).float().cpu().numpy())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _import_sim(repo: Path):
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(repo / "sim"))
    try:
        from sim.world import OBJECTS, SecondLookEnv
        from sim.expert import TASK_TEXT, run_expert
    except ImportError:
        from world import OBJECTS, SecondLookEnv       # type: ignore
        from expert import TASK_TEXT, run_expert       # type: ignore
    return SecondLookEnv, OBJECTS, TASK_TEXT, run_expert


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", choices=["smolvla", "expert"], default="smolvla")
    ap.add_argument("--checkpoint", help="final_model folder (config.json + model.safetensors)")
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parent.parent),
                    help="repo root containing sim/ (default: parent of ai/)")
    ap.add_argument("--episodes", type=int, default=3)
    ap.add_argument("--seed0", type=int, default=100000,
                    help="first seed. Keep it far from the training seeds (C generated from small seeds)")
    ap.add_argument("--max-steps", type=int, default=400, help="10 Hz, so 400 = 40 simulated seconds")
    ap.add_argument("--n-action-steps", type=int, default=None,
                    help="re-plan every N steps instead of the checkpoint default (try 10)")
    ap.add_argument("--out", default="rollout_results.csv")
    args = ap.parse_args()

    SecondLookEnv, OBJECTS, TASK_TEXT, run_expert = _import_sim(Path(args.repo))
    env = SecondLookEnv(render=True, img=224, randomize=True)

    runner = None
    if args.policy == "smolvla":
        if not args.checkpoint:
            sys.exit("--checkpoint is required for --policy smolvla")
        runner = SmolVLARunner(args.checkpoint, n_action_steps=args.n_action_steps)
        print(f"loaded {args.checkpoint} on {runner.device}")

    rows = []
    for i in range(args.episodes):
        seed = args.seed0 + i
        target, start = seed_to_case(seed, OBJECTS)
        task = TASK_TEXT[target]
        t0 = time.time()
        if args.policy == "expert":
            env.reset(seed=seed, target=target, start=start)
            ok, frames = run_expert(env, target, np.random.default_rng(10_000 + seed))
            row = {"seed": seed, "target": target, "start": start, "success": int(bool(ok)),
                   "steps": len(frames), "sim_seconds": round(len(frames) / 10.0, 1),
                   "mean_policy_ms": 0.0, "max_policy_ms": 0.0, "final_obj_pos": None}
        else:
            row = run_episode(env, runner, seed, target, start, task, args.max_steps)
        row["policy"] = args.policy
        row["wall_s"] = round(time.time() - t0, 1)
        rows.append(row)
        print(f"RESULT policy={args.policy} seed={seed} target={target} start={start} "
              f"success={row['success']} steps={row['steps']} sim_s={row['sim_seconds']} "
              f"policy_ms={row['mean_policy_ms']} wall_s={row['wall_s']}", flush=True)

    print()
    for line in summarize(rows):
        print(line)
    fields = ["policy", "seed", "target", "start", "success", "steps", "sim_seconds",
              "mean_policy_ms", "max_policy_ms", "wall_s", "final_obj_pos"]
    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"\nsaved {args.out}")


if __name__ == "__main__":
    main()
