"""Summarise and compare rollout CSVs (output of ai/rollout.py).

    python ai/summarize.py r2_60.csv                         # one run
    python ai/summarize.py r2_60.csv --vs smolvla_60_results.csv   # paired comparison on the same seeds
"""
import argparse, csv, math, sys
from collections import defaultdict

def wilson(k, n, z=1.96):
    if n == 0: return 0.0, 0.0
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - h) / d, (c + h) / d

def load(f): return list(csv.DictReader(open(f)))

def table(rows, key):
    by = defaultdict(lambda: [0, 0])
    for r in rows:
        by[r[key]][0] += int(r["success"]); by[r[key]][1] += 1
    return "   ".join(f"{k}: {v[0]}/{v[1]} ({v[0]/v[1]:.0%})" for k, v in sorted(by.items()))

def report(name, rows):
    k = sum(int(r["success"]) for r in rows); n = len(rows); lo, hi = wilson(k, n)
    print(f"{name}: {k}/{n} = {k/n:.1%}   95% CI {lo:.1%}-{hi:.1%}")
    print("  by start :", table(rows, "start")); print("  by target:", table(rows, "target"))
    if k:
        st = sorted(int(r["steps"]) for r in rows if r["success"] == "1")
        print(f"  successful episodes: median {st[len(st)//2]} steps ({st[len(st)//2]/10:.1f} s)")

def mcnemar_p(b, c):
    n = b + c
    if n == 0: return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--vs")
    a = ap.parse_args()
    new = load(a.csv); report(a.csv, new)
    if a.vs:
        old = load(a.vs); print(); report(a.vs, old)
        o = {r["seed"]: int(r["success"]) for r in old}; nw = {r["seed"]: int(r["success"]) for r in new}
        common = sorted(set(o) & set(nw))
        gained = sum(1 for s in common if nw[s] and not o[s]); lost = sum(1 for s in common if o[s] and not nw[s])
        print(f"\npaired on {len(common)} shared seeds: gained {gained}, lost {lost}, unchanged {len(common)-gained-lost}")
        print(f"exact McNemar p-value for 'no real change': {mcnemar_p(gained, lost):.3f}  (small p = the change is probably real)")
        if len(common) != len(new): print("WARNING: not all seeds are shared; use the same --seed0/--episodes for a fair comparison", file=sys.stderr)
