"""Belief about WHERE an object is when there are several hiding places (role B). Tested (pure Python).

Places: "L" = behind the left screen, "R" = behind the right screen, "OPEN" = somewhere the front camera can see.
The robot remembers where it last saw each object and how much it still trusts that memory:
  * trust fades while the object is out of sight            (half-life HALF_LIFE_S)
  * trust drops when a sensor says "that place was disturbed" (multiply by DISTURB)
  * if the front camera does NOT see the object, it cannot be in OPEN (negative evidence)
Then it searches the hiding places in the order that finds the object fastest: highest p / cost first.
"""
from dataclasses import dataclass

HALF_LIFE_S = 60.0     # tune this (or learn it from simulated episodes)
DISTURB = 0.35         # confidence multiplier when the sensor fires for the remembered place
LOOK_COST_S = {"L": 8.0, "R": 8.0}      # seconds to fly over a hiding place and look
HIDING = ["L", "R"]


@dataclass
class Belief:
    name: str
    place: str = "L"          # where it was last seen
    conf: float = 1.0         # probability it is STILL there
    t: float = 0.0            # time of the last update


def tick(b: Belief, now: float, hidden: bool) -> None:
    if hidden:
        b.conf *= 0.5 ** ((now - b.t) / HALF_LIFE_S)
    b.t = now


def seen(b: Belief, place: str, now: float) -> None:
    b.place, b.conf, b.t = place, 1.0, now


def disturbed(b: Belief, place: str, now: float, hidden: bool = True) -> None:
    tick(b, now, hidden)
    if place == b.place:
        b.conf *= DISTURB


def place_probs(b: Belief, visible_in_front: bool) -> dict:
    """P(object is at each hiding place) given that we know whether the front camera sees it."""
    if visible_in_front:
        return {"OPEN": 1.0}
    p = {pl: 0.0 for pl in HIDING}
    others = [pl for pl in HIDING if pl != b.place]
    if b.place in p:
        p[b.place] = b.conf
    spread = (1.0 - b.conf) / max(len(others) + 1, 1)      # the rest is shared with "somewhere else"
    for pl in others:
        p[pl] += spread
    total = sum(p.values())                                  # negative evidence: OPEN is ruled out
    return {pl: v / total for pl, v in p.items()}


def search_order(b: Belief, visible_in_front: bool) -> list:
    """Hiding places sorted by probability per second of looking (best first)."""
    p = place_probs(b, visible_in_front)
    return sorted((pl for pl in HIDING if pl in p), key=lambda pl: -p[pl] / LOOK_COST_S[pl])
