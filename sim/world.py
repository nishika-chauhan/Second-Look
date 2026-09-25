"""SecondLookEnv - the MuJoCo world for the VLA edition of the project (role C and D share this file).

What it gives you
  * a table with 3 objects (cup_red, bottle_blue, box_green), a painted tray, and TWO screens that hide objects
  * a gantry robot: you command an absolute target [x, y, z, gripper] every 0.1 s (10 Hz)
  * two cameras: "front" (fixed, can be blocked by the screens) and "wrist" (on the robot head, looks down)
  * a gripper state in [0, 1]: 1 = open, 0.4 = closed on an object, 0 = closed on nothing (grasp failed!)
  * ground truth (object positions, who is hidden) for scoring - never show it to the policy

Honesty note for your README: the grasp is kinematic. When the gripper closes near an object it "attaches";
everything else (gravity, contacts, motors) is real physics.

Tested with MuJoCo 3.13.0 (Python 3.12). Rendering: MUJOCO_GL=osmesa on Linux without a display.
"""
import os

import mujoco
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OBJECTS = ["cup_red", "bottle_blue", "box_green"]
REST_Z = {"cup_red": 0.04, "bottle_blue": 0.035, "box_green": 0.02}
Z_SAFE = 0.30                      # travel height
Z_HOME_JOINT = 0.14                # height of the grip site when the z-joint is 0
HOME = np.array([0.0, -0.28, Z_SAFE])
TRAY_XY = np.array([0.0, -0.22])
TRAY_HALF = np.array([0.07, 0.05])
MAX_STEP = 0.04                    # metres per control step = 0.4 m/s at 10 Hz
SUBSTEPS = 50                      # 50 x 2 ms = 0.1 s per control step
CAM_POS = np.array([0.0, -0.85, 0.55])
LOW, HIGH = np.array([-0.45, -0.28, -0.05]), np.array([0.45, 0.30, 0.42])


def _slab_hit(p0, p1, bmin, bmax):
    """Does the segment p0->p1 pass through the axis-aligned box [bmin, bmax]?"""
    d, tmin, tmax = p1 - p0, 0.0, 1.0
    for i in range(3):
        if abs(d[i]) < 1e-12:
            if p0[i] < bmin[i] or p0[i] > bmax[i]:
                return False
        else:
            t1, t2 = (bmin[i] - p0[i]) / d[i], (bmax[i] - p0[i]) / d[i]
            if t1 > t2:
                t1, t2 = t2, t1
            tmin, tmax = max(tmin, t1), min(tmax, t2)
            if tmin > tmax:
                return False
    return True


class SecondLookEnv:
    def __init__(self, render=True, img=224):
        self.m = mujoco.MjModel.from_xml_path(os.path.join(HERE, "scene_v2.xml"))
        self.d = mujoco.MjData(self.m)
        self.render, self.img = render, img
        self.r = mujoco.Renderer(self.m, height=img, width=img) if render else None
        self.opt_wrist = mujoco.MjvOption()             # the wrist camera does not draw the gantry frame
        self.opt_wrist.geomgroup[1] = 0
        gid = lambda n: mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_GEOM, n)
        self.screen_geoms = {"L": gid("screen_left_g"), "R": gid("screen_right_g")}
        self.grip_site = mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_SITE, "grip")
        self.bid = {n: mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_BODY, n) for n in OBJECTS}
        self.jadr = {n: self.m.jnt_qposadr[mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_JOINT, n + "_j")]
                     for n in OBJECTS}
        self.gid = {n: gid(n + "_g") for n in OBJECTS}
        self.jdof = {n: self.m.jnt_dofadr[mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_JOINT, n + "_j")]
                     for n in OBJECTS}
        self.slide = {k: self.m.jnt_qposadr[mujoco.mj_name2id(self.m, mujoco.mjtObj.mjOBJ_JOINT, k)]
                      for k in ("gx", "gy", "gz")}
        self.attached, self.grip, self.t, self.target = None, 1.0, 0, None

    # ---------------------------------------------------------------- geometry helpers
    def grip_pos(self):
        return self.d.site_xpos[self.grip_site].copy()

    def obj_pos(self, name):
        return self.d.xpos[self.bid[name]].copy()

    def hide_center(self, k):
        """Centre of the zone hidden behind screen 'L' or 'R' (as seen from the front camera)."""
        sx = self.m.geom_pos[self.screen_geoms[k]][0]
        return np.array([sx * 1.14, 0.14])

    def front_visible_pos(self, p):
        """True if the front camera has a clear line of sight to point p (both screens are checked)."""
        for g in self.screen_geoms.values():
            c, s = self.m.geom_pos[g], self.m.geom_size[g]
            if _slab_hit(CAM_POS, np.asarray(p, float), c - s, c + s):
                return False
        return True

    def front_visible(self, name):
        return self.front_visible_pos(self.obj_pos(name))

    def wrist_sees(self, name):
        """Rough test: is the object inside the footprint of the down-looking wrist camera?"""
        g = self.grip_pos(); p = self.obj_pos(name)
        cam_z = g[2] + 0.06
        radius = max(cam_z - p[2], 0.0) * np.tan(np.radians(25.0)) * 0.95
        return bool(np.abs(p[:2] - g[:2]).max() <= radius)

    def in_tray(self, name):
        p = self.obj_pos(name)
        return bool(np.all(np.abs(p[:2] - TRAY_XY) <= TRAY_HALF) and p[2] < 0.06 and self.attached is None)

    # ---------------------------------------------------------------- reset
    def _sample_xy(self, rng, hidden, region, others):
        for _ in range(300):
            if hidden:
                k = region or str(rng.choice(["L", "R"]))
                x, y = self.hide_center(k)[0] + rng.uniform(-0.06, 0.06), rng.uniform(0.09, 0.19)
            elif rng.random() < 0.6:
                x, y = rng.uniform(-0.40, 0.40), rng.uniform(-0.15, -0.06)
            else:
                x, y = rng.uniform(-0.07, 0.07), rng.uniform(0.06, 0.20)
            p = np.array([x, y])
            if any(np.linalg.norm(p - q) < 0.08 for q in others):
                continue
            if self.front_visible_pos([x, y, 0.04]) == hidden:
                continue
            return p
        raise RuntimeError("could not place an object")

    def _put(self, name, xy):
        a = self.jadr[name]
        self.d.qpos[a:a + 3] = [xy[0], xy[1], REST_Z[name]]
        self.d.qpos[a + 3:a + 7] = [1, 0, 0, 0]

    def set_gantry(self, xyz, g=1.0):
        self.d.qpos[self.slide["gx"]], self.d.qpos[self.slide["gy"]] = xyz[0], xyz[1]
        self.d.qpos[self.slide["gz"]] = xyz[2] - Z_HOME_JOINT
        self.d.ctrl[:] = [xyz[0], xyz[1], xyz[2] - Z_HOME_JOINT]
        self.grip = g

    def reset(self, seed=0, target="cup_red", start="home"):
        """start: 'home' (target visible from the front) | 'look_L' | 'look_R' (target hidden behind that
        screen, robot already hovering above it - like after a 'look')."""
        rng = np.random.default_rng(seed)
        mujoco.mj_resetData(self.m, self.d)
        self.attached, self.target, self.t = None, target, 0
        for g in self.screen_geoms.values():
            self.m.geom_contype[g] = 1
        self.m.geom_pos[self.screen_geoms["L"]][0] = -0.22 + rng.uniform(-0.03, 0.03)
        self.m.geom_pos[self.screen_geoms["R"]][0] = 0.22 + rng.uniform(-0.03, 0.03)
        for n in OBJECTS:                                   # make sure collisions are on again
            self.m.geom_contype[self.gid[n]] = 1; self.m.geom_conaffinity[self.gid[n]] = 1
        placed = []
        order = [target] + [n for n in OBJECTS if n != target]
        for n in order:
            if n == target:
                hidden, region = start.startswith("look"), (start[-1] if start.startswith("look") else None)
            else:
                hidden, region = bool(rng.random() < 0.4), None
            xy = self._sample_xy(rng, hidden, region, placed)
            placed.append(xy); self._put(n, xy)
        if start.startswith("look"):
            c = self.hide_center(start[-1]); self.set_gantry([c[0], c[1], Z_SAFE])
        else:
            self.set_gantry(HOME)
        mujoco.mj_forward(self.m, self.d)
        for _ in range(200):                                # let the objects settle
            mujoco.mj_step(self.m, self.d)
        return self.obs()

    def move_object(self, name, xy):
        """Scenario helper: a 'person' moves an object while nobody is looking."""
        self._put(name, xy)
        self.d.qvel[self.jdof[name]:self.jdof[name] + 6] = 0
        mujoco.mj_forward(self.m, self.d)

    # ---------------------------------------------------------------- stepping
    def _attach(self, name):
        self.attached = name
        self.m.geom_contype[self.gid[name]] = 0; self.m.geom_conaffinity[self.gid[name]] = 0

    def _release(self):
        n, self.attached = self.attached, None
        self.m.geom_contype[self.gid[n]] = 1; self.m.geom_conaffinity[self.gid[n]] = 1

    def _graspable(self):
        g, best, bd = self.grip_pos(), None, 1e9
        for n in OBJECTS:
            p = self.obj_pos(n); h = np.linalg.norm(p[:2] - g[:2]); v = g[2] - p[2]
            if h <= 0.035 and 0.0 <= v <= 0.07 and h < bd:
                best, bd = n, h
        return best

    def step(self, action, obs=False):
        """action = [x, y, z, gripper] absolute target; gripper < 0.5 means 'close'.
        Rendering is slow, so step() only returns an observation if you ask for it (obs=True)."""
        a = np.asarray(action, dtype=np.float64)
        cur = self.grip_pos()
        tgt = np.clip(cur + np.clip(a[:3] - cur, -MAX_STEP, MAX_STEP), LOW, HIGH)
        self.d.ctrl[:] = [tgt[0], tgt[1], tgt[2] - Z_HOME_JOINT]
        for _ in range(SUBSTEPS):
            if self.attached is not None:
                p = self.grip_pos() + np.array([0, 0, -0.03])
                q, dof = self.jadr[self.attached], self.jdof[self.attached]
                self.d.qpos[q:q + 3] = p
                self.d.qvel[dof:dof + 6] = 0
            mujoco.mj_step(self.m, self.d)
        if a[3] < 0.5:                                      # closing
            self.grip = max(self.grip - 0.34, 0.4 if self.attached else 0.0)
            if self.attached is None and self.grip < 0.7:
                cand = self._graspable()
                if cand:
                    self._attach(cand); self.grip = max(self.grip, 0.4)
        else:                                               # opening
            self.grip = min(self.grip + 0.34, 1.0)
            if self.attached is not None and self.grip > 0.6:
                self._release()
        self.t += 1
        return self.obs() if obs else None

    def goto(self, xyz, g=1.0, tol=0.006, max_steps=80):
        """Scripted move (used by the expert and by the 'look' tool). Returns True when it arrived."""
        for _ in range(max_steps):
            cur = self.grip_pos()
            err = np.asarray(xyz, float) - cur
            if np.linalg.norm(err) < tol:
                return True
            self.step([*(cur + np.clip(err, -MAX_STEP, MAX_STEP)), g])
        return False

    # ---------------------------------------------------------------- observations
    def obs(self):
        o = {"state": np.array([*self.grip_pos(), self.grip], dtype=np.float32)}
        if self.render:
            for cam in ("front", "wrist"):
                self.r.update_scene(self.d, camera=cam, scene_option=self.opt_wrist if cam == "wrist" else None)
                o[cam] = self.r.render().copy()
        return o
