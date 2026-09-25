#!/usr/bin/env bash
# TEMPLATE - NOT TESTED. Read https://docs.nebius.com/serverless/jobs/manage first.
# Easiest first step: create ONE job in the web console (Serverless AI > Jobs > Create job > Custom,
# choose "no GPUs" for state-mode runs) and keep its settings. Or run `nebius ai create` for the guided flow.
#
# 1) Push your image to a registry the job can read (Docker Hub / GitHub Container Registry / Nebius Container Registry).
# 2) Fill in the <placeholders>, then:
nebius ai job create \
  --name second-look-eval-001 \
  --image <registry>/<user>/second-look-sim:latest \
  --container-command python \
  --args "sim/run_batch.py --scenario S3 --episodes 200 --seed-start 0 --policy ours" \
  --platform <platform-id-from-docs> \
  --preset <preset-from-docs> \
  --timeout 2h
# Follow the logs; print one line per episode that starts with RESULT, so you can save them with grep:
#   nebius ai job logs <job-id> --follow
#   nebius ai job logs <job-id> | grep '^RESULT,' > results/part-001.csv
# When finished: nebius ai job list  /  nebius ai job cancel <job-id>  /  nebius ai job delete <job-id>
