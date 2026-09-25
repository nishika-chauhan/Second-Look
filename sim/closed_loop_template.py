"""TEMPLATE - NOT TESTED (needs a GPU and a trained checkpoint). Role D owns this file.

Closed-loop test: load a fine-tuned policy, run it in SecondLookEnv, count successes.
The loop and the success check use the tested SecondLookEnv; the policy loading part is a sketch written from the
LeRobot docs - open https://huggingface.co/docs/lerobot/en/groot (or /smolvla) and fix the imports and calls.

    python sim/closed_loop_template.py --policy-path <hf_user>/groot_second_look --episodes 20
"""
import argparse
import os
import sys

os.environ.setdefault("MUJOCO_GL", "osmesa")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np                                    # noqa: E402

from expert import TASK_TEXT                          # noqa: E402
from world import OBJECTS, SecondLookEnv              # noqa: E402


def load_policy(path, device="cuda"):
    """Sketch: returns act(obs, task) -> np.ndarray of shape (chunk, 4). Check the LeRobot docs for exact names."""
    import torch
    from lerobot.policies.factory import make_pre_post_processors           # verify import path
    from lerobot.policies.pretrained import PreTrainedPolicy                 # verify import path
    policy = PreTrainedPolicy.from_pretrained(path).to(device).eval()
    pre, post = make_pre_post_processors(policy.config, path,
                                         preprocessor_overrides={"device_processor": {"device": device}})

    def act(obs, task):
        frame = {
            "observation.images.front": torch.from_numpy(obs["front"]).permute(2, 0, 1).float() / 255.0,
            "observation.images.wrist": torch.from_numpy(obs["wrist"]).permute(2, 0, 1).float() / 255.0,
            "observation.state": torch.from_numpy(obs["state"]),
            "task": task,
        }
        with torch.inference_mode():
            action = policy.select_action(pre(frame))     # one action per call (LeRobot keeps an internal chunk)
        return post(action).cpu().numpy().reshape(-1)     # -> [x, y, z, gripper]
    return act


def run(env, act, target, start, seed, max_steps=150):
    obs = env.reset(seed=seed, target=target, start=start)
    for t in range(max_steps):
        obs = env.step(act(obs, TASK_TEXT[target]), obs=True)
        if env.in_tray(target):
            return True, t + 1
    return False, max_steps


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy-path", required=True)
    ap.add_argument("--episodes", type=int, default=20)
    args = ap.parse_args()
    env, act = SecondLookEnv(render=True), load_policy(args.policy_path)
    ok = 0
    for i in range(args.episodes):
        target, start = OBJECTS[i % 3], ["home", "look_L", "look_R"][(i // 3) % 3]
        s, steps = run(env, act, target, start, seed=50_000 + i)
        ok += s
        print(f"episode {i:3d} {start:7s} {target:12s} success={s} steps={steps}")
    print(f"success {ok}/{args.episodes}")
