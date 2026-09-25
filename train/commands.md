# Training commands (copied from the official docs on 20 Sep 2026 - versions move, re-check them)

Everything here is TEMPLATE / NOT TESTED by us: it needs a GPU with 40 GB+ VRAM (GR00T) and access to the gated
Hugging Face model nvidia/Cosmos-Reason2-2B (request access first, then `hf auth login`).

## A) GR00T N1.7 through LeRobot  (recommended first try)
    pip install "lerobot[training]"
    hf auth login ; wandb login
    lerobot-train \
      --dataset.repo_id=<your_hf_user>/second_look_v1 \
      --dataset.image_transforms.enable=true \
      --policy.type=groot \
      --policy.device=cuda \
      --policy.base_model_path=nvidia/GR00T-N1.7-3B \
      --policy.embodiment_tag=new_embodiment \
      --policy.chunk_size=16 --policy.n_action_steps=16 \
      --batch_size=32 --steps=10000 --save_freq=2000 \
      --policy.tune_diffusion_model=false \
      --output_dir=outputs/train/groot_second_look --job_name=groot_second_look --wandb.enable=true
Docs: https://huggingface.co/docs/lerobot/en/groot

## B) GR00T N1.7 with NVIDIA's own repo (reference implementation, needs LeRobot v2-flavoured data)
    # v3 -> v2 conversion helper lives in scripts/lerobot_conversion/convert_v3_to_v2.py
    uv run python gr00t/experiment/launch_finetune.py \
      --base-model-path nvidia/GR00T-N1.7-3B \
      --dataset-path <dataset-dir> --embodiment-tag NEW_EMBODIMENT \
      --modality-config-path <dataset-dir>/new_embodiment_config_defaults.py \
      --num-gpus 1 --output-dir <output-dir> \
      --max-steps 10000 --save-steps 2000 --global-batch-size 32 --dataloader-num-workers 4
Docs: https://github.com/NVIDIA/Isaac-GR00T  (getting_started/finetune_new_embodiment.md)

## C) SmolVLA (cheap fallback / second baseline, trains on one modest GPU)
    pip install "lerobot[smolvla]"
    lerobot-train \
      --policy.path=lerobot/smolvla_base \
      --dataset.repo_id=<your_hf_user>/second_look_v1 \
      --batch_size=64 --steps=20000 \
      --output_dir=outputs/train/smolvla_second_look --job_name=smolvla_second_look \
      --policy.device=cuda --wandb.enable=true
Docs: https://huggingface.co/docs/lerobot/en/smolvla

## Day-1 smoke test (do this BEFORE generating big data)
Fine-tune for a few hundred steps on a tiny dataset (the GR00T repo ships demo_data/cube_to_bowl_5, 5 episodes;
or use the 6-episode dataset from sim/make_dataset.py). You are testing the toolchain, not the accuracy.
