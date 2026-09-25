#!/usr/bin/env bash
# TEMPLATE - NOT TESTED. Read https://docs.nebius.com/serverless/jobs/manage first.
# One GPU job that fine-tunes GR00T with LeRobot. Create your container image first (CUDA + lerobot[training]).
# Pass secrets with --env-secret, never bake them into the image. Fill the <placeholders> from the docs / console.
nebius ai job create \
  --name groot-finetune-001 \
  --image <registry>/<user>/second-look-train:latest \
  --container-command bash \
  --args "-lc 'lerobot-train --dataset.repo_id=<hf_user>/second_look_v1 --policy.type=groot --policy.base_model_path=nvidia/GR00T-N1.7-3B --policy.embodiment_tag=new_embodiment --policy.chunk_size=16 --policy.n_action_steps=16 --batch_size=32 --steps=10000 --save_freq=2000 --output_dir=/output/groot'" \
  --platform <gpu-platform-id> --preset <1-gpu-preset> \
  --disk-size 300GiB --timeout 8h
# Follow: nebius ai job logs <job-id> --follow      Stop early: nebius ai job cancel <job-id>
