"""Tier-2 style scoring of the planner policies on C's held-out scenarios (plan Part 7).

    python ai/eval.py --scenarios contracts/heldout_eval_scenarios.jsonl            # P0-P3, no network
    python ai/eval.py --scenarios ... --nemotron 50 --timeout 8                      # adds P5 (needs NEBIUS_API_KEY)

Timeline per scenario (C's sim/scenarios.py, confirmed by C): the object is hidden for
delay_s seconds. If moved, it moves at 0.50 * delay_s to the other place. If sensor_fired
(a true alarm or a false alarm) the sensor fires at 0.75 * delay_s under the place where the
object WAS (assumption: same zone our server uses; C's file gives no zone). The robot then
searches. Looking costs RB.LOOK_COST_S (8 s) per place, picking 6 s (as in server.py).
Success = object in the tray within 90 s of the request (plan 7.2).

No rendering and no VLA: this measures the memory + planner layer only (plan Tier 2).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import sys
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import regions_belief as RB  # noqa: E402
import event_watcher as EW  # noqa: E402
import planner as PL  # noqa: E402

PICK_COST_S = 6.0
DEADLINE_S = 90.0
OTHER = {"L": "R", "R": "L"}


def load_scenarios(path):
    with open(path) as fh:
        return [json.loads(l) for l in fh if l.strip()]


def timeline(sc):
    d = float(sc["delay_s"])
    t_sensor = 0.75 * d if sc.get("sensor_fired") else None
    return d, t_sensor


# ---- the policies -----------------------------------------------------------------
def order_p0(sc):  return [sc["initial_place"]]                               # trust memory, give up
def order_p1(sc):  return ["L", "R"]                                          # sweep
def order_p2(sc, T=30.0):                                                      # timer
    return [sc["initial_place"], OTHER[sc["initial_place"]]] if sc["delay_s"] < T else ["L", "R"]


def run_fixed(sc, order):
    true, looks, t = sc["true_place"], 0, 0.0
    for place in order:
        looks += 1
        t += RB.LOOK_COST_S[place]
        if place == true:
            return dict(found=True, looks=looks, t=t + PICK_COST_S, llm_calls=0, lat=[], offline=0)
    return dict(found=False, looks=looks, t=t, llm_calls=0, lat=[], offline=0)


def run_planner(sc, planner, grasp_ok=True):
    d, t_sensor = timeline(sc)
    obj = sc["target"]
    b = RB.Belief(obj, sc["initial_place"], 1.0, 0.0)
    ctx = PL.PlanContext(obj=obj, now=0.0, last_seen_t=0.0)
    if t_sensor is not None:
        RB.tick(b, t_sensor, hidden=True)
        ev = {"type": "event", "kind": "zone_disturbed", "zone": sc["initial_place"],
              "sensor_triggered": True, "t": t_sensor}
        EW.process_event(ev, {obj: b}, t_sensor)
        ctx.sensor_events.append((t_sensor, sc["initial_place"]))
    RB.tick(b, d, hidden=True)
    ctx.now = d
    t, looks, lats, offline, llm_calls, found = 0.0, 0, [], 0, 0, False
    for _ in range(len(RB.HIDING) + 1):
        dec = planner.decide(b, ctx, False)
        if dec.get("engine") == "llm" or dec.get("fallback_reason"):
            llm_calls += 1
            lats.append(dec.get("latency_ms", 0))
            offline += int(bool(dec.get("offline")))
        if dec["action"] != "look":
            break
        place = dec["target"]
        looks += 1
        t += RB.LOOK_COST_S[place]
        found = place == sc["true_place"]
        PL.note_look_result(b, ctx, place, found, d + t)
        if found:
            break
    if found:
        t += PICK_COST_S
        found = grasp_ok
    return dict(found=found, looks=looks, t=t, llm_calls=llm_calls, lat=lats, offline=offline)


# ---- statistics -------------------------------------------------------------------
def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    den = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - h) / den, (c + h) / den


def boot_ci(vals, n_boot=5000, seed=0):
    rng = random.Random(seed)
    m = len(vals)
    if m == 0:
        return 0.0, 0.0
    means = sorted(sum(vals[rng.randrange(m)] for _ in range(m)) / m for _ in range(n_boot))
    return means[int(0.025 * n_boot)], means[int(0.975 * n_boot)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", default="contracts/heldout_eval_scenarios.jsonl")
    ap.add_argument("--out", default="eval_results.csv")
    ap.add_argument("--nemotron", type=int, default=0, help="also run P5 on the first N scenarios")
    ap.add_argument("--timeout", type=float, default=PL.TIMEOUT_S)
    ap.add_argument("--timer-T", type=float, default=30.0)
    ap.add_argument("--grasp-fail-prob", type=float, default=0.0)
    a = ap.parse_args()

    scs = load_scenarios(a.scenarios)
    rng = random.Random(0)
    grasp = [rng.random() >= a.grasp_fail_prob for _ in scs]       # same draws for every policy
    rule = PL.Planner(mode="rule")
    rows = []

    def add(pol, sc, r):
        succ = bool(r["found"] and r["t"] <= DEADLINE_S)
        rows.append(dict(policy=pol, eval_id=sc["eval_id"], scenario=sc["scenario"], seed=sc["seed"],
                         target=sc["target"], delay_s=sc["delay_s"], initial_place=sc["initial_place"],
                         moved=int(sc["moved"]), true_place=sc["true_place"], sensor_fired=int(sc["sensor_fired"]),
                         success=int(succ), looks=r["looks"], time_to_finish_s=round(r["t"], 1),
                         llm_calls=r["llm_calls"], mean_llm_ms=round(sum(r["lat"]) / len(r["lat"]), 0) if r["lat"] else 0,
                         max_llm_ms=max(r["lat"]) if r["lat"] else 0, offline=r["offline"]))

    for sc, g in zip(scs, grasp):
        for pol, order in (("P0_trust_memory", order_p0(sc)), ("P1_sweep", order_p1(sc)),
                           ("P2_timer", order_p2(sc, a.timer_T))):
            r = run_fixed(sc, order)
            r["found"] = r["found"] and g
            add(pol, sc, r)
        add("P3_rule", sc, run_planner(sc, rule, g))
    if a.nemotron:
        llm = PL.Planner(mode="llm", timeout_s=a.timeout)
        print("Nemotron warm-up:", llm.warm_up())
        for sc, g in list(zip(scs, grasp))[:a.nemotron]:
            add("P5_nemotron", sc, run_planner(sc, llm, g))
        print("Nemotron planner stats:", json.dumps(llm.stats()))

    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    pols = list(dict.fromkeys(r["policy"] for r in rows))
    print(f"\n{len(scs)} scenarios | success = in tray within {DEADLINE_S:.0f} s of the request | 95% CIs: Wilson (success), bootstrap (mean looks)\n")
    print(f"{'policy':16s} {'n':>3s} {'success':>12s} {'95% CI':>14s} {'mean looks':>11s} {'looks CI':>14s} {'mean time':>10s}")
    for p in pols:
        rs = [r for r in rows if r["policy"] == p]
        k = sum(r["success"] for r in rs)
        lo, hi = wilson(k, len(rs))
        lk = [r["looks"] for r in rs]
        llo, lhi = boot_ci(lk)
        print(f"{p:16s} {len(rs):3d} {k:5d}/{len(rs):<3d} {k/len(rs):5.0%}  {lo:5.0%}-{hi:<5.0%} {sum(lk)/len(lk):11.2f} {llo:6.2f}-{lhi:<6.2f} {sum(r['time_to_finish_s'] for r in rs)/len(rs):9.1f}s")
    print("\nPaired difference in looks, P3_rule minus other (negative = P3 looks less). Same scenarios for every policy.")
    base = {r["eval_id"]: r for r in rows if r["policy"] == "P3_rule"}
    for p in pols:
        if p == "P3_rule":
            continue
        diffs = [base[r["eval_id"]]["looks"] - r["looks"] for r in rows if r["policy"] == p and r["eval_id"] in base]
        lo, hi = boot_ci(diffs)
        print(f"  vs {p:16s} mean {sum(diffs)/len(diffs):+.2f}  95% CI [{lo:+.2f}, {hi:+.2f}]  (n={len(diffs)})")
    print("\nP3_rule by case:")
    for name, pred in (("not moved, no sensor", lambda r: not r["moved"] and not r["sensor_fired"]),
                       ("moved, sensor fired (true alarm)", lambda r: r["moved"] and r["sensor_fired"]),
                       ("moved, sensor missed", lambda r: r["moved"] and not r["sensor_fired"]),
                       ("not moved, sensor fired (false alarm)", lambda r: not r["moved"] and r["sensor_fired"])):
        sel = [r for r in rows if r["policy"] == "P3_rule" and pred(r)]
        if sel:
            print(f"  {name:40s} n={len(sel):2d}  mean looks {sum(r['looks'] for r in sel)/len(sel):.2f}  success {sum(r['success'] for r in sel)}/{len(sel)}")
    dash = os.path.splitext(a.out)[0] + "_dashboard.csv"
    labels = {"P0_trust_memory": "P0 Trust memory", "P1_sweep": "P1 Sweep", "P2_timer": "P2 Timer",
              "P3_rule": "P3 Ours (rule)", "P5_nemotron": "P5 Ours + Nemotron"}
    with open(dash, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["condition", "success", "total_time_s", "looks"])
        for r in rows:
            w.writerow([labels.get(r["policy"], r["policy"]), r["success"], r["time_to_finish_s"], r["looks"]])
    print(f"\nper-episode rows -> {os.path.abspath(a.out)}")
    print(f"dashboard Results-tab CSV -> {os.path.abspath(dash)}")


if __name__ == "__main__":
    main()
