"""Offline sanity check of the fine-tuned SmolVLA checkpoint (Week 3, T1 follow-up).

Loads the checkpoint, runs it on frames from C's dataset, and compares the
predicted action with the recorded (expert) action. A trained model should
beat the trivial baseline "always predict the dataset's mean action".

This does NOT prove the robot succeeds in closed loop; it only proves the
model learned something and that the checkpoint loads and runs.

Run (needs a GPU or a lot of patience on CPU; Kaggle/Colab is fine):
    python ai/offline_check.py \
        --checkpoint out/smolvla_run1 \
        --dataset out/second_look_v1 \
        --n 16

--checkpoint may be the folder you unzipped, or the pretrained_model folder
inside it; the script searches for config.json + model.safetensors.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch


def find_pretrained_dir(root: Path) -> Path:
    """Find the folder that holds config.json and model.safetensors."""
    cands = [root] + [p.parent for p in root.rglob("model.safetensors")]
    for c in cands:
        if (c / "config.json").exists() and (c / "model.safetensors").exists():
            return c
    sys.exit(f"No folder with config.json + model.safetensors under {root}")


def to_batch(sample: dict, device: str) -> dict:
    """Add a batch dim to tensors, keep strings as 1-item lists."""
    out = {}
    for k, v in sample.items():
        if isinstance(v, torch.Tensor):
            out[k] = v.unsqueeze(0).to(device)
        elif isinstance(v, str):
            out[k] = [v]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--dataset", default="out/second_look_v1")
    ap.add_argument("--n", type=int, default=16, help="frames to test")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--plot", default="offline_check.png")
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    ckpt = find_pretrained_dir(Path(args.checkpoint))
    print(f"device={device}  checkpoint={ckpt}")

    # Imports are inside main so a missing LeRobot gives a readable error.
    from lerobot.datasets.lerobot_dataset import LeRobotDataset
    from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy

    ds_root = Path(args.dataset)
    ds = LeRobotDataset(repo_id=f"local/{ds_root.name}", root=ds_root)
    print(f"dataset: {ds.num_episodes} episodes, {len(ds)} frames")

    policy = SmolVLAPolicy.from_pretrained(str(ckpt)).to(device).eval()

    # Newer LeRobot keeps normalisation in pre/post processors. Older keeps it
    # inside the policy. Support both.
    pre = post = None
    try:
        from lerobot.policies.factory import make_pre_post_processors

        pre, post = make_pre_post_processors(
            policy.config,
            pretrained_path=str(ckpt),
            dataset_stats=ds.meta.stats,
        )
        print("using pre/post processors")
    except Exception as e:  # noqa: BLE001
        print(f"no processors ({type(e).__name__}); using policy-internal normalisation")

    rng = np.random.default_rng(args.seed)
    idxs = sorted(rng.choice(len(ds), size=args.n, replace=False).tolist())

    preds, truth = [], []
    for i in idxs:
        sample = ds[i]
        batch = to_batch(sample, device)
        if pre is not None:
            batch = pre(batch)
        policy.reset()
        with torch.no_grad():
            act = policy.select_action(batch)
        if post is not None:
            act = post(act)
        preds.append(act.squeeze(0).float().cpu().numpy())
        truth.append(sample["action"].float().numpy())

    preds, truth = np.stack(preds), np.stack(truth)

    # Baseline: always predict the mean action over the whole dataset.
    all_actions = np.stack(
        [ds[j]["action"].float().numpy() for j in range(0, len(ds), max(1, len(ds) // 2000))]
    )
    baseline = np.broadcast_to(all_actions.mean(0), truth.shape)

    mae_model = np.abs(preds - truth).mean(0)
    mae_base = np.abs(baseline - truth).mean(0)

    print("\nper-dimension mean absolute error (lower is better)")
    print("dim   model    mean-baseline")
    for d, (m, b) in enumerate(zip(mae_model, mae_base)):
        print(f"{d:>3}  {m:7.4f}  {b:7.4f}")
    print(f"\nOVERALL  model={mae_model.mean():.4f}  baseline={mae_base.mean():.4f}")
    verdict = "learned something" if mae_model.mean() < mae_base.mean() else "NOT better than baseline"
    print(f"verdict: {verdict}")
    print("(dims 4 and 5 are roll/pitch, constant zero: ignore them)")

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        n_dim = truth.shape[1]
        fig, axes = plt.subplots(1, n_dim, figsize=(3 * n_dim, 3), sharex=True)
        for d, ax in enumerate(np.atleast_1d(axes)):
            ax.plot(truth[:, d], "o-", label="recorded")
            ax.plot(preds[:, d], "x--", label="predicted")
            ax.set_title(f"action dim {d}")
        np.atleast_1d(axes)[0].legend()
        fig.tight_layout()
        fig.savefig(args.plot, dpi=120)
        print(f"saved plot -> {args.plot}")
    except ImportError:
        print("matplotlib not installed; skipped plot")


if __name__ == "__main__":
    main()
