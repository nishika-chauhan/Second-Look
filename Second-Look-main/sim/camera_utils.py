"""Camera geometry, ray-plane projection, and homography utilities for Second Look.

Implements pixel-to-table projection and world-to-pixel camera math
for both front and wrist cameras (Sim Ladder Level 2 / Role C).
"""
import cv2
import mujoco
import numpy as np


def get_camera_params(env, cam_name="wrist", img_w=None, img_h=None):
    """Retrieve intrinsic parameters, extrinsic orientation, and camera position in world space.

    Args:
        env: SecondLookEnv instance.
        cam_name: 'front' or 'wrist'.
        img_w: Image width in pixels (defaults to env.img).
        img_h: Image height in pixels (defaults to env.img).

    Returns:
        dict containing:
            'pos': (3,) camera world position.
            'rot': (3, 3) camera rotation matrix in world space.
            'focal': float focal length in pixels.
            'cx': float principal point x.
            'cy': float principal point y.
            'K': (3, 3) camera intrinsic matrix.
            'cam_id': int camera geom/sensor ID.
    """
    w = img_w or env.img
    h = img_h or env.img
    cam_id = mujoco.mj_name2id(env.m, mujoco.mjtObj.mjOBJ_CAMERA, cam_name)
    if cam_id < 0:
        raise ValueError(f"Unknown camera name: {cam_name}")

    cam_pos = env.d.cam_xpos[cam_id].copy()
    cam_rot = env.d.cam_xmat[cam_id].reshape(3, 3).copy()
    fovy_deg = float(env.m.cam_fovy[cam_id])
    focal = (h / 2.0) / np.tan(np.radians(fovy_deg) / 2.0)
    cx = w / 2.0
    cy = h / 2.0

    K = np.array([
        [focal, 0.0,   cx],
        [0.0,   focal, cy],
        [0.0,   0.0,   1.0]
    ], dtype=np.float64)

    return {
        "pos": cam_pos,
        "rot": cam_rot,
        "focal": focal,
        "cx": cx,
        "cy": cy,
        "K": K,
        "cam_id": cam_id,
        "width": w,
        "height": h,
    }


def world_to_pixel(p_world, env, cam_name="wrist", img_w=None, img_h=None):
    """Project a 3D point in world coordinates into 2D camera pixel coordinates.

    Args:
        p_world: (3,) array-like [x, y, z] in world meters.
        env: SecondLookEnv instance.
        cam_name: 'front' or 'wrist'.
        img_w: Image width in pixels.
        img_h: Image height in pixels.

    Returns:
        (u, v): float pixel coordinates.
        in_front: bool, True if point is in front of the camera optical center.
    """
    params = get_camera_params(env, cam_name, img_w, img_h)
    p_w = np.asarray(p_world, dtype=np.float64)
    c_w = params["pos"]
    r_c = params["rot"]

    # Express world point relative to camera frame: p_cam = R^T * (p_world - c_world)
    p_c = r_c.T @ (p_w - c_w)

    # In MuJoCo camera frame: +X is right, +Y is up, -Z is optical forward
    optical_depth = -p_c[2]
    in_front = optical_depth > 1e-6

    if not in_front:
        return float("nan"), float("nan"), False

    f = params["focal"]
    u = params["cx"] + f * (p_c[0] / optical_depth)
    v = params["cy"] - f * (p_c[1] / optical_depth)  # pixel v points down, camera Y points up

    return float(u), float(v), True


def pixel_to_table(u, v, env, cam_name="wrist", z_table=0.0, img_w=None, img_h=None):
    """Cast a ray through pixel (u, v) and find its intersection with horizontal plane z = z_table.

    Args:
        u: Horizontal pixel coordinate (0 to width).
        v: Vertical pixel coordinate (0 to height).
        env: SecondLookEnv instance.
        cam_name: 'front' or 'wrist'.
        z_table: Table plane height in world meters (default 0.0).
        img_w: Image width in pixels.
        img_h: Image height in pixels.

    Returns:
        (x, y): Table coordinates in world meters.
    """
    params = get_camera_params(env, cam_name, img_w, img_h)
    c_w = params["pos"]
    r_c = params["rot"]
    f = params["focal"]

    # Direction vector in camera frame: [x_c, y_c, -1.0] where camera looks along -Z
    d_c = np.array([
        (u - params["cx"]) / f,
        -(v - params["cy"]) / f,
        -1.0
    ], dtype=np.float64)

    # Rotate ray to world frame
    d_w = r_c @ d_c

    # Check for ray parallel to tabletop
    if abs(d_w[2]) < 1e-9:
        raise ValueError("Ray is parallel to the tabletop plane and does not intersect.")

    # Ray equation: P(t) = c_w + t * d_w. At z = z_table: c_w[2] + t * d_w[2] = z_table
    t = (z_table - c_w[2]) / d_w[2]
    if t < 0:
        raise ValueError("Table intersection lies behind the camera optical plane.")

    p_intersect = c_w + t * d_w
    return float(p_intersect[0]), float(p_intersect[1])


def compute_table_homography(env, cam_name="wrist", z_table=0.0, img_w=None, img_h=None):
    """Compute 3x3 planar homography matrix H mapping image pixels to table (x, y) coordinates.

    Uses 4 control points on the tabletop and cv2.findHomography.
    Points satisfy: [x_table, y_table, 1]^T ~ H @ [u, v, 1]^T.

    Args:
        env: SecondLookEnv instance.
        cam_name: 'front' or 'wrist'.
        z_table: Table plane height in world meters.

    Returns:
        H: (3, 3) float64 homography matrix.
    """
    # 4 distinct points on the table workspace
    table_pts = np.array([
        [-0.20, -0.15],
        [ 0.20, -0.15],
        [ 0.20,  0.15],
        [-0.20,  0.15],
    ], dtype=np.float32)

    pixel_pts = []
    for pt in table_pts:
        u, v, ok = world_to_pixel([pt[0], pt[1], z_table], env, cam_name, img_w, img_h)
        if not ok:
            raise RuntimeError(f"Control point {pt} is not visible to camera {cam_name}")
        pixel_pts.append([u, v])

    pixel_pts = np.array(pixel_pts, dtype=np.float32)
    H, _ = cv2.findHomography(pixel_pts, table_pts)
    return H


def homography_pixel_to_table(u, v, H):
    """Project pixel (u, v) to table coordinates (x, y) using a precomputed homography matrix H.

    Args:
        u: Horizontal pixel coordinate.
        v: Vertical pixel coordinate.
        H: (3, 3) homography matrix from compute_table_homography.

    Returns:
        (x, y): Table coordinates in world meters.
    """
    p_img = np.array([u, v, 1.0], dtype=np.float64)
    p_world_h = H @ p_img
    x = p_world_h[0] / p_world_h[2]
    y = p_world_h[1] / p_world_h[2]
    return float(x), float(y)
