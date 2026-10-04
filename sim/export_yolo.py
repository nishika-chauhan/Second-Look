"""Batch YOLO Dataset Exporter for Second Look (Role C - Phase 5).

Generates 1,000-2,000 images across both front and wrist cameras with randomized
scene layouts (lighting, camera pose jitter, object positions, colors, and occluders).
Extracts free segmentation labels from MuJoCo, normalizes bounding boxes, and
exports clean YOLO format image-label pairs with an 80/20 train/val split and data.yaml.
"""
import argparse
import os
import sys
import shutil
from pathlib import Path
import cv2
import imageio.v2 as imageio
import mujoco
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world import OBJECTS, SecondLookEnv, Z_SAFE

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out")
os.makedirs(OUT, exist_ok=True)

CLASSES = ["cup_red", "bottle_blue", "box_green", "screen"]
CLASS_TO_ID = {name: idx for idx, name in enumerate(CLASSES)}


def extract_bboxes(env, camera: str, min_pixels: int = 10):
    """Renders segmentation and extracts normalized YOLO bounding boxes for all visible classes."""
    env.r.enable_segmentation_rendering()
    opt = env.opt_wrist if camera == "wrist" else None
    env.r.update_scene(env.d, camera=camera, scene_option=opt)
    seg = env.r.render().copy()
    env.r.disable_segmentation_rendering()

    ids, types = seg[..., 0], seg[..., 1]
    h_img, w_img = ids.shape
    bboxes = []

    # 1. Objects
    for obj_name in OBJECTS:
        gid = env.gid[obj_name]
        mask = (ids == gid) & (types == mujoco.mjtObj.mjOBJ_GEOM)
        if mask.sum() >= min_pixels:
            ys, xs = np.where(mask)
            x_min, x_max = float(xs.min()), float(xs.max())
            y_min, y_max = float(ys.min()), float(ys.max())

            # Convert to YOLO normalized format: x_center, y_center, width, height
            xc = (x_min + x_max) / (2.0 * w_img)
            yc = (y_min + y_max) / (2.0 * h_img)
            w = (x_max - x_min) / float(w_img)
            h = (y_max - y_min) / float(h_img)
            bboxes.append((CLASS_TO_ID[obj_name], xc, yc, w, h))

    # 2. Screens
    for s_name, gid in env.screen_geoms.items():
        mask = (ids == gid) & (types == mujoco.mjtObj.mjOBJ_GEOM)
        if mask.sum() >= min_pixels:
            ys, xs = np.where(mask)
            x_min, x_max = float(xs.min()), float(xs.max())
            y_min, y_max = float(ys.min()), float(ys.max())

            xc = (x_min + x_max) / (2.0 * w_img)
            yc = (y_min + y_max) / (2.0 * h_img)
            w = (x_max - x_min) / float(w_img)
            h = (y_max - y_min) / float(h_img)
            bboxes.append((CLASS_TO_ID["screen"], xc, yc, w, h))

    return bboxes


def export_yolo(num_resets: int = 750, out_dir: str = "out/yolo_dataset", val_ratio: float = 0.20, img_size: int = 224):
    out_path = Path(out_dir)
    if out_path.exists():
        shutil.rmtree(out_path)

    # Directory layout: images/{train, val}, labels/{train, val}
    for split in ("train", "val"):
        (out_path / "images" / split).mkdir(parents=True, exist_ok=True)
        (out_path / "labels" / split).mkdir(parents=True, exist_ok=True)

    # Write data.yaml
    yaml_content = f"""# YOLOv8 / YOLOv11 dataset configuration for Second Look
path: {out_path.resolve().as_posix()}
train: images/train
val: images/val

names:
  0: cup_red
  1: bottle_blue
  2: box_green
  3: screen

nc: 4
"""
    with open(out_path / "data.yaml", "w", encoding="utf-8") as f:
        f.write(yaml_content)

    env = SecondLookEnv(render=True, img=img_size, randomize=True)
    rng = np.random.default_rng(2026)

    total_images = 0
    train_count = 0
    val_count = 0
    class_counts = {c: 0 for c in CLASSES}

    print(f"=== Exporting YOLO Dataset ({num_resets} resets x 2 cameras = {num_resets * 2} images) to {out_path} ===")

    for i in range(num_resets):
        seed = 50_000 + i
        target = OBJECTS[seed % 3]
        start = ["home", "look_L", "look_R"][(seed // 3) % 3]

        env.reset(seed=seed, target=target, start=start)

        # Diverse robot vantage points for the wrist camera
        if rng.random() < 0.35:
            rx = rng.uniform(-0.35, 0.35)
            ry = rng.uniform(-0.15, 0.20)
            rz = rng.uniform(0.18, Z_SAFE)
            env.goto([rx, ry, rz], g=1.0, max_steps=20)

        # Decide train / val split
        split = "val" if (i % int(1.0 / val_ratio) == 0) else "train"

        # Render both camera views
        for cam in ("front", "wrist"):
            # 1. RGB render
            opt = env.opt_wrist if cam == "wrist" else None
            env.r.update_scene(env.d, camera=cam, scene_option=opt)
            rgb = env.r.render().copy()

            # 2. Extract bounding boxes from segmentation
            boxes = extract_bboxes(env, camera=cam)

            img_filename = f"reset_{i:05d}_{cam}.jpg"
            lbl_filename = f"reset_{i:05d}_{cam}.txt"

            img_dest = out_path / "images" / split / img_filename
            lbl_dest = out_path / "labels" / split / lbl_filename

            # Save JPEG (using OpenCV for high speed)
            cv2.imwrite(str(img_dest), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [int(cv2.IMWRITE_JPEG_QUALITY), 95])

            # Save YOLO text format
            with open(lbl_dest, "w", encoding="utf-8") as f:
                for cid, xc, yc, w, h in boxes:
                    f.write(f"{cid} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}\n")
                    class_counts[CLASSES[cid]] += 1

            total_images += 1
            if split == "train":
                train_count += 1
            else:
                val_count += 1

        if (i + 1) % 150 == 0 or (i + 1) == num_resets:
            print(f"  Processed {i + 1}/{num_resets} resets ({total_images} images written)...")

    print("\n--- YOLO Export Summary ---")
    print(f"  Total Images: {total_images} (Train: {train_count}, Val: {val_count})")
    print(f"  Split ratio:  {train_count / total_images * 100:.1f}% train / {val_count / total_images * 100:.1f}% val")
    print("  Class instances labeled:")
    for c, cnt in class_counts.items():
        print(f"    {c:15s}: {cnt:5d} boxes")
    print(f"  Config file:  {out_path / 'data.yaml'}")
    return total_images


def main():
    ap = argparse.ArgumentParser(description="Export YOLO format labels and images")
    ap.add_argument("--num-resets", type=int, default=750, help="Number of resets (each reset generates 2 images)")
    ap.add_argument("--out", default="out/yolo_dataset", help="Output directory")
    ap.add_argument("--img", type=int, default=224, help="Image resolution")
    args = ap.parse_args()

    export_yolo(num_resets=args.num_resets, out_dir=args.out, img_size=args.img)


if __name__ == "__main__":
    main()
