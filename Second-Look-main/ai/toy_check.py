"""TOY sanity check of the search-order idea (NOT project results - the world here is made up).

World: the object was last seen going behind the LEFT screen. While hidden, a 'person' may move it
(to behind the right screen or to an open spot). A sensor under the left screen notices the move with
probability 0.8 (and cries wolf sometimes). Compare three policies. Run:  python ai/toy_check.py
"""
import random
from regions_belief import Belief, disturbed, search_order, tick, seen

PICK_S, LOOK_S, RATE = 10.0, 8.0, 1 / 90.0     # seconds to pick, seconds per look, moves per second


def episode(policy, rng):
    wait = rng.uniform(0, 90)
    where = "L"
    if rng.random() < 1 - 2.718281828 ** (-RATE * wait):
        where = rng.choice(["R", "OPEN"])
    sensor = (where != "L" and rng.random() < 0.8) or (where == "L" and rng.random() < 0.10)
    if where == "OPEN":                                   # the front camera sees it for free
        return True, PICK_S
    b = Belief("bottle", "L"); seen(b, "L", 0.0); tick(b, wait, hidden=True)
    if sensor:
        disturbed(b, "L", wait)
    if policy == "trust":       order = ["L"]
    elif policy == "sweep":     order = ["L", "R"]        # fixed order
    else:                       order = search_order(b, visible_in_front=False)
    t = 0.0
    for pl in order:
        t += LOOK_S
        if pl == where:
            return True, t + PICK_S
    return False, t


for policy in ["trust", "sweep", "ours"]:
    rng = random.Random(1); n, ok, tt = 20000, 0, 0.0
    for _ in range(n):
        s, t = episode(policy, rng); ok += s; tt += t
    print(f"{policy:>6}: success {100*ok/n:5.1f}%   mean time {tt/n:5.1f} s")
