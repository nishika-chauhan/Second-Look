from dataclasses import dataclass
from typing import Optional

HALF_LIFE_S = 20.0      # confidence halves every 20 s while the object is out of sight (tune!)
DISTURB_FACTOR = 0.3    # multiply confidence by this when something disturbed the hidden area
C_RELOOK = 8.0          # cost (seconds) of taking a second look
C_FAIL = 40.0           # cost (seconds) of acting on a wrong belief and failing

@dataclass
class Belief:
    name: str
    pos: tuple                      # last known (x, y) on the table
    conf: float = 1.0               # 0..1: how sure we are it is still at pos
    last_update: float = 0.0        # sim time of the last update
    hidden_by: Optional[str] = None # which occluder hides it right now (None = visible)

def tick(b: Belief, now: float) -> None:
    """Call every step: fade confidence while the object is hidden."""
    if b.hidden_by is not None:
        b.conf *= 0.5 ** ((now - b.last_update) / HALF_LIFE_S)
    b.last_update = now

def seen(b: Belief, pos, now: float) -> None:
    b.pos, b.conf, b.last_update, b.hidden_by = pos, 1.0, now, None

def occluded(b: Belief, occluder: str, now: float) -> None:
    tick(b, now); b.hidden_by = occluder

def disturbed(b: Belief, now: float) -> None:
    tick(b, now); b.conf *= DISTURB_FACTOR

def decide(b: Belief) -> str:
    """Take a second look if the expected cost of being wrong is higher than the cost of looking."""
    return "relook" if (1.0 - b.conf) * C_FAIL > C_RELOOK else "act"

if __name__ == "__main__":
    b = Belief("bottle_blue", (0.0, 0.12))
    seen(b, (0.0, 0.12), now=0.0)
    occluded(b, "screen", now=1.0)
    for t in (3, 6, 8, 12):
        tick(b, float(t)); print(f"t={t:>2}s  conf={b.conf:.2f}  ->", decide(b))
    disturbed(b, now=13.0); print(f"after disturbance conf={b.conf:.2f} ->", decide(b))
    seen(b, (0.2, 0.05), now=20.0); print(f"seen again      conf={b.conf:.2f} ->", decide(b))
