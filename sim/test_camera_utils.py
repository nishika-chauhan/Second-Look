"""Unit tests for camera math and pixel_to_table projection (Role C)."""
import os
import sys
import unittest
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world import SecondLookEnv, OBJECTS
from camera_utils import (
    get_camera_params,
    world_to_pixel,
    pixel_to_table,
    compute_table_homography,
    homography_pixel_to_table,
)


class TestCameraUtils(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = SecondLookEnv(render=True, img=224, randomize=False)
        cls.env.reset(seed=123)

    def test_camera_params_retrieval(self):
        """Verify camera parameters exist and have correct shapes."""
        for cam in ("front", "wrist"):
            params = get_camera_params(self.env, cam)
            self.assertEqual(params["pos"].shape, (3,))
            self.assertEqual(params["rot"].shape, (3, 3))
            self.assertGreater(params["focal"], 0)
            self.assertEqual(params["cx"], 112.0)
            self.assertEqual(params["cy"], 112.0)

    def test_front_cam_round_trip_accuracy(self):
        """Verify round-trip world -> pixel -> world accuracy on front camera."""
        test_points = [
            [-0.25, -0.10, 0.04],
            [ 0.00, -0.15, 0.035],
            [ 0.25, -0.10, 0.02],
            [ 0.00,  0.12, 0.04],
        ]
        for pt in test_points:
            u, v, in_front = world_to_pixel(pt, self.env, cam_name="front")
            self.assertTrue(in_front, f"Point {pt} should be in front of front camera")
            reproj_x, reproj_y = pixel_to_table(u, v, self.env, cam_name="front", z_table=pt[2])
            error = np.linalg.norm([reproj_x - pt[0], reproj_y - pt[1]])
            self.assertLess(error, 1e-6, f"Reprojection error {error} exceeds 1e-6 for {pt}")

    def test_wrist_cam_round_trip_accuracy(self):
        """Verify round-trip accuracy on down-looking wrist camera."""
        # Move gantry to hover directly over a point
        self.env.set_gantry([0.15, 0.05, 0.20])
        test_points = [
            [0.15, 0.05, 0.04],
            [0.12, 0.02, 0.035],
            [0.18, 0.08, 0.02],
        ]
        for pt in test_points:
            u, v, in_front = world_to_pixel(pt, self.env, cam_name="wrist")
            self.assertTrue(in_front)
            reproj_x, reproj_y = pixel_to_table(u, v, self.env, cam_name="wrist", z_table=pt[2])
            error = np.linalg.norm([reproj_x - pt[0], reproj_y - pt[1]])
            self.assertLess(error, 1e-6, f"Wrist reprojection error {error} exceeds 1e-6 for {pt}")

    def test_homography_vs_analytical_projection(self):
        """Verify planar homography matches analytical ray projection within 0.1 mm."""
        z_table = 0.0
        H = compute_table_homography(self.env, cam_name="front", z_table=z_table)
        
        # Test across multiple grid points on the table
        for x in (-0.15, 0.0, 0.15):
            for y in (-0.10, 0.0, 0.10):
                u, v, ok = world_to_pixel([x, y, z_table], self.env, cam_name="front")
                self.assertTrue(ok)
                hx, hy = homography_pixel_to_table(u, v, H)
                ax, ay = pixel_to_table(u, v, self.env, cam_name="front", z_table=z_table)
                err_h = np.linalg.norm([hx - x, hy - y])
                err_a = np.linalg.norm([ax - x, ay - y])
                self.assertLess(err_h, 1e-4, f"Homography error {err_h} exceeds 0.1 mm")
                self.assertLess(err_a, 1e-6, f"Analytical error {err_a} exceeds 1e-6")

    def test_object_ground_truth_positions(self):
        """Verify projecting ground-truth object coordinates recovers exact positions."""
        for obj in OBJECTS:
            pos = self.env.obj_pos(obj)
            u, v, ok = world_to_pixel(pos, self.env, cam_name="front")
            self.assertTrue(ok)
            px, py = pixel_to_table(u, v, self.env, cam_name="front", z_table=pos[2])
            err = np.linalg.norm([px - pos[0], py - pos[1]])
            self.assertLess(err, 1e-6)


if __name__ == "__main__":
    unittest.main()
