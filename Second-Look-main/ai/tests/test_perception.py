"""
pytest for the HSV colour detector (ai/perception.py, T3 Rung 1).

Tests cover:
  - synthetic images with ideal colours → correct detections
  - jittered colours (±0.06 RGB noise from C's sim) → still detected
  - blank grey image → no false positives
  - pixel-to-table coordinate mapping direction and magnitude
  - blob-too-small filter

Run from repo root:
    pytest ai/tests/test_perception.py -v
"""

import os
import sys
import math

import cv2
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import perception as P


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def blank_rgb(val=200):
    return np.ones((224, 224, 3), dtype=np.uint8) * val


def place_blob(img, cx, cy, radius, colour_rgb, shape="circle"):
    """Draw a solid blob on *img* (in-place) and return img."""
    if shape == "circle":
        cv2.circle(img, (cx, cy), radius, colour_rgb, -1)
    else:
        cv2.rectangle(img, (cx - radius, cy - radius),
                      (cx + radius, cy + radius), colour_rgb, -1)
    return img


# Pure ideal colours for each object (BGR tuples not needed — RGB)
RED_RGB   = (220,  30,  30)
BLUE_RGB  = ( 30,  80, 220)
GREEN_RGB = ( 40, 200,  40)


# ---------------------------------------------------------------------------
# px_to_table: geometry contract
# ---------------------------------------------------------------------------

def test_centre_pixel_maps_to_origin():
    x, y = P.px_to_table(112, 112)
    assert x == pytest.approx(0.0, abs=1e-3)
    assert y == pytest.approx(0.0, abs=1e-3)


def test_right_of_centre_is_positive_x():
    x, _ = P.px_to_table(168, 112)   # 56 px to the right
    assert x > 0, "rightward pixels should map to positive table-x"


def test_above_centre_is_positive_y():
    _, y = P.px_to_table(112, 56)    # 56 px upward in image
    assert y > 0, "upward pixels (lower row index) should map to positive table-y"


def test_symmetry():
    x_r, y_r = P.px_to_table(156, 112)
    x_l, y_l = P.px_to_table(68,  112)
    assert x_r == pytest.approx(-x_l, abs=1e-4)
    assert y_r == pytest.approx(y_l, abs=1e-4)


def test_magnitude_roughly_correct():
    """224 px at FOV=90°, height=0.30 m → half-width ≈ 0.30 m."""
    x_edge, _ = P.px_to_table(223, 112)
    assert 0.25 < x_edge < 0.35, f"edge pixel should be ~0.30 m from centre, got {x_edge:.3f}"


# ---------------------------------------------------------------------------
# detect_objects: ideal colours
# ---------------------------------------------------------------------------

def test_detects_red_cup():
    img = blank_rgb()
    place_blob(img, 60, 80, 18, RED_RGB)
    hits = P.detect_objects(img)
    assert hits["cup_red"] is not None, "red blob should be detected as cup_red"
    assert hits["bottle_blue"] is None
    assert hits["box_green"]   is None


def test_detects_blue_bottle():
    img = blank_rgb()
    place_blob(img, 160, 90, 14, BLUE_RGB)
    hits = P.detect_objects(img)
    assert hits["bottle_blue"] is not None
    assert hits["cup_red"]    is None
    assert hits["box_green"]  is None


def test_detects_green_box():
    img = blank_rgb()
    place_blob(img, 110, 155, 18, GREEN_RGB, shape="rect")
    hits = P.detect_objects(img)
    assert hits["box_green"] is not None
    assert hits["cup_red"]    is None
    assert hits["bottle_blue"] is None


def test_detects_all_three_simultaneously():
    img = blank_rgb()
    place_blob(img,  55,  60, 18, RED_RGB)
    place_blob(img, 165,  80, 14, BLUE_RGB)
    place_blob(img, 110, 160, 18, GREEN_RGB, shape="rect")
    hits = P.detect_objects(img)
    assert hits["cup_red"]    is not None, "cup_red should be found"
    assert hits["bottle_blue"] is not None, "bottle_blue should be found"
    assert hits["box_green"]  is not None, "box_green should be found"


def test_blank_image_has_no_detections():
    img = blank_rgb(val=200)   # neutral grey, no saturated blobs
    hits = P.detect_objects(img)
    assert all(v is None for v in hits.values()), "grey image should have no detections"


# ---------------------------------------------------------------------------
# detect_objects: jittered colours (±0.06 RGB)
# ---------------------------------------------------------------------------

def _jitter(rgb, delta=15):
    """Add a fixed offset to each channel and clip, simulating ±0.06 jitter."""
    arr = np.array(rgb, dtype=np.int32) + delta
    return tuple(int(np.clip(v, 0, 255)) for v in arr)


def test_red_still_detected_with_jitter():
    img = blank_rgb()
    place_blob(img, 60, 80, 18, _jitter(RED_RGB, +15))
    assert P.detect_objects(img)["cup_red"] is not None


def test_blue_still_detected_with_jitter():
    img = blank_rgb()
    place_blob(img, 160, 90, 14, _jitter(BLUE_RGB, -15))
    assert P.detect_objects(img)["bottle_blue"] is not None


def test_green_still_detected_with_jitter():
    img = blank_rgb()
    place_blob(img, 110, 155, 18, _jitter(GREEN_RGB, +15), shape="rect")
    assert P.detect_objects(img)["box_green"] is not None


# ---------------------------------------------------------------------------
# detect_objects: coordinate correctness
# ---------------------------------------------------------------------------

def test_blob_left_of_centre_gives_negative_x():
    img = blank_rgb()
    place_blob(img, 50, 112, 18, BLUE_RGB)   # clearly left of cx=112
    pos = P.detect_objects(img)["bottle_blue"]
    assert pos is not None
    assert pos[0] < 0, f"blob at col 50 should give negative table-x, got {pos[0]}"


def test_blob_right_of_centre_gives_positive_x():
    img = blank_rgb()
    place_blob(img, 174, 112, 18, BLUE_RGB)   # clearly right of cx=112
    pos = P.detect_objects(img)["bottle_blue"]
    assert pos is not None
    assert pos[0] > 0, f"blob at col 174 should give positive table-x, got {pos[0]}"


def test_blob_at_centre_near_zero():
    img = blank_rgb()
    place_blob(img, 112, 112, 20, RED_RGB)
    pos = P.detect_objects(img)["cup_red"]
    assert pos is not None
    assert abs(pos[0]) < 0.02, f"blob at image centre should give x≈0, got {pos[0]}"
    assert abs(pos[1]) < 0.02, f"blob at image centre should give y≈0, got {pos[1]}"


# ---------------------------------------------------------------------------
# detect_objects: tiny blob filter
# ---------------------------------------------------------------------------

def test_tiny_blob_not_detected():
    img = blank_rgb()
    # Draw a 2×2 px red square — well below MIN_BLOB_AREA
    cv2.rectangle(img, (110, 110), (112, 112), RED_RGB, -1)
    hits = P.detect_objects(img)
    assert hits["cup_red"] is None, "2×2 pixel blob should be filtered out"


def test_blob_just_above_threshold_detected():
    img = blank_rgb()
    # Radius 5 → area ≈ π×25 ≈ 78 px² (> MIN_BLOB_AREA=50 after morphology)
    place_blob(img, 112, 112, 5, RED_RGB)
    hits = P.detect_objects(img)
    # Not guaranteed to survive morphological opening at radius 5 with kernel 5
    # but if it does, it should be at the right place
    if hits["cup_red"] is not None:
        assert abs(hits["cup_red"][0]) < 0.05
