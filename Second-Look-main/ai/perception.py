"""Wrist-camera HSV colour detector (role B, T3 Rung 1).

Detects cup_red, bottle_blue, box_green in a 224×224 wrist image by
thresholding HSV channels, finding the largest blob per object, and
converting the pixel centroid to table-frame (x, y) coordinates.

Plan Part 5.6, Rung 1: "Threshold HSV in OpenCV, take blob centres,
convert pixel centres to table coordinates."

HSV ranges have ±0.06 RGB slack baked in to tolerate C's colour jitter.

Usage
-----
    # From Python:
    import cv2
    from ai.perception import detect_objects
    img_rgb = cv2.cvtColor(cv2.imread("wrist.png"), cv2.COLOR_BGR2RGB)
    hits = detect_objects(img_rgb)
    # → {"bottle_blue": (0.12, -0.05), "cup_red": None, "box_green": None}

    # Standalone smoke test:
    python ai/perception.py [--image path/to/wrist.png] [--show]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Camera ↔ table geometry
# ---------------------------------------------------------------------------
# Wrist camera: 224×224, mounted 0.30 m above the table surface, pointing
# straight down.  FOV ≈ 90° → each pixel spans ~(0.30 * 2 / 224) ≈ 2.68 mm.
# Image centre = robot wrist position (table_x=0, table_y=0 in wrist frame).
# Positive x → right in the image; positive y → up in the image.
# These numbers are tunable when C publishes the exact camera intrinsics.

WRIST_IMG_W = 224
WRIST_IMG_H = 224
WRIST_HEIGHT_M = 0.30          # metres above table surface
WRIST_FOV_DEG = 90.0           # full horizontal field of view

_px_per_m = WRIST_IMG_W / (2.0 * WRIST_HEIGHT_M * np.tan(np.radians(WRIST_FOV_DEG / 2.0)))
_cx = WRIST_IMG_W / 2.0
_cy = WRIST_IMG_H / 2.0


def px_to_table(px_col: float, px_row: float) -> tuple[float, float]:
    """Convert wrist-image pixel (col, row) to table-frame (x, y) in metres.

    Origin is the pixel centre (112, 112).  x increases rightward, y upward
    (away from camera in the image's top-left-origin row convention).
    """
    x = (px_col - _cx) / _px_per_m
    y = -((px_row - _cy) / _px_per_m)   # row↑ = y↓ in image, so flip
    return round(x, 4), round(y, 4)


# ---------------------------------------------------------------------------
# HSV colour ranges  (OpenCV HSV: H∈[0,179], S∈[0,255], V∈[0,255])
# ---------------------------------------------------------------------------
# Ranges include slack for C's ±0.06 RGB jitter (≈ ±10 H, ±20 S, ±20 V).
# Red wraps around 0°/360° in HSV so it needs two masks.

_HSV_RANGES: dict[str, list[tuple]] = {
    "cup_red": [
        # lower red (H ≈ 0–15)
        ((0,   120, 100), (15,  255, 255)),
        # upper red (H ≈ 160–179)
        ((160, 120, 100), (179, 255, 255)),
    ],
    "bottle_blue": [
        ((100, 120, 80),  (135, 255, 255)),
    ],
    "box_green": [
        ((40,  100, 80),  (85,  255, 255)),
    ],
}

# Minimum blob area (px²) to be counted as a real detection.
# At 224×224 and ~2.7 mm/px, a 2 cm object subtends ~7 px → 50 px².
MIN_BLOB_AREA = 50


# ---------------------------------------------------------------------------
# Core detection
# ---------------------------------------------------------------------------

def _largest_blob(mask: np.ndarray) -> Optional[tuple[float, float, float]]:
    """Return (cx, cy, area) of the largest connected component in mask, or None."""
    num, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    best_area = MIN_BLOB_AREA - 1
    best = None
    for i in range(1, num):          # component 0 is background
        area = stats[i, cv2.CC_STAT_AREA]
        if area > best_area:
            best_area = area
            best = (centroids[i][0], centroids[i][1], float(area))
    return best


def detect_objects(
    wrist_img_rgb: np.ndarray,
    min_blob_area: int = MIN_BLOB_AREA,
) -> dict[str, Optional[tuple[float, float]]]:
    """Detect coloured objects in a wrist-camera image.

    Parameters
    ----------
    wrist_img_rgb : np.ndarray
        224×224×3 uint8 image in RGB order (as delivered by LeRobot /
        cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)).
    min_blob_area : int
        Override the minimum blob size threshold.

    Returns
    -------
    dict  {object_name: (table_x, table_y) | None}
        table_x, table_y in metres in the wrist frame.
        None means the object was not detected in this image.
    """
    hsv = cv2.cvtColor(wrist_img_rgb, cv2.COLOR_RGB2HSV)
    results: dict[str, Optional[tuple[float, float]]] = {}

    for obj, ranges in _HSV_RANGES.items():
        # Build combined mask from all ranges for this object
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for (lo, hi) in ranges:
            mask |= cv2.inRange(hsv, np.array(lo, dtype=np.uint8),
                                     np.array(hi, dtype=np.uint8))

        # Morphological cleanup: remove noise, fill small holes
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

        blob = _largest_blob(mask)
        if blob is None or blob[2] < min_blob_area:
            results[obj] = None
        else:
            cx, cy, _ = blob
            results[obj] = px_to_table(cx, cy)

    return results


def detect_from_belief_update(
    wrist_img_rgb: np.ndarray,
    t: float,
    beliefs: dict,          # {obj_name: Belief}  from regions_belief
) -> None:
    """Run detector and call regions_belief.seen() for each visible object.

    This is the integration hook called by the episode runner after every
    wrist-frame observation.  Pass the live belief dict so this function
    can update in-place without the caller needing to know detector output.

    Parameters
    ----------
    wrist_img_rgb : np.ndarray   224×224×3 RGB wrist frame
    t             : float        current sim time (seconds)
    beliefs       : dict         {obj_name: Belief}  mutable, updated in place
    """
    # import here to avoid circular import at module load time
    from ai import regions_belief as RB   # noqa: PLC0415

    hits = detect_objects(wrist_img_rgb)
    for obj_name, table_pos in hits.items():
        if table_pos is not None and obj_name in beliefs:
            # Determine which screen we're looking at from the x coordinate:
            # table x < 0 → left screen ("L"), x > 0 → right screen ("R").
            place = "L" if table_pos[0] < 0 else "R"
            RB.seen(beliefs[obj_name], place, t)


# ---------------------------------------------------------------------------
# Visualisation helper (debug / demo only)
# ---------------------------------------------------------------------------

def annotate(wrist_img_rgb: np.ndarray,
             detections: dict[str, Optional[tuple[float, float]]]) -> np.ndarray:
    """Draw detection markers on a copy of the image (RGB → RGB)."""
    vis = wrist_img_rgb.copy()
    colours_bgr = {
        "cup_red":    (0,   0,   200),
        "bottle_blue":(200, 50,  0),
        "box_green":  (0,   200, 50),
    }
    # We need pixel coords back; reverse px_to_table for display
    for obj, pos in detections.items():
        if pos is None:
            continue
        tx, ty = pos
        px_col = int(tx * _px_per_m + _cx)
        px_row = int(-ty * _px_per_m + _cy)
        bgr = colours_bgr.get(obj, (200, 200, 200))
        # Annotate on BGR copy
        vis_bgr = cv2.cvtColor(vis, cv2.COLOR_RGB2BGR)
        cv2.circle(vis_bgr, (px_col, px_row), 8, bgr, 2)
        cv2.putText(vis_bgr, obj.split("_")[1],
                    (px_col + 10, px_row),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, bgr, 1, cv2.LINE_AA)
        vis = cv2.cvtColor(vis_bgr, cv2.COLOR_BGR2RGB)
    return vis


# ---------------------------------------------------------------------------
# Standalone smoke test
# ---------------------------------------------------------------------------

def _generate_test_image() -> np.ndarray:
    """Synthesise a 224×224 RGB image with one blob of each colour."""
    img = np.ones((224, 224, 3), dtype=np.uint8) * 200  # grey background
    # Red cup at (60, 60)
    cv2.circle(img, (60, 60), 20, (220, 30, 30), -1)
    # Blue bottle at (160, 80)
    cv2.circle(img, (160, 80), 15, (30, 80, 220), -1)
    # Green box at (110, 160)
    cv2.rectangle(img, (90, 145), (130, 175), (40, 200, 40), -1)
    return img


def main():
    ap = argparse.ArgumentParser(description="HSV colour detector smoke test")
    ap.add_argument("--image", default=None,
                    help="Path to a wrist PNG/JPG (uses synthetic image if omitted)")
    ap.add_argument("--show", action="store_true",
                    help="Display annotated result with cv2.imshow()")
    args = ap.parse_args()

    if args.image:
        bgr = cv2.imread(args.image)
        if bgr is None:
            print(f"ERROR: cannot read {args.image}", file=sys.stderr)
            sys.exit(1)
        img_rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        print(f"Loaded {args.image}  ({img_rgb.shape[1]}×{img_rgb.shape[0]})")
    else:
        img_rgb = _generate_test_image()
        print("Using synthetic test image (224×224)")

    hits = detect_objects(img_rgb)

    print("\nDetections (table-frame metres, origin = wrist centre):")
    any_hit = False
    for obj, pos in hits.items():
        if pos is not None:
            print(f"  {obj:<15s}  x={pos[0]:+.4f} m  y={pos[1]:+.4f} m")
            any_hit = True
        else:
            print(f"  {obj:<15s}  — not detected")

    if not any_hit:
        print("\n  (no objects detected — try --image with a real wrist frame)")

    if args.show:
        vis = annotate(img_rgb, hits)
        cv2.imshow("perception smoke test", cv2.cvtColor(vis, cv2.COLOR_RGB2BGR))
        print("\nPress any key to close…")
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    print("\nOK")


if __name__ == "__main__":
    main()
