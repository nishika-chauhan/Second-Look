"""Level-2 demo: render camera images, get FREE labels from segmentation, draw boxes.

Run:  python sim/render_frames.py            (writes PNG files to ./out)

Rendering backend (MUJOCO_GL):
  * Windows / macOS: the default just works.
  * Linux with no display:  MUJOCO_GL=osmesa python sim/render_frames.py   (needs the libosmesa6 package)
  * Linux with a GPU:       MUJOCO_GL=egl python sim/render_frames.py
Set it in the shell BEFORE running Python. Tested with MuJoCo 3.13.0 using osmesa.
"""
import os

import cv2
import imageio.v2 as imageio
import mujoco
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out")
os.makedirs(OUT, exist_ok=True)
m = mujoco.MjModel.from_xml_path(os.path.join(HERE, "scene.xml"))
d = mujoco.MjData(m)


def put(name, x, y, z):
    """Teleport an object (it has a free joint called <name>_j) to a new position."""
    j = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, name + "_j")
    a = m.jnt_qposadr[j]
    d.qpos[a:a + 3] = [x, y, z]


def settle(n=800):
    for _ in range(n):
        mujoco.mj_step(m, d)


r = mujoco.Renderer(m, height=480, width=640)

# 1) everything visible
put("cup_red", -0.28, 0.10, 0.04)
put("bottle_blue", 0.22, 0.10, 0.04)
put("box_green", 0.30, -0.15, 0.03)
settle()
r.update_scene(d, camera="front")
rgb = r.render().copy()
imageio.imwrite(os.path.join(OUT, "visible.png"), rgb)

# 2) move the bottle behind the screen -> hidden from the front camera
put("bottle_blue", 0.0, 0.12, 0.04)
settle()
r.update_scene(d, camera="front")
imageio.imwrite(os.path.join(OUT, "hidden.png"), r.render())

# 3) free labels: segmentation tells us, per pixel, which geom we are looking at
put("bottle_blue", 0.22, 0.10, 0.04)
settle()
r.enable_segmentation_rendering()
r.update_scene(d, camera="front")
seg = r.render().copy()
r.disable_segmentation_rendering()
ids, types = seg[..., 0], seg[..., 1]

boxes = {}
for name in ["cup_red", "bottle_blue", "box_green", "screen"]:
    g = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, name + "_g")
    mask = (ids == g) & (types == mujoco.mjtObj.mjOBJ_GEOM)
    if mask.any():
        ys, xs = np.where(mask)
        boxes[name] = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
        cv2.rectangle(rgb, (boxes[name][0] - 2, boxes[name][1] - 2),
                      (boxes[name][2] + 2, boxes[name][3] + 2), (255, 255, 0), 2)
imageio.imwrite(os.path.join(OUT, "boxes.png"), rgb)
print("free labels (x0, y0, x1, y1):", boxes)
