# Second Look - starter kit (VLA edition)

Working starting point for the hackathon project "a robot that knows when its memory is stale".
TESTED = run by us with MuJoCo 3.13.0, lerobot 0.6.1, Python 3.12 (Linux, software rendering).
TEMPLATE = written from official docs, not run. Treat as a head start, expect to debug.

## Set up (10 minutes)
    python -m venv .venv
    source .venv/bin/activate                # Windows: .venv\Scripts\activate
    pip install -r requirements.txt          # add: pip install "lerobot[dataset]"  for the dataset writer

## Level 1-3: the small world you can understand in an afternoon
    python ai/belief.py                      # TESTED  belief with fading confidence
    python sim/gantry_demo.py                # TESTED  gantry picks the red cup (scene.xml)
    python sim/render_frames.py              # TESTED  camera images, free labels, boxes -> ./out
    python -m mujoco.viewer --mjcf sim/scene.xml      # look at it (macOS: mjpython -m mujoco.viewer ...)

## The VLA-edition world and data engine
    python sim/check_expert.py               # TESTED  scripted expert succeeds 30/30, no rendering
    python ai/regions_belief.py              # (imported by the toy check)
    python ai/toy_check.py                   # TESTED  toy sanity check of the search-order idea (NOT results)
    python sim/make_dataset.py --episodes 6 --out out/second_look_v0        # TESTED  ~1 min on 1 CPU
    python sim/make_dataset.py --episodes 300 --seed0 0 --out out/shard_0   # run several of these (different --seed0)
    python sim/merge_shards.py --shards out/shard_0 out/shard_1 --out out/second_look_v1    # TESTED  merge shards

Files
    sim/scene_v2.xml        table, 3 objects, tray, TWO screens, gantry robot, front + wrist cameras
    sim/world.py            SecondLookEnv: step([x,y,z,gripper]) at 10 Hz, gripper state, visibility, reset layouts
    sim/expert.py           scripted pick-and-place with privileged info (data + "perfect executor" baseline)
    sim/make_dataset.py     expert demos -> LeRobot dataset (video + parquet)
    sim/merge_shards.py     merge shards from several jobs into one dataset
    sim/closed_loop_template.py   TEMPLATE  run a trained policy in the sim and count successes
    ai/regions_belief.py    belief over hiding places + search order (p / cost)
    ai/nemotron_client.py   TEMPLATE  Nebius Token Factory call with JSON handling and fallback
    train/commands.md       TEMPLATE  GR00T N1.7 / SmolVLA training commands from the official docs
    contracts/examples.jsonl   message shapes shared by all four roles
    docker/                 TEMPLATE  headless simulator image + Nebius job example

Rendering on Linux without a display: `sudo apt install libosmesa6`, then `MUJOCO_GL=osmesa python ...`.
Windows/macOS: remove the MUJOCO_GL line in make_dataset.py (default renderer works).
Do not forget a LICENSE file (MIT or Apache-2.0) in your public repo. The hackathon requires one.
