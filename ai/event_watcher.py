"""Wire scenario_logs.jsonl zone-disturbed events into regions_belief (Week 2, Step 5).

Reads C's out/scenario_logs.jsonl and calls regions_belief.disturbed()
for each zone_disturbed sensor event, applying the P(moved) > 0.7
threshold recommended after observing a 12% false-alarm rate in S3.

Two modes
---------
1. **Batch replay** (offline, for testing):
       python ai/event_watcher.py --log out/scenario_logs.jsonl
   Replays the whole log against a fresh Belief object and prints
   how confidence evolved.

2. **Live tail** (online, for the episode runner):
   Call `process_event(event_dict, beliefs, now)` from your episode
   loop whenever a new log line arrives.  The beliefs dict is mutated
   in-place via regions_belief.disturbed().

P(moved) threshold
------------------
C's S3 logs show ~12% false-alarm rate.  The plan says:
   "treat zone_disturbed as evidence only when P(object moved) > 0.7"
We implement this by gating on a per-place cumulative alarm count:
   - first alarm  → small nudge (conf × DISTURB), not enough to flip
   - second alarm in same episode → update belief properly
   - single alarm from a DIFFERENT zone than remembered → p_moved > 0.7
     (object is not there; this is strong evidence), update belief.

In practice `regions_belief.disturbed()` already multiplies conf by
DISTURB=0.35.  The threshold logic here decides *whether* to call it.
"""

from __future__ import annotations

import argparse
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

import regions_belief as RB

# Minimum P(moved) to act on a zone_disturbed event.
# Derived from: 1 false alarm in 8 episodes ≈ 12% false-alarm rate.
# One alarm at the remembered place barely moves P(moved) above 0.5;
# we wait for a second alarm OR an alarm at a different place.
P_MOVED_THRESHOLD = 0.70


def _p_moved(event: dict, belief: RB.Belief, alarm_counts: dict) -> float:
    """Estimate P(object moved) given this event and running alarm history.

    Simple heuristic matching the 12% false-alarm context:
      - Alarm at a DIFFERENT zone than the remembered place → p=0.85
        (we had no reason to expect noise there; likely a real disturbance)
      - Second+ alarm at the SAME zone in this episode → p=0.75
        (repeated alarms are less likely all false)
      - First alarm at the SAME zone → p=0.40 (probably false, ignore)
    """
    zone = event.get("zone")
    key  = zone or "?"
    count = alarm_counts.get(key, 0) + 1   # this event not yet counted

    if zone != belief.place:
        return 0.85   # different zone alarm → strong evidence
    elif count >= 2:
        return 0.75   # repeated same-zone alarm → act
    else:
        return 0.40   # first same-zone alarm → likely false positive


def process_event(
    event: dict,
    beliefs: dict,          # {obj_name: RB.Belief}
    now: float,
    alarm_counts: dict | None = None,
    verbose: bool = False,
) -> bool:
    """Process one parsed log event dict.  Returns True if belief was updated.

    Parameters
    ----------
    event        : dict   one parsed JSON line from scenario_logs.jsonl
    beliefs      : dict   {obj_name: RB.Belief}  mutated in-place
    now          : float  current sim time in seconds
    alarm_counts : dict   per-(obj,zone) alarm counter; pass the same dict
                          across calls within an episode to enable the
                          "second alarm" heuristic.  Pass None to skip.
    verbose      : bool   print a line for each event processed
    """
    if event.get("type") != "event" or event.get("event") != "zone_disturbed":
        return False

    zone: str      = event.get("zone", "?")
    triggered: bool = event.get("sensor_triggered", True)

    if not triggered:
        return False   # sensor didn't actually fire

    updated = False
    for obj_name, belief in beliefs.items():
        ac = alarm_counts or {}
        key = (obj_name, zone)
        p_moved = _p_moved(event, belief, {zone: ac.get(key, 0)})

        if alarm_counts is not None:
            alarm_counts[key] = alarm_counts.get(key, 0) + 1

        if p_moved >= P_MOVED_THRESHOLD:
            old_conf = belief.conf
            RB.disturbed(belief, zone, now)
            updated = True
            if verbose:
                print(f"  [event_watcher] t={now:.1f}s  zone_disturbed zone={zone!r}"
                      f"  obj={obj_name}  p_moved={p_moved:.2f}"
                      f"  conf: {old_conf:.3f} → {belief.conf:.3f}")
        else:
            if verbose:
                print(f"  [event_watcher] t={now:.1f}s  zone_disturbed zone={zone!r}"
                      f"  obj={obj_name}  p_moved={p_moved:.2f} < threshold — ignored")

    return updated


# ---------------------------------------------------------------------------
# Batch replay (offline / demo)
# ---------------------------------------------------------------------------

def replay_log(log_path: str, verbose: bool = True) -> None:
    """Read scenario_logs.jsonl and replay all zone_disturbed events."""
    path = Path(log_path)
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)

    # Start a fresh belief for a single object as a demo
    belief = RB.Belief(name="bottle_blue", place="L", conf=1.0, t=0.0)
    beliefs = {"bottle_blue": belief}
    alarm_counts: dict = {}

    print(f"\nReplaying {path.name} against a fresh Belief(place='L', conf=1.0)\n")
    print(f"  P_MOVED_THRESHOLD = {P_MOVED_THRESHOLD}")
    print(f"  DISTURB factor    = {RB.DISTURB}  (confidence multiplier when threshold met)")
    print()

    n_events = n_acted = 0
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if event.get("type") != "event" or event.get("event") != "zone_disturbed":
                continue

            t = float(event.get("t", 0.0))
            n_events += 1

            # Tick belief to current time before processing event
            RB.tick(belief, t, hidden=True)

            acted = process_event(event, beliefs, t,
                                  alarm_counts=alarm_counts, verbose=verbose)
            if acted:
                n_acted += 1

    print()
    print(f"Summary: {n_events} zone_disturbed events, {n_acted} acted on")
    print(f"Final belief: place={belief.place!r}  conf={belief.conf:.4f}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Replay zone_disturbed events into regions_belief")
    ap.add_argument("--log", default="out/scenario_logs.jsonl",
                    help="Path to scenario_logs.jsonl (default: out/scenario_logs.jsonl)")
    ap.add_argument("--quiet", action="store_true", help="Suppress per-event output")
    args = ap.parse_args()
    replay_log(args.log, verbose=not args.quiet)


if __name__ == "__main__":
    main()
