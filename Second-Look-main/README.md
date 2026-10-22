# Second Look: A Robot That Knows When Its Memory Is Stale

**Hackathon Project:** Nebius x NVIDIA Global AI Hackathon (Physical AI Track)  
**Track Focus:** Simulation, World Design, Synthetic Data Generation, and Domain Randomisation (Role C)

---

## 1. Quick Start Setup (5 minutes)

### Prerequisites
* Python 3.12+ (tested with MuJoCo 3.13.0)
* Git

### Installation
```bash
# Clone and enter directory
cd second-look

# Create virtual environment
python -m venv .venv

# Activate environment
# On Windows:
.venv\Scripts\activate
# On Linux / macOS:
source .venv/bin/activate

# Install dependencies (MuJoCo, OpenCV, fastparquet, pyyaml, pandas, etc.)
pip install -r requirements.txt
```

> **Headless Linux Rendering:**  
> If running on a headless cloud VM or server without a display, set:  
> `export MUJOCO_GL=osmesa` (requires `sudo apt install libosmesa6`).  
> On Windows and macOS, default rendering works out of the box.

---

## 2. Running the Verification & Core Checks

### A. Verify the Baseline Simulation & Scripted Expert
Runs 30 test episodes to confirm that physics, kinematics, visibility raycasts, and the scripted expert policy pass with 100% success:
```bash
python sim/check_expert.py
```
*(Expected output: `expert success 30/30 | steps per episode: mean 82 | ~2.0 s`)*

### B. Verify Camera Math & Pixel-to-Table Projection
Runs unit tests for `pixel_to_table()` ray-plane intersection and homography mapping:
```bash
python sim/test_camera_utils.py
```
*(Expected output: `Ran 5 tests ... OK`)*

### C. Verify Belief Logic & Search-Order Ordering
Runs a quick Monte Carlo test of confidence decay and search order:
```bash
python ai/toy_check.py
```

---

## 3. Running Scenarios & Disturbance Calibration (S1–S4)

The scenario engine implements:
* **S1:** Visible pick-and-place.
* **S2:** Hidden object fetch with variable delay $H$.
* **S3:** Moved while hidden with move probability $q$, detection rate $d$, and false-alarm rate $f$.
* **S4:** Failed grasp slip (`grip=0.0`) followed by autonomous recovery.

Run the 500-seed Monte Carlo calibration test to verify configured rates match observed rates:
```bash
python sim/test_scenarios.py
```
*(Saves structured telemetry logs matching contract schemas to `out/scenario_logs.jsonl`)*

---

## 4. Generating Synthetic Datasets

All datasets are recorded in **standard LeRobot v2.0 format** (dual $224 \times 224$ MP4 videos at 10 Hz + tabular Parquet state/action trajectories).

### Option 1: 50-Episode Smoke Dataset (~1.5 minutes)
Useful for rapid pipeline debugging and local tests:
```bash
python sim/make_dataset.py --episodes 50 --seed0 90000 --out out/smoke
```

### Option 2: Full 1,200-Episode Production Dataset (`second_look_v1`)
Generated across 4 non-overlapping seed shards and merged:
```bash
# Generate 4 shards (300 episodes each):
python sim/make_dataset.py --episodes 300 --seed0 0 --out out/shard_0
python sim/make_dataset.py --episodes 300 --seed0 10000 --out out/shard_1
python sim/make_dataset.py --episodes 300 --seed0 20000 --out out/shard_2
python sim/make_dataset.py --episodes 300 --seed0 30000 --out out/shard_3

# Merge shards into final dataset:
python sim/merge_shards.py --shards out/shard_0 out/shard_1 out/shard_2 out/shard_3 --out out/second_look_v1
```

### Option 3: 200-Episode Recovery Dataset (`v1b` Stretch Goal)
Demonstrates recovery from mechanical grip slips (detect failure $\to$ retract $\to$ realign $\to$ regrasp $\to$ deliver):
```bash
python sim/make_recovery_dataset.py --episodes 200 --seed0 50000 --out out/second_look_v1b
```

---

## 5. Validating Generated Datasets (QA Audit)

Run the automated QA audit script to check state/action ranges, kinematic step limits ($< 0.045\text{ m}$), and 100% video-to-table frame sync:

```bash
# Audit the production dataset:
python sim/validate_dataset.py --dataset out/second_look_v1 --num-samples 16 --out-sheet out/dataset_qa_contact_sheet.png

# Audit the recovery dataset:
python sim/validate_dataset.py --dataset out/second_look_v1b --num-samples 10 --out-sheet out/recovery_qa_contact_sheet.png

# Audit the smoke dataset:
python sim/validate_dataset.py --dataset out/smoke --num-samples 6 --out-sheet out/smoke_qa_contact_sheet.png
```

---

## 6. Generating YOLO Perception Labels

Export 1,500 synthetic images (front and wrist cameras) with tight 2D bounding boxes and train/val splits:
```bash
# 1. Export images, labels, and data.yaml:
python sim/export_yolo.py

# 2. Visually verify bounding boxes (generates out/yolo_verification_sheet.png):
python sim/check_yolo_labels.py
```

---

## 7. Generating Domain Randomisation Contact Sheet

Renders 12 randomized scene resets (lighting, camera jitter, object sizes/colors, screen positions) into a single visual contact sheet:
```bash
python sim/generate_contact_sheet.py
```
*(Saves composite image to `out/phase1_contact_sheet.png`)*

---

## 8. Repository Layout & Architecture

```
second-look/
├── contracts/
│   └── examples.jsonl              # Inter-module message contracts (extended with "event")
├── docs/
│   └── C_SUMMARY.md                # Comprehensive Role C master report & teammate handoff
├── sim/
│   ├── camera_utils.py             # Camera geometry & pixel_to_table() ray projection
│   ├── check_expert.py             # 30/30 expert policy invariant verification
│   ├── check_yolo_labels.py        # Visual bounding box verification tool
│   ├── closed_loop_template.py     # Template for closed-loop policy evaluation (Role D)
│   ├── dataset_backend.py          # Native DLL-safe LeRobot v2.0 writer & merger
│   ├── expert.py                   # Scripted expert policy (visible-only demonstration)
│   ├── export_yolo.py              # Synthetic YOLO image & label exporter
│   ├── generate_contact_sheet.py   # Domain randomisation contact sheet generator
│   ├── make_dataset.py             # Dataset shard generator
│   ├── make_recovery_dataset.py    # 200-episode v1b recovery dataset generator
│   ├── merge_shards.py             # Shard merger with seed collision validation
│   ├── render_frames.py            # Free segmentation label utility
│   ├── scenarios.py                # S1–S4 scenario simulation engine
│   ├── scene_v2.xml                # MuJoCo scene definition (lighting/specular polished)
│   ├── test_camera_utils.py        # Unit tests for camera projections
│   ├── test_scenarios.py           # Monte Carlo calibration test for q, d, f
│   ├── validate_dataset.py         # QA validation tool for dataset integrity
│   └── world.py                    # SecondLookEnv environment with domain randomisation
├── ai/                             # Belief, memory, and Nemotron modules (Role B)
├── train/                          # Model training scripts and commands (Role B & D)
├── docker/                         # Container recipes for headless cloud runs (Role D)
├── requirements.txt                # Python environment dependencies
└── README.md                       # Project overview and run guide
```

---

## 9. Honest Simplifications & Rules

* **Robot Kinematics:** The robot is a 3-axis Cartesian gantry with a parallel gripper. This eliminates inverse kinematics singularities while focusing on vision, memory, and reasoning.
* **Grasp Physics:** The grasp is kinematic: closing within $3.5\text{ cm}$ sideways and $0$ to $7\text{ cm}$ below the fingertips attaches the object; opening releases it.
* **Hard Demonstration Rule:** An expert demo never picks an object that neither camera can see. If an object is hidden, the robot must first move to look before it can pick.
