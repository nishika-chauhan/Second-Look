"""Sanity check: the scripted expert should succeed in (almost) every randomised episode. Tested.

    python sim/check_expert.py            # 30 episodes, no rendering, takes a few seconds
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np                        # noqa: E402

from expert import run_expert             # noqa: E402
from world import OBJECTS, SecondLookEnv  # noqa: E402

env = SecondLookEnv(render=False)
ok, lengths, t0 = 0, [], time.time()
for seed in range(30):
    target = OBJECTS[seed % 3]
    start = ["home", "look_L", "look_R"][(seed // 3) % 3]
    env.reset(seed=seed, target=target, start=start)
    visible = env.front_visible(target)
    assert visible == (start == "home"), "home starts need a visible target, look starts a hidden one"
    success, frames = run_expert(env, target, np.random.default_rng(seed), record=True)
    ok += success
    lengths.append(len(frames))
print(f"expert success {ok}/30 | steps per episode: mean {np.mean(lengths):.0f}, "
      f"min {min(lengths)}, max {max(lengths)} | {time.time() - t0:.1f} s")
