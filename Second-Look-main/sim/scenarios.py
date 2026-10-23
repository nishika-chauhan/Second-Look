"""General Scenario Engine for Second Look (Role C - Simulation: World and Data).

Implements:
- S1: Target visible in open, robot picks and places into tray.
- S2: Target hidden behind screen for variable time, robot looks and fetches.
- S3: Target hidden; while hidden it moves with probability q (to another screen or open table).
      Zone disturbance sensor triggers on moves with detection probability d, and false-alarms with rate f.
- S4: Grasp failure simulation (gripper closes on nothing, grip=0.0) followed by autonomous recovery.

All scenarios enforce the HARD RULE:
A training demo must never show the expert picking up an object that neither
the front nor wrist camera can currently see.
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world import MAX_STEP, REST_Z, TRAY_XY, Z_SAFE, HOME, OBJECTS, SecondLookEnv
from expert import run_expert


def _create_event(episode_id, t, kind, **kwargs):
    """Structured event log extending contracts/examples.jsonl."""
    msg = {
        "type": "event",
        "episode_id": episode_id,
        "t": round(float(t), 2),
        "kind": kind,
    }
    msg.update(kwargs)
    return msg


def _create_observation(episode_id, t, env, target=None):
    """Structured observation record matching contracts/examples.jsonl."""
    detections = []
    for n in OBJECTS:
        if env.front_visible(n):
            pos = env.obj_pos(n)
            detections.append({
                "label": n,
                "xy": [round(float(pos[0]), 3), round(float(pos[1]), 3)],
                "score": 0.99
            })
    occluders = []
    for k, gid in env.screen_geoms.items():
        pos = env.m.geom_pos[gid]
        occluders.append({
            "id": f"screen_{k}",
            "xy": [round(float(pos[0]), 3), round(float(pos[1]), 3)]
        })
    return {
        "type": "observation",
        "episode_id": episode_id,
        "t": round(float(t), 2),
        "detections": detections,
        "occluders": occluders,
        "events": []
    }


def _create_action_result(episode_id, t, skill, ok, duration_s, **kwargs):
    """Structured action result record matching contracts/examples.jsonl."""
    msg = {
        "type": "action_result",
        "episode_id": episode_id,
        "t": round(float(t), 2),
        "skill": skill,
        "ok": bool(ok),
        "duration_s": round(float(duration_s), 2)
    }
    msg.update(kwargs)
    return msg


def _create_episode_end(episode_id, scenario, target, success, total_time_s, ground_truth_xy, **metadata):
    """Structured episode end record matching contracts/examples.jsonl."""
    msg = {
        "type": "episode_end",
        "episode_id": episode_id,
        "scenario": scenario,
        "target": target,
        "success": bool(success),
        "total_time_s": round(float(total_time_s), 2),
        "ground_truth_xy": [round(float(ground_truth_xy[0]), 3), round(float(ground_truth_xy[1]), 3)],
    }
    msg.update(metadata)
    return msg


# ---------------------------------------------------------------------------
# S1: VISIBLE TARGET PICK-AND-PLACE
# ---------------------------------------------------------------------------
def run_s1(env, seed, target="cup_red", record=False):
    """Scenario 1: Target is visible in the open. Robot executes pick-and-place."""
    rng = np.random.default_rng(seed)
    episode_id = f"S1-seed{seed}-{target}"
    logs = []
    frames = []

    # Reset environment with target visible from the front
    env.reset(seed=seed, target=target, start="home")
    t_curr = 0.0

    # Verification of initial state
    assert env.front_visible(target), f"S1 requires target {target} to be front-visible"
    logs.append(_create_observation(episode_id, t_curr, env, target))

    # HARD RULE CHECK: Target must be visible before picking
    can_see = env.front_visible(target) or env.wrist_sees(target)
    assert can_see, "HARD RULE VIOLATION: Robot cannot see target before pick!"

    t_start = t_curr
    success, expert_frames = run_expert(env, target, rng, record=record)
    if record:
        frames.extend(expert_frames)
    duration = len(expert_frames) * 0.1 if expert_frames else 8.5
    t_curr += duration

    logs.append(_create_action_result(episode_id, t_curr, "pick_and_place", success, duration))
    gt_pos = env.obj_pos(target)
    logs.append(_create_episode_end(episode_id, "S1", target, success, t_curr, gt_pos))

    return success, logs, frames


# ---------------------------------------------------------------------------
# S2: HIDDEN THEN FETCH (VARIABLE HIDDEN TIME)
# ---------------------------------------------------------------------------
def run_s2(env, seed, target="bottle_blue", hidden_screen="L", hidden_time=None, record=False):
    """Scenario 2: Target is hidden behind a screen for hidden_time seconds.
    Robot navigates to look over the screen, verifies visibility, and fetches.
    """
    rng = np.random.default_rng(seed)
    episode_id = f"S2-seed{seed}-{target}"
    logs = []
    frames = []

    if hidden_time is None:
        hidden_time = float(rng.uniform(5.0, 45.0))

    # Reset so target is hidden behind hidden_screen, robot starts at HOME
    env.reset(seed=seed, target=target, start=f"look_{hidden_screen}")
    env.set_gantry(HOME)
    t_curr = 0.0

    # Ensure target is not visible from front
    assert not env.front_visible(target), f"S2 requires target {target} hidden behind {hidden_screen}"
    logs.append(_create_observation(episode_id, t_curr, env, target))

    # Hidden wait phase
    logs.append(_create_event(episode_id, t_curr, "hidden_wait", duration_s=round(hidden_time, 2), screen=hidden_screen))
    t_curr += hidden_time

    # Robot moves to inspect the hiding place
    look_target = env.hide_center(hidden_screen)
    t_look_start = t_curr
    arrived = env.goto([look_target[0], look_target[1], Z_SAFE], g=1.0)
    t_curr += 2.5
    
    # HARD RULE: Must verify wrist sees target now
    sees_target = env.wrist_sees(target)
    logs.append(_create_action_result(episode_id, t_curr, "look", sees_target and arrived, t_curr - t_look_start,
                                      screen=hidden_screen))
    assert sees_target, "HARD RULE VIOLATION: Target was expected to be seen by wrist camera after look!"

    # Now that it's visible to wrist camera, execute grasp and place
    success, expert_frames = run_expert(env, target, rng, record=record)
    if record:
        frames.extend(expert_frames)
    duration = len(expert_frames) * 0.1 if expert_frames else 8.5
    t_curr += duration

    logs.append(_create_action_result(episode_id, t_curr, "pick_and_place", success, duration))
    gt_pos = env.obj_pos(target)
    logs.append(_create_episode_end(episode_id, "S2", target, success, t_curr, gt_pos,
                                    hidden_time_s=round(hidden_time, 2)))

    return success, logs, frames


# ---------------------------------------------------------------------------
# S3: OBJECT MOVED WHILE HIDDEN WITH DISTURBANCE SENSOR (q, d, f)
# ---------------------------------------------------------------------------
def run_s3(env, seed, target="bottle_blue", hidden_screen="L", q=0.5, d=0.8, f=0.1,
           hidden_time=None, record=False):
    """Scenario 3: Target starts hidden behind hidden_screen.
    While hidden:
    - Object moves with probability q to another location (other screen or open table).
    - Sensor under hidden_screen detects move with probability d.
    - Sensor triggers false alarm with probability f if object did NOT move.
    Robot uses sensory evidence and search strategy to find and fetch target.
    """
    rng = np.random.default_rng(seed)
    episode_id = f"S3-seed{seed}-{target}"
    logs = []
    frames = []

    if hidden_time is None:
        hidden_time = float(rng.uniform(10.0, 60.0))

    # Target starts hidden behind hidden_screen, robot at HOME
    env.reset(seed=seed, target=target, start=f"look_{hidden_screen}")
    env.set_gantry(HOME)
    t_curr = 0.0

    assert not env.front_visible(target), f"S3 requires target {target} initially hidden behind {hidden_screen}"
    logs.append(_create_observation(episode_id, t_curr, env, target))

    # Determine other hiding places
    available_screens = [s for s in env.screen_geoms.keys() if s != hidden_screen]
    other_screen = available_screens[0] if available_screens else "R"

    # Step 1: Object movement process with probability q
    moved = bool(rng.random() < q)
    move_dest = None
    if moved:
        # Check if other_screen is already congested by another object
        placed = [env.obj_pos(n)[:2] for n in OBJECTS if n != target]
        other_center = env.hide_center(other_screen)[0]
        other_screen_occupied = any(abs(p[0] - other_center) < 0.10 for p in placed)

        # 50% chance moved to another screen (if free), otherwise moved to open table
        move_to_open = bool(rng.random() < 0.5) or other_screen_occupied
        if move_to_open:
            move_dest = "OPEN"
            # Sample an open position that is front-visible
            new_xy = env._sample_xy(rng, hidden=False, region=None, others=placed)
        else:
            move_dest = other_screen
            new_xy = env._sample_xy(rng, hidden=True, region=other_screen, others=placed)
        
        env.move_object(target, new_xy)
        logs.append(_create_event(episode_id, t_curr + hidden_time * 0.5, "object_moved",
                                  from_zone=hidden_screen, to_zone=move_dest,
                                  new_xy=[round(float(new_xy[0]), 3), round(float(new_xy[1]), 3)]))

    # Step 2: Sensor detection process (detection rate d, false alarm rate f)
    if moved:
        sensor_triggered = bool(rng.random() < d)
    else:
        sensor_triggered = bool(rng.random() < f)

    if sensor_triggered:
        sensor_t = t_curr + hidden_time * 0.75
        logs.append(_create_event(episode_id, sensor_t, "zone_disturbed",
                                  zone=hidden_screen, trigger_cause="detection" if moved else "false_alarm"))

    t_curr += hidden_time

    # Step 3: Search and Retrieval Logic
    relooks = 0
    # First: check if front camera can see target (e.g. if moved to OPEN)
    if env.front_visible(target):
        # Target in plain sight!
        logs.append(_create_event(episode_id, t_curr, "target_spotted_front", zone="OPEN"))
    else:
        # Target is hidden. Robot checks initial location first
        look_c = env.hide_center(hidden_screen)
        env.goto([look_c[0], look_c[1], Z_SAFE], g=1.0)
        relooks += 1
        t_curr += 2.5
        
        if env.wrist_sees(target):
            logs.append(_create_action_result(episode_id, t_curr, "look", True, 2.5, screen=hidden_screen))
        else:
            # Not there! Search alternate screen
            logs.append(_create_action_result(episode_id, t_curr, "look", False, 2.5,
                                              screen=hidden_screen, note="stale_memory_search_other"))
            alt_c = env.hide_center(other_screen)
            env.goto([alt_c[0], alt_c[1], Z_SAFE], g=1.0)
            relooks += 1
            t_curr += 2.5
            found_alt = env.wrist_sees(target)
            logs.append(_create_action_result(episode_id, t_curr, "look", found_alt, 2.5, screen=other_screen))

    # HARD RULE CHECK: Can the robot see the object right now?
    can_see = env.front_visible(target) or env.wrist_sees(target)
    assert can_see, f"HARD RULE VIOLATION: Cannot see {target} before grasp attempt!"

    # Execute grasp and placement
    success, expert_frames = run_expert(env, target, rng, record=record)
    if record:
        frames.extend(expert_frames)
    duration = len(expert_frames) * 0.1 if expert_frames else 8.5
    t_curr += duration

    logs.append(_create_action_result(episode_id, t_curr, "pick_and_place", success, duration))
    gt_pos = env.obj_pos(target)
    logs.append(_create_episode_end(
        episode_id, "S3", target, success, t_curr, gt_pos,
        configured_q=q, configured_d=d, configured_f=f,
        moved=moved, move_dest=move_dest, sensor_triggered=sensor_triggered,
        relooks=relooks, hidden_time_s=round(hidden_time, 2)
    ))

    return success, logs, frames


# ---------------------------------------------------------------------------
# S4: FAILED GRASP AND AUTONOMOUS RECOVERY
# ---------------------------------------------------------------------------
def run_s4(env, seed, target="box_green", record=False):
    """Scenario 4: Grasp failure simulation.
    Robot attempts grasp with a deliberate offset resulting in gripper closing on nothing
    (grip drops to 0.0), logs grasp_failed, then recovers autonomously with a clean grasp.
    """
    rng = np.random.default_rng(seed)
    episode_id = f"S4-seed{seed}-{target}"
    logs = []
    frames = []

    # Reset with target visible
    env.reset(seed=seed, target=target, start="home")
    t_curr = 0.0

    assert env.front_visible(target), f"S4 requires target {target} to be front-visible"
    logs.append(_create_observation(episode_id, t_curr, env, target))

    p = env.obj_pos(target)
    zs = Z_SAFE

    # Attempt 1: Deliberately offset grasp (offset by 0.06m in X, outside graspable threshold 0.035m)
    offset_x = 0.06
    env.goto([p[0] + offset_x, p[1], zs], g=1.0)
    grasp_z = REST_Z[target] + 0.03
    env.goto([p[0] + offset_x, p[1], grasp_z], g=1.0)
    
    # Close gripper on empty space
    for _ in range(5):
        cur = env.grip_pos()
        env.step([cur[0], cur[1], cur[2], 0.0])
    t_curr += 3.0

    # Verify grasp failure condition: gripper closed on nothing (grip == 0.0, attached is None)
    is_failed = (env.attached is None) and (env.grip <= 0.05)
    assert is_failed, f"Expected grasp failure, but attached={env.attached}, grip={env.grip}"

    logs.append(_create_event(episode_id, t_curr, "grasp_failed",
                              grip=round(float(env.grip), 2),
                              attached=env.attached,
                              note="gripper closed on nothing"))
    logs.append(_create_action_result(episode_id, t_curr, "grasp_attempt_1", False, 3.0))

    # Recovery Phase: Re-open gripper, ascend to safe height, realign precisely with target
    logs.append(_create_event(episode_id, t_curr, "recovery_initiated", strategy="reopen_and_realign"))
    env.goto([env.grip_pos()[0], env.grip_pos()[1], zs], g=1.0)
    t_curr += 1.5

    # HARD RULE CHECK before second grasp attempt
    can_see = env.front_visible(target) or env.wrist_sees(target)
    assert can_see, "HARD RULE VIOLATION: Cannot see target during grasp recovery!"

    # Attempt 2: Scripted expert completes precise grasp and deposit
    success, expert_frames = run_expert(env, target, rng, record=record)
    if record:
        frames.extend(expert_frames)
    duration = len(expert_frames) * 0.1 if expert_frames else 8.5
    t_curr += duration

    logs.append(_create_event(episode_id, t_curr, "grasp_recovered",
                              target=target, in_tray=env.in_tray(target)))
    logs.append(_create_action_result(episode_id, t_curr, "grasp_attempt_2", success, duration))
    gt_pos = env.obj_pos(target)
    logs.append(_create_episode_end(episode_id, "S4", target, success, t_curr, gt_pos,
                                    grasp_attempts=2, initial_grasp_failed=True))

    return success, logs, frames
