"""Feed zone_disturbed sensor events into regions_belief (Week 2 step 5, corrected).

Plan Part 6.1: "Touch or pressure sensor under a place fires -> confidence x 0.35
for that place." One alarm is enough. The 0.35 factor is already a soft update
that prices in false alarms (C's S3 logs show about 12 %), so alarms are NOT
gated or ignored. An earlier version of this file ignored the first alarm at the
remembered place; that broke the plan's own worked example (0.75 -> 0.2625,
search order flips to the other screen) and has been removed.

Behaviour of RB.disturbed(): the belief decays up to `now`, then, only if the
alarm is for the remembered place, confidence is multiplied by DISTURB.
Alarms for other places only advance the clock.

Offline replay of C's log:
    python ai/event_watcher.py --log out/scenario_logs.jsonl
Live use inside an episode loop:
    from event_watcher import process_event
    process_event(event_dict, {"bottle_blue": belief}, now=t)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import regions_belief as RB  # noqa: E402


def is_alarm(event: dict) -> bool:
    return (event.get("type") == "event" and event.get("event") == "zone_disturbed"
            and bool(event.get("sensor_triggered", True)))


def process_event(event: dict, beliefs: dict, now: float, verbose: bool = False) -> bool:
    """Apply one log event. Returns True if some belief's confidence was cut."""
    if not is_alarm(event):
        return False
    zone = event.get("zone", "?")
    cut = False
    for name, b in beliefs.items():
        before = b.conf
        RB.disturbed(b, zone, now)
        if zone == b.place:
            cut = True
        if verbose:
            tag = "cut x%.2f" % RB.DISTURB if zone == b.place else "other place, clock only"
            print(f"  t={now:6.1f}s  alarm zone={zone!r}  {name}: {before:.3f} -> {b.conf:.3f}  ({tag})")
    return cut


def replay_log(log_path: str, verbose: bool = True) -> None:
    path = Path(log_path)
    if not path.exists():
        sys.exit(f"{path} not found")
    belief = RB.Belief(name="bottle_blue", place="L", conf=1.0, t=0.0)
    beliefs = {"bottle_blue": belief}
    n = cuts = 0
    with path.open() as fh:
        for line in fh:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not is_alarm(event):
                continue
            n += 1
            cuts += process_event(event, beliefs, float(event.get("t", 0.0)), verbose)
    print(f"\n{n} alarms, {cuts} at the remembered place. final conf={belief.conf:.4f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="out/scenario_logs.jsonl")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    replay_log(a.log, verbose=not a.quiet)
