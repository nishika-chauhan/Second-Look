"""Scripted expert: it knows the true object position (privileged) and produces clean demonstrations.

It is used for two things: (1) to generate training data for the VLA, (2) as the "perfect executor" baseline
in the evaluation (so you can separate memory mistakes from VLA mistakes).
Only call it when the target is VISIBLE to the robot (front camera or wrist camera) - otherwise the demo would
teach the VLA to guess things it cannot see.
"""
import numpy as np

from world import MAX_STEP, REST_Z, TRAY_XY, Z_SAFE

TASK_TEXT = {
    "cup_red": "pick up the red cup and place it in the tray",
    "bottle_blue": "pick up the blue bottle and place it in the tray",
    "box_green": "pick up the green box and place it in the tray",
}


def run_expert(env, target, rng, record=True):
    """Runs one pick-and-place. Returns (success, frames); frames = list of (obs_before_action, action)."""
    frames = []

    def act(a):
        if record:
            frames.append((env.obs(), np.array(a, dtype=np.float32)))
        env.step(a)

    def move(wp, g, speed, tol=0.006, max_steps=90):
        for _ in range(max_steps):
            cur = env.grip_pos(); err = np.asarray(wp, float) - cur
            if np.linalg.norm(err) < tol:
                return
            act([*(cur + np.clip(err, -MAX_STEP * speed, MAX_STEP * speed)), g])

    def hold(pos, g, n):
        for _ in range(n):
            act([*pos, g])

    p = env.obj_pos(target)
    jit = rng.normal(0, 0.003, 2)
    speed = rng.uniform(0.6, 1.0)
    zs = Z_SAFE + rng.uniform(-0.03, 0.02)
    grasp_z = REST_Z[target] + 0.03
    move([p[0] + jit[0], p[1] + jit[1], zs], 1.0, speed)                 # above the object
    move([p[0] + jit[0], p[1] + jit[1], grasp_z], 1.0, speed)            # go down
    cur = env.grip_pos()
    hold(cur, 0.0, int(rng.integers(4, 7)))                              # close the gripper
    move([cur[0], cur[1], zs], 0.0, speed)                               # lift
    move([TRAY_XY[0] + jit[0], TRAY_XY[1] + jit[1], zs], 0.0, speed)     # over the tray
    move([TRAY_XY[0] + jit[0], TRAY_XY[1] + jit[1], 0.07], 0.0, speed)   # down
    cur = env.grip_pos()
    hold(cur, 1.0, 4)                                                    # open
    move([cur[0], cur[1], zs], 1.0, speed)                               # back up
    return env.in_tray(target), frames
