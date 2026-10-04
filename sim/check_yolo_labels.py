"""Verification tool for YOLO-exported labels (Role C - Phase 5).

Loads N random exported images and their corresponding YOLO label files, draws
the bounding boxes back onto the images with class colors, and compiles a contact sheet
to verify visual alignment and bounding-box accuracy.
"""
import argparse
import os
import sys
from pathlib import Path
import cv2
import imageio.v2 as imageio
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out")
os.makedirs(OUT, exist_ok=True)

CLASSES = ["cup_red", "bottle_blue", "box_green", "screen"]
COLORS = {
    0: (0, 0, 255),       # red for cup_red (BGR)
    1: (255, 140, 0),     # blue for bottle_blue
    2: (0, 200, 0),       # green for box_green
    3: (0, 200, 255),     # yellow/amber for screen
}


def verify_yolo_labels(yolo_dir: str = "out/yolo_dataset", num_samples: int = 12, out_sheet: str | None = None):
    root = Path(yolo_dir)
    if not root.exists():
        print(f"[FAIL] YOLO directory not found: {root}")
        return False

    if out_sheet is None:
        out_sheet = os.path.join(OUT, "yolo_verification_sheet.png")

    # Find all images across train and val
    all_images = sorted(list(root.glob("images/*/*.jpg")))
    if not all_images:
        print(f"[FAIL] No images found in {root / 'images'}")
        return False

    print(f"=== Verifying YOLO Labels at {root} (Total Images: {len(all_images)}) ===")

    rng = np.random.default_rng(12345)
    sample_paths = rng.choice(all_images, size=min(num_samples, len(all_images)), replace=False)

    annotated_tiles = []
    total_boxes_verified = 0

    for img_path in sample_paths:
        # Corresponding label file
        split = img_path.parent.name
        lbl_path = root / "labels" / split / (img_path.stem + ".txt")

        img = cv2.imread(str(img_path))
        if img is None:
            continue
        h_img, w_img, _ = img.shape

        boxes = []
        if lbl_path.exists():
            with open(lbl_path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 5:
                        cid = int(parts[0])
                        xc, yc, w, h = map(float, parts[1:])
                        # Verify normalized range
                        assert 0.0 <= xc <= 1.0, f"xc {xc} outside [0, 1]"
                        assert 0.0 <= yc <= 1.0, f"yc {yc} outside [0, 1]"
                        assert 0.0 <= w <= 1.0, f"w {w} outside [0, 1]"
                        assert 0.0 <= h <= 1.0, f"h {h} outside [0, 1]"
                        boxes.append((cid, xc, yc, w, h))

        # Draw boxes onto image
        for cid, xc, yc, w, h in boxes:
            x1 = int(round((xc - w / 2.0) * w_img))
            y1 = int(round((yc - h / 2.0) * h_img))
            x2 = int(round((xc + w / 2.0) * w_img))
            y2 = int(round((yc + h / 2.0) * h_img))

            color = COLORS.get(cid, (255, 255, 255))
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)

            label = CLASSES[cid] if cid < len(CLASSES) else f"cls_{cid}"
            # Text background
            cv2.rectangle(img, (x1, max(0, y1 - 16)), (x1 + len(label) * 8 + 4, max(16, y1)), color, -1)
            cv2.putText(img, label, (x1 + 2, max(12, y1 - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 0), 1, cv2.LINE_AA)
            total_boxes_verified += 1

        # Border and subtitle
        sub = f"{img_path.name} ({split}) - {len(boxes)} boxes"
        cv2.putText(img, sub, (6, h_img - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
        tile = cv2.copyMakeBorder(img, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=[40, 40, 40])
        annotated_tiles.append(tile)

    # Composite into grid (4 columns)
    cols = 4
    rows = (len(annotated_tiles) + cols - 1) // cols
    grid_rows = []
    for r in range(rows):
        row_tiles = annotated_tiles[r * cols : (r + 1) * cols]
        while len(row_tiles) < cols:
            row_tiles.append(np.zeros_like(annotated_tiles[0]))
        grid_rows.append(np.hstack(row_tiles))
    sheet = np.vstack(grid_rows)

    imageio.imwrite(out_sheet, cv2.cvtColor(sheet, cv2.COLOR_BGR2RGB))
    print(f"[PASS] Successfully verified {total_boxes_verified} boxes across {len(annotated_tiles)} sample images.")
    print(f"       Visual contact sheet saved to -> {out_sheet}")
    return True


def main():
    ap = argparse.ArgumentParser(description="Check YOLO exported labels")
    ap.add_argument("--yolo-dir", default="out/yolo_dataset", help="YOLO dataset root")
    ap.add_argument("--num-samples", type=int, default=12, help="Number of samples to visualize")
    ap.add_argument("--out-sheet", default=None, help="Output contact sheet path")
    args = ap.parse_args()

    ok = verify_yolo_labels(yolo_dir=args.yolo_dir, num_samples=args.num_samples, out_sheet=args.out_sheet)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
