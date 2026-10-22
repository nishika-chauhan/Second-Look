"""
pytest for the pure helpers and the episode loop in ai/rollout.py.
Uses a fake environment, so no MuJoCo, GPU or checkpoint is needed.

    pytest ai/tests/test_rollout.py -v
"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import rollout as R

OBJECTS = ["cup_red", "bottle_blue", "box_green"]


class FakeEnv:
    """Succeeds once `succeed_at` steps have been taken (None = never)."""

    def __init__(self, succeed_at=None):
        self.succeed_at, self.n, self.actions, self.reset_args = succeed_at, 0, [], None

    def _obs(self):
        return {"state": np.zeros(4, np.float32),
                "front": np.zeros((224, 224, 3), np.uint8),
                "wrist": np.zeros((224, 224, 3), np.uint8)}

    def reset(self, seed, target, start):
        self.n, self.actions, self.reset_args = 0, [], (seed, target, start)
        return self._obs()

    def step(self, action, obs=False):
        self.n += 1
        self.actions.append(action)
        return self._obs() if obs else None

    def in_tray(self, target):
        return self.succeed_at is not None and self.n >= self.succeed_at

    def obj_pos(self, target):
        return (0.1, 0.2, 0.0)


def const_policy(obs, task):
    return np.array([0.0, -0.28, 0.30, 1.0], dtype=np.float32)


# --- 4 <-> 6 dimension mapping ------------------------------------------------

def test_state_padding_matches_export_script():
    s6 = R.state4_to_6([0.1, 0.2, 0.3, 1.0])
    assert s6.tolist() == pytest.approx([0.1, 0.2, 0.3, 0.0, 0.0, 1.0])
    assert s6.dtype == np.float32


def test_action_takes_xyz_and_gripper():
    a4 = R.action6_to_4([0.1, 0.2, 0.3, 9.9, 9.9, 0.7])
    assert a4.tolist() == pytest.approx([0.1, 0.2, 0.3, 0.7])


def test_gripper_is_clipped_to_unit_range():
    assert R.action6_to_4([0, 0, 0, 0, 0, 1.6])[3] == 1.0
    assert R.action6_to_4([0, 0, 0, 0, 0, -0.4])[3] == 0.0


def test_wrong_sizes_rejected():
    with pytest.raises(AssertionError):
        R.state4_to_6([1, 2, 3])
    with pytest.raises(AssertionError):
        R.action6_to_4([1, 2, 3, 4])


# --- seed cycling and statistics ---------------------------------------------

def test_seed_cycling_matches_export_script():
    # export_lerobot_v3.py: target = OBJECTS[seed % 3]; start = [...][(seed // 3) % 3]
    assert R.seed_to_case(0, OBJECTS) == ("cup_red", "home")
    assert R.seed_to_case(1, OBJECTS) == ("bottle_blue", "home")
    assert R.seed_to_case(3, OBJECTS) == ("cup_red", "look_L")
    assert R.seed_to_case(8, OBJECTS) == ("box_green", "look_R")
    assert R.seed_to_case(9, OBJECTS) == ("cup_red", "home")


def test_wilson_known_values():
    lo, hi = R.wilson(8, 10)
    assert lo == pytest.approx(0.490, abs=0.005) and hi == pytest.approx(0.943, abs=0.005)
    assert R.wilson(0, 10)[0] == 0.0 and R.wilson(10, 10)[1] == 1.0
    assert R.wilson(0, 0) == (0.0, 0.0)


def test_wilson_interval_narrows_with_more_episodes():
    w10, w200 = R.wilson(5, 10), R.wilson(100, 200)
    assert (w200[1] - w200[0]) < (w10[1] - w10[0])


def test_summarize_groups_by_target_and_start():
    rows = [
        {"success": 1, "target": "cup_red", "start": "home"},
        {"success": 0, "target": "cup_red", "start": "look_L"},
        {"success": 1, "target": "box_green", "start": "home"},
    ]
    text = "\n".join(R.summarize(rows))
    assert "ALL" in text and "2/3" in text
    assert "target=cup_red" in text and "start=look_L" in text


# --- episode loop -------------------------------------------------------------

def test_episode_success_stops_early():
    env = FakeEnv(succeed_at=12)
    r = R.run_episode(env, const_policy, seed=5, target="cup_red", start="home", task="t", max_steps=100)
    assert r["success"] == 1 and r["steps"] == 12 and env.n == 12
    assert r["sim_seconds"] == 1.2


def test_episode_failure_hits_step_cap():
    env = FakeEnv(succeed_at=None)
    r = R.run_episode(env, const_policy, seed=5, target="cup_red", start="home", task="t", max_steps=30)
    assert r["success"] == 0 and r["steps"] == 30


def test_reset_receives_seed_target_start():
    env = FakeEnv(succeed_at=1)
    R.run_episode(env, const_policy, seed=77, target="box_green", start="look_R", task="t")
    assert env.reset_args == (77, "box_green", "look_R")


def test_actions_are_plain_floats_of_length_four():
    env = FakeEnv(succeed_at=3)
    R.run_episode(env, const_policy, seed=1, target="cup_red", start="home", task="t")
    assert all(len(a) == 4 and all(type(v) is float for v in a) for a in env.actions)


def test_policy_reset_called_each_episode():
    class P:
        resets = 0

        def reset(self):
            P.resets += 1

        def __call__(self, obs, task):
            return np.zeros(4, np.float32)

    for s in (1, 2):
        R.run_episode(FakeEnv(succeed_at=1), P(), seed=s, target="cup_red", start="home", task="t")
    assert P.resets == 2


def test_ground_truth_logged_but_task_text_passed_through():
    seen = {}

    def spy(obs, task):
        seen["task"] = task
        return np.zeros(4, np.float32)

    r = R.run_episode(FakeEnv(succeed_at=1), spy, seed=1, target="cup_red", start="home",
                      task="pick up the red cup and place it in the tray")
    assert seen["task"] == "pick up the red cup and place it in the tray"
    assert r["final_obj_pos"] == [0.1, 0.2, 0.0]
