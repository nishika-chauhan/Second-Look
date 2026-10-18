"""Offline sanity check of the fine-tuned SmolVLA checkpoint (Week 3, T1 follow-up).

Loads the checkpoint, runs it on random frames from the training dataset and
compares the predicted action with the recorded (expert) action. A trained
model should beat the trivial baseline "always predict the dataset mean".

Run it with the Python that has LeRobot installed (the lr_env from training):

    !/kaggle/working/lr_env/bin/python /kaggle/working/offline_check.py

Defaults below are the Kaggle paths from the training notebook; override with
--checkpoint / --dataset if yours differ.

This does NOT prove the robot succeeds in closed loop. It only shows that the
checkpoint loads, runs, and learned something.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Jupyter sets MPLBACKEND to its inline backend, which does not exist inside
# the training venv. Force a file-only backend before matplotlib is imported.
os.environ["MPLBACKEND"] = "Agg"

import numpy as np
import torch

DEFAULT_CKPT = "/kaggle/input/models/globalgems/smolvla/other/default/1/smolvla_run1"
DEFAULT_DS = "/kaggle/input/datasets/globalgems/second-look-v2/second_look_v2"

# Same renaming used in training (lerobot-train --rename_map=...).
RENAME = {
    "observation.images.front": "observation.images.camera1",
    "observation.images.wrist": "observation.images.camera2",
}


def find_pretrained_dir(root: Path) -> Path:
    """Folder that holds config.json + model.safetensors (root or below it)."""
    if root.is_file():
        root = root.parent
    cands = [root] + [p.parent for p in root.rglob("model.safetensors")]
    for c in cands:
        if (c / "config.json").exists() and (c / "model.safetensors").exists():
            return c
    sys.exit(f"No folder with config.json + model.safetensors under {root}")


def to_batch(sample: dict, device: str) -> dict:
    """Rename cameras, add a batch dim to tensors, wrap strings in a list."""
    out = {}
    for k, v in sample.items():
        k = RENAME.get(k, k)
        if isinstance(v, torch.Tensor):
            out[k] = v.unsqueeze(0).to(device)
        elif isinstance(v, str):
            out[k] = [v]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default=DEFAULT_CKPT)
    ap.add_argument("--dataset", default=DEFAULT_DS)
    ap.add_argument("--n", type=int, default=16, help="frames to test")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--plot", default="offline_check.png")
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    ckpt = find_pretrained_dir(Path(args.checkpoint))
    print(f"device={device}\ncheckpoint={ckpt}\ndataset={args.dataset}")

    try:
        from lerobot.datasets import LeRobotDataset
    except ImportError:
        from lerobot.datasets.lerobot_dataset import LeRobotDataset
    from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy

    ds_root = Path(args.dataset)
    ds = LeRobotDataset(f"local/{ds_root.name}", root=ds_root, video_backend="pyav")
    print(f"dataset: {ds.num_episodes} episodes, {len(ds)} frames")

    policy = SmolVLAPolicy.from_pretrained(str(ckpt)).to(device).eval()

    # The final_model folder contains the saved pre/post processors
    # (normalisation stats included), so load those rather than rebuilding.
    from lerobot.policies.factory import make_pre_post_processors

    pre, post = make_pre_post_processors(policy.config, pretrained_path=str(ckpt))
    print("loaded saved pre/post processors")

    rng = np.random.default_rng(args.seed)
    idxs = sorted(rng.choice(len(ds), size=args.n, replace=False).tolist())

    preds, truth = [], []
    for i in idxs:
        sample = ds[i]
        batch = pre(to_batch(sample, device))
        policy.reset()
        with torch.no_grad():
            act = policy.select_action(batch)
        act = post(act)
        preds.append(act.squeeze(0).float().cpu().numpy())
        truth.append(sample["action"].float().numpy())

    preds, truth = np.stack(preds), np.stack(truth)

    # Baseline: always predict the dataset's mean action (from saved stats).
    mean_action = np.asarray(ds.meta.stats["action"]["mean"], dtype=np.float32).reshape(-1)
    baseline = np.broadcast_to(mean_action, truth.shape)

    mae_model = np.abs(preds - truth).mean(0)
    mae_base = np.abs(baseline - truth).mean(0)

    print("\nper-dimension mean absolute error (lower is better)")
    print("dim   model    mean-baseline")
    for d, (m, b) in enumerate(zip(mae_model, mae_base)):
        print(f"{d:>3}  {m:7.4f}  {b:7.4f}")
    # Dims 4 and 5 (roll/pitch) are constant zero, so leave them out of the verdict.
    keep = [d for d in range(truth.shape[1]) if d not in (3, 4)]
    m_all, b_all = mae_model[keep].mean(), mae_base[keep].mean()
    print(f"\nOVERALL (dims 0,1,2,5): model={m_all:.4f}  baseline={b_all:.4f}")
    print("verdict:", "learned something" if m_all < b_all else "NOT better than baseline")

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
        print("matplotlib not installed in this env; skipped plot")


if __name__ == "__main__":
    main()
