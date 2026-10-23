"""Generate a contact sheet of 12 random resets to visually verify scene randomisation.
Saves out/phase1_contact_sheet.png.
"""
import os
import sys

import cv2
import imageio.v2 as imageio
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world import OBJECTS, SecondLookEnv

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out")
os.makedirs(OUT, exist_ok=True)

def main():
    env = SecondLookEnv(render=True, img=224, randomize=True)
    rows = []
    
    # 12 random resets (seeds 100 to 111 for varied layouts)
    seeds = list(range(100, 112))
    grid = []
    
    for idx, seed in enumerate(seeds):
        target = OBJECTS[seed % 3]
        start = ["home", "look_L", "look_R"][(seed // 3) % 3]
        obs = env.reset(seed=seed, target=target, start=start)
        
        front = obs["front"].copy()
        wrist = obs["wrist"].copy()
        
        # Combine front and wrist side by side for each episode
        # Label each panel
        cv2.putText(front, f"Seed {seed} ({start})", (8, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(front, f"Tgt: {target}", (8, 38),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(wrist, "Wrist Cam", (8, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        
        # Add a 2px vertical separator between front and wrist
        sep = np.full((224, 2, 3), 120, dtype=np.uint8)
        cell = np.hstack([front, sep, wrist])
        
        # Add a border around each cell
        cell = cv2.copyMakeBorder(cell, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=[40, 40, 40])
        grid.append(cell)
        
    # Arrange 4 columns x 3 rows
    row_images = []
    for r in range(3):
        row_images.append(np.hstack(grid[r * 4:(r + 1) * 4]))
    sheet = np.vstack(row_images)
    
    out_path = os.path.join(OUT, "phase1_contact_sheet.png")
    imageio.imwrite(out_path, sheet)
    print(f"Contact sheet saved to {out_path} (shape: {sheet.shape})")

if __name__ == "__main__":
    main()
