"""Check perception.py against C's real wrist frames (out/wrist_detector_samples/).

    python ai/validate_perception.py <folder with PNGs + metadata.json>

For every frame: project each object's true position into the camera, decide
whether it should be visible, run the detector, and compare world positions.
"""
import json, os, sys
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import perception as P

OBJ_TOP_Z = 0.04


def main(folder):
    meta = json.load(open(os.path.join(folder, "metadata.json")))
    half = np.tan(np.radians(P.WRIST_FOV_DEG / 2))
    errs, tp, fn, fp, tn = [], 0, 0, 0, 0
    for m in meta:
        img = cv2.cvtColor(cv2.imread(os.path.join(folder, m["filename"])), cv2.COLOR_BGR2RGB)
        cam = np.array(m["cam_world_pos"]); h = cam[2] - OBJ_TOP_Z
        det = P.detect_objects(img, cam_height=h)
        for name, pos in m["object_world_positions"].items():
            dx, dy = pos[0] - cam[0], pos[1] - cam[1]
            visible = max(abs(dx), abs(dy)) < 0.92 * h * half          # inside the frame with a small margin
            d = det.get(name)
            if d is None:
                fn += visible; tn += (not visible)
                if visible: print(f"MISS  {m['filename']:26s} {name}  truth offset=({dx:+.3f},{dy:+.3f})")
            else:
                if not visible:
                    fp += 1; print(f"FALSE {m['filename']:26s} {name} detected but outside frame")
                    continue
                tp += 1; errs.append(np.hypot(d[0] - dx, d[1] - dy))
    errs = np.array(errs)
    print(f"\nframes={len(meta)}  detected={tp}  missed={fn}  false={fp}  correctly-absent={tn}")
    if len(errs):
        print(f"position error (m): mean={errs.mean():.4f}  median={np.median(errs):.4f}  max={errs.max():.4f}")
        print(f"within 2 cm: {(errs < 0.02).mean():.0%}   within 4 cm: {(errs < 0.04).mean():.0%}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "out/wrist_detector_samples")
