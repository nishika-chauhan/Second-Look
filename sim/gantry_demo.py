"""Level-3 demo: a gantry robot picks the red cup and places it somewhere else.

Run:            python sim/gantry_demo.py
Save a video:   python sim/gantry_demo.py --video out/demo.mp4     (needs rendering, see README)

Tested with MuJoCo 3.13.0. The grasp is *kinematic*: while "attached", the object simply follows
the gripper. Everything else (gravity, contacts, the gantry motors) is real physics.
Say so honestly in your README.
"""
import argparse
import os
import time

import mujoco
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
model = mujoco.MjModel.from_xml_path(os.path.join(HERE, "scene.xml"))
data = mujoco.MjData(model)
mujoco.mj_forward(model, data)


def bid(n): return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, n)
def sid(n): return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, n)
def jid(n): return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n)
def gid(n): return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, n)


GRIP = sid("grip")
Z_HOME = 0.14    # height of the grip site when the z-joint is at 0
Z_SAFE = 0.30    # travel height (above the screen, which is 0.18 tall)


def grip_pos():
    return data.site_xpos[GRIP].copy()


def obj_pos(n):
    """Ground-truth position of an object (use it for scoring, not for the robot's belief)."""
    return data.xpos[bid(n)].copy()


# ---------- optional video recording ----------
frames, renderer, step_count, RECORD_EVERY = [], None, 0, 33   # 33 steps of 2 ms ~ 15 frames per second

# ---------- kinematic grasp ----------
attached = None


def _set_collide(name, on):
    g = gid(name + "_g")
    model.geom_contype[g] = 1 if on else 0
    model.geom_conaffinity[g] = 1 if on else 0


def attach(name):
    global attached
    attached = name
    _set_collide(name, False)          # no collisions while carried (avoids "explosions")


def release():
    global attached
    _set_collide(attached, True)
    attached = None


def step(n=1):
    global step_count
    for _ in range(n):
        if attached is not None:
            j = jid(attached + "_j")
            qa, da = model.jnt_qposadr[j], model.jnt_dofadr[j]
            data.qpos[qa:qa + 3] = grip_pos() + np.array([0, 0, -0.03])   # hold just below the fingertips
            data.qvel[da:da + 6] = 0
        mujoco.mj_step(model, data)
        step_count += 1
        if renderer is not None and step_count % RECORD_EVERY == 0:
            renderer.update_scene(data, camera="front")
            frames.append(renderer.render().copy())


def goto(x, y, z, tol=0.004, max_steps=4000):
    """Drive the gantry so the grip site reaches (x, y, z). Returns False if it times out."""
    data.ctrl[0], data.ctrl[1], data.ctrl[2] = x, y, z - Z_HOME
    for _ in range(max_steps):
        step()
        if np.linalg.norm(grip_pos() - np.array([x, y, z])) < tol:
            return True
    return False


def pick(name):
    p = obj_pos(name)
    if not (goto(p[0], p[1], Z_SAFE) and goto(p[0], p[1], p[2] + 0.03)):
        return False
    attach(name)
    return goto(p[0], p[1], Z_SAFE)


def place(x, y, z_rest):
    if not (goto(x, y, Z_SAFE) and goto(x, y, z_rest + 0.03)):
        return False
    release()
    step(500)                          # let it settle on the table
    return goto(x, y, Z_SAFE)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=None)
    args = ap.parse_args()
    if args.video:
        renderer = mujoco.Renderer(model, height=480, width=640)
    t0 = time.time()
    print("initial cup_red:", obj_pos("cup_red").round(3))
    ok1 = pick("cup_red")
    ok2 = place(0.15, -0.20, 0.04)
    print("pick ok:", ok1, "| place ok:", ok2)
    print("final cup_red :", obj_pos("cup_red").round(3), "(target is about [0.15 -0.2 0.04])")
    print("sim time %.1f s, wall time %.2f s" % (data.time, time.time() - t0))
    if args.video:
        import imageio.v2 as imageio
        os.makedirs(os.path.dirname(os.path.abspath(args.video)), exist_ok=True)
        imageio.mimsave(args.video, frames, fps=15)
        print("saved", args.video, len(frames), "frames")
