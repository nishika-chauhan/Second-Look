"""Planner: rule engine + Nemotron with a hard fallback (role B, plan Part 6.3).

The rule planner is the workhorse and always runs. Nemotron (Nebius Token
Factory) is asked only when the situation is not routine:
  * the top two places are nearly tied,
  * a look came back empty,
  * the goal is natural language ("bring me my medicine").
If the LLM call fails, times out (default 5 s), or returns something that
breaks the rules, the rule decision is used and the decision is flagged
`offline: true` so the dashboard can show "offline: rule engine".

Modes
  "rule"  never call the LLM
  "auto"  call it only for non-routine cases      (policy P5 in the plan)
  "llm"   call it on every decision where the object is not yet visible
          (use for the rule-vs-Nemotron agreement study)

Output is the `decision` message of plan Part 2.2:
  engine ("rule" | "llm"), action (look|pick|ask|finish), target, command,
  why, latency_ms.  Extra fields (offline, fallback_reason, model,
  agree_with_rule) are additive; tell A before the dashboard relies on them.

The prompt deliberately does NOT contain the rule planner's answer, so the
agreement numbers are an honest comparison.

Quick demo (no network):   python ai/planner.py
Against real Nemotron:     python ai/planner.py --mode llm
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import regions_belief as RB  # noqa: E402

try:  # nemotron_client exits at import if `openai` is missing, so guard it
    import nemotron_client as NC  # noqa: E402
except (ImportError, SystemExit):  # pragma: no cover - depends on environment
    NC = None

# Wording must match the training task strings in the dataset exactly,
# because the VLA was fine-tuned on "pick up the red cup and place it in the tray".
OBJECTS = {"cup_red": "red cup", "bottle_blue": "blue bottle", "box_green": "green box"}
PLACE_NAMES = {"L": "left screen", "R": "right screen"}
ACTIONS = ("look", "pick", "ask", "finish")

TIMEOUT_S = float(os.environ.get("PLANNER_TIMEOUT_S", "5.0"))   # plan: fall back after 5 s (override via env or --timeout)
MARGIN = 0.25            # top-two probability gap below this counts as "unclear"


def pick_command(obj: str) -> str:
    return f"pick up the {OBJECTS[obj]} and place it in the tray"


# ---------------------------------------------------------------------------
# Episode context (owned by the caller, one per episode)
# ---------------------------------------------------------------------------

@dataclass
class PlanContext:
    obj: Optional[str] = "bottle_blue"      # None = goal not yet resolved
    goal_text: Optional[str] = None         # natural-language request, if any
    now: float = 0.0
    last_seen_t: Optional[float] = None
    ruled_out: set = field(default_factory=set)       # places looked at and empty
    sensor_events: list = field(default_factory=list)  # [(t, place), ...]
    delivered: bool = False


def note_look_result(b, ctx: PlanContext, place: str, found: bool, now: float) -> None:
    """Evidence update after a look(place): plan Part 6.1."""
    ctx.now = now
    if found:
        RB.seen(b, place, now)
        ctx.ruled_out.clear()
        ctx.last_seen_t = now
    else:
        ctx.ruled_out.add(place)


def note_grasp_result(b, ctx: PlanContext, ok: bool, now: float) -> None:
    """Gripper closed on nothing -> memory was wrong (plan Part 6.1: about 0.05)."""
    ctx.now = now
    if not ok:
        b.conf = min(b.conf, 0.05)


# ---------------------------------------------------------------------------
# Beliefs -> probabilities
# ---------------------------------------------------------------------------

def effective_probs(b, ctx: PlanContext, visible: bool) -> dict:
    """place_probs() with looked-and-empty places forced to 0 and renormalised."""
    p = RB.place_probs(b, visible)
    if visible:
        return p
    p = {k: (0.0 if k in ctx.ruled_out else v) for k, v in p.items()}
    total = sum(p.values())
    if total <= 1e-9:
        # memory said "definitely at X" but X was empty: memory was wrong,
        # so spread evenly over whatever is left.
        left = [k for k in RB.HIDING if k not in ctx.ruled_out]
        return {k: 1.0 / len(left) for k in left} if left else {}
    return {k: v / total for k, v in p.items()}


def _ranked(p: dict) -> list:
    return sorted(p, key=lambda pl: -p[pl] / RB.LOOK_COST_S[pl])


def _mk(engine, action, target, command, why, latency_ms, **extra) -> dict:
    d = {
        "type": "decision",
        "engine": engine,
        "action": action,
        "target": target,
        "command": command,
        "why": why,
        "latency_ms": int(latency_ms),
        "offline": False,
    }
    d.update(extra)
    return d


# ---------------------------------------------------------------------------
# Rule planner
# ---------------------------------------------------------------------------

def rule_decide(b, ctx: PlanContext, visible: bool) -> dict:
    t0 = time.perf_counter()

    def done(action, target, command, why):
        return _mk("rule", action, target, command, why, (time.perf_counter() - t0) * 1000)

    if ctx.delivered:
        return done("finish", ctx.obj or "", "", "The object is in the tray.")
    if ctx.obj is None:
        return done("ask", "user", "", "I am not sure which object you mean, so I will ask.")
    if visible:
        return done("pick", ctx.obj, pick_command(ctx.obj),
                    f"The {OBJECTS[ctx.obj]} is visible, so I will pick it up.")

    p = effective_probs(b, ctx, visible)
    if not p:
        return done("ask", "user", "",
                    "I checked every hiding place and did not find it, so I will ask for help.")

    order = _ranked(p)
    target = order[0]
    name = PLACE_NAMES[target]
    pct = f"{p[target]:.0%}"

    if ctx.ruled_out:
        empty = " and ".join(PLACE_NAMES[x] for x in sorted(ctx.ruled_out))
        why = f"The {empty} was empty, so I will check the {name} next ({pct})."
    else:
        recent = [(t, pl) for t, pl in ctx.sensor_events if pl == b.place]
        if recent:
            age = max(0.0, ctx.now - recent[-1][0])
            why = (f"The {PLACE_NAMES[b.place]} was disturbed {age:.0f} s ago, so memory is shaky; "
                   f"the {name} is more likely ({pct}) and I will check it first.")
        else:
            why = (f"Last seen behind the {PLACE_NAMES[b.place]} with {b.conf:.0%} confidence; "
                   f"the {name} is the best place to look first ({pct}).")
    return done("look", target, f"fly the wrist camera over the {name}", why)


def is_routine(b, ctx: PlanContext, visible: bool, margin: float = MARGIN) -> tuple[bool, str]:
    """(routine?, reason). Non-routine cases are the ones worth an LLM call."""
    if ctx.delivered or visible:
        return True, "target visible or finished"
    if ctx.goal_text and ctx.obj is None:
        return False, "natural-language goal"
    if ctx.obj is None:
        return True, "no object (rule will ask)"
    if ctx.ruled_out:
        return False, "a look came back empty"
    p = effective_probs(b, ctx, visible)
    if len(p) >= 2:
        top = sorted(p.values(), reverse=True)
        if top[0] - top[1] < margin:
            return False, "probabilities are close"
    return True, "clear favourite"


# ---------------------------------------------------------------------------
# LLM planner
# ---------------------------------------------------------------------------

class LLMUnavailable(RuntimeError):
    pass


def _load_dotenv() -> None:
    """Make NEBIUS_API_KEY available if it only lives in a .env file."""
    key = os.environ.get("NEBIUS_API_KEY")
    if key:
        return
    here = Path(__file__).resolve().parent
    for d in (Path.cwd(), here, here.parent):
        f = d / ".env"
        if f.is_file():
            for line in f.read_text(errors="ignore").splitlines():
                line = line.strip()
                if line.startswith("NEBIUS_API_KEY") and "=" in line:
                    os.environ["NEBIUS_API_KEY"] = line.split("=", 1)[1].strip().strip("'\"")
                    return


def choose_models(ids: list) -> dict:
    """Tiering from plan 6.3: small model for routine calls, big for hard ones.
    Model ids come from models.list(); nothing is hard-coded."""
    override = os.environ.get("NEMOTRON_MODEL")
    nem = [m for m in ids if "nemotron" in m.lower()]
    if override:
        return {"small": override, "big": override}
    if not nem:
        raise LLMUnavailable("no Nemotron model in models.list()")
    small = [m for m in nem if any(s in m.lower() for s in ("nano", "mini", "small"))]
    big = [m for m in nem if any(s in m.lower() for s in ("ultra", "super"))]
    s = small[0] if small else nem[0]
    return {"small": s, "big": big[0] if big else s}


SYSTEM_PROMPT = (
    "You plan for a tabletop robot that must fetch an object hidden behind one of two screens "
    "(L = left, R = right). You may look at a screen (flying the wrist camera over it), pick the "
    "object up (only if it is visible), ask the user, or finish. Looking costs time, so prefer the "
    "place with the highest probability per second. Reply by calling the decide function. "
    "The `why` field must be one short sentence for a dashboard."
)


def build_prompt(b, ctx: PlanContext, visible: bool, p: dict) -> str:
    lines = []
    if ctx.goal_text:
        lines.append(f'User request: "{ctx.goal_text}"')
    known = ", ".join(f"{k} ({v})" for k, v in OBJECTS.items())
    lines.append(f"Known objects: {known}.")
    lines.append(f"Target object: {ctx.obj or 'NOT YET RESOLVED, choose one from the known objects'}.")
    lines.append(f"Object visible to the front camera now: {'yes' if visible else 'no'}.")
    lines.append(f"Last seen at: {b.place} ({PLACE_NAMES.get(b.place, b.place)})"
                 + (f", {ctx.now - ctx.last_seen_t:.0f} s ago." if ctx.last_seen_t is not None else "."))
    lines.append(f"Memory confidence it is still there: {b.conf:.2f} (fades with a 60 s half-life while hidden).")
    for t, pl in ctx.sensor_events:
        lines.append(f"Touch sensor under {PLACE_NAMES.get(pl, pl)} fired {max(0.0, ctx.now - t):.0f} s ago.")
    if ctx.ruled_out:
        lines.append("Looked at and found EMPTY: " + ", ".join(sorted(ctx.ruled_out)) + ".")
    if p:
        lines.append("Estimated probability per place: "
                     + ", ".join(f"{k}={v:.2f}" for k, v in sorted(p.items())) + ".")
    lines.append("Seconds to look at each place: "
                 + ", ".join(f"{k}={RB.LOOK_COST_S[k]:.0f}" for k in RB.HIDING) + ".")
    lines.append("Rules: pick only if the object is visible; never look at a place already found empty; "
                 "target for look is L or R; target for pick is the object name.")
    return "\n".join(lines)


def _validate(dec: dict, ctx: PlanContext, visible: bool) -> dict:
    """Return a cleaned decision or raise ValueError. We never trust the LLM's
    wording of the VLA command: the policy only understands its training phrases."""
    if not isinstance(dec, dict):
        raise ValueError("decision is not an object")
    action = dec.get("action")
    target = dec.get("target")
    if action not in ACTIONS:
        raise ValueError(f"unknown action {action!r}")
    why = str(dec.get("why") or "").strip()
    if not why:
        raise ValueError("empty why")
    why = why[:240]

    if action == "look":
        if visible:
            raise ValueError("look requested but object is already visible")
        if target not in RB.HIDING:
            raise ValueError(f"look target {target!r} is not a hiding place")
        if target in ctx.ruled_out:
            raise ValueError(f"look target {target!r} was already found empty")
        return {"action": "look", "target": target,
                "command": f"fly the wrist camera over the {PLACE_NAMES[target]}", "why": why}
    if action == "pick":
        if not visible:
            raise ValueError("pick requested but object is not visible")
        if target not in OBJECTS:
            raise ValueError(f"pick target {target!r} is not a known object")
        if ctx.obj is not None and target != ctx.obj:
            raise ValueError(f"pick target {target!r} differs from requested {ctx.obj!r}")
        return {"action": "pick", "target": target, "command": pick_command(target), "why": why}
    if action == "finish":
        if not ctx.delivered:
            raise ValueError("finish requested before delivery")
        return {"action": "finish", "target": str(target or ""), "command": "", "why": why}
    return {"action": "ask", "target": "user", "command": "", "why": why}


class Planner:
    def __init__(self, mode: str = "auto", client=None, models: Optional[dict] = None,
                 timeout_s: float = TIMEOUT_S, margin: float = MARGIN):
        mode = {"nemotron": "llm"}.get(mode, mode)
        if mode not in ("rule", "auto", "llm"):
            raise ValueError("mode must be rule, auto or llm")
        self.mode = mode
        self.timeout_s = timeout_s
        self.margin = margin
        self._client = client
        self._models = models
        self._llm_error: Optional[str] = None
        self._error_at = 0.0
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="planner-llm")
        self.log: list[dict] = []

    # -- LLM plumbing -------------------------------------------------------
    def _ensure_llm(self):
        if self._client is not None and self._models:
            return self._client, self._models
        if self._llm_error and time.monotonic() - self._error_at < 30:
            raise LLMUnavailable(self._llm_error)       # do not hammer a broken setup
        try:
            if NC is None:
                raise LLMUnavailable("nemotron_client/openai not importable (pip install openai)")
            _load_dotenv()
            key = os.environ.get(NC.API_KEY_ENV)
            if not key:
                raise LLMUnavailable(f"{NC.API_KEY_ENV} not set (env var or .env)")
            from openai import OpenAI
            client = OpenAI(base_url=NC.BASE_URL, api_key=key, timeout=self.timeout_s, max_retries=0)
            ids = [m.id for m in client.models.list().data]
            self._client, self._models = client, choose_models(ids)
            self._llm_error = None
            return self._client, self._models
        except LLMUnavailable as e:
            self._llm_error, self._error_at = str(e), time.monotonic()
            raise
        except Exception as e:  # network, auth, ...
            self._llm_error, self._error_at = f"{type(e).__name__}: {e}"[:200], time.monotonic()
            raise LLMUnavailable(self._llm_error) from e

    def warm_up(self) -> dict:
        """Connect, list models and send one tiny request so the first real decision
        does not pay for the TLS handshake and cold model start. Never raises."""
        t0 = time.monotonic()
        try:
            client, models = self._ensure_llm()
            model = models.get("small") or next(iter(models.values()))
            client.chat.completions.create(model=model, max_tokens=4, temperature=0,
                                           messages=[{"role": "user", "content": "ok"}])
            return {"ok": True, "model": model, "ms": int((time.monotonic() - t0) * 1000)}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"[:200],
                    "ms": int((time.monotonic() - t0) * 1000)}

    def _call_llm(self, b, ctx, visible, p, tier) -> tuple[dict, str, int]:
        client, models = self._ensure_llm()
        model = models.get(tier) or models["small"]
        tool = NC.DECISION_TOOL if NC else None
        if tool is None:
            raise LLMUnavailable("decision tool schema unavailable")

        def call():
            return client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": build_prompt(b, ctx, visible, p)}],
                tools=[tool],
                tool_choice={"type": "function", "function": {"name": "decide"}},
                temperature=0.2,
            )

        fut = self._pool.submit(call)
        try:
            resp = fut.result(timeout=self.timeout_s)
        except FutureTimeout:
            raise TimeoutError(f"LLM call exceeded {self.timeout_s:.1f} s")
        raw, _path = NC.extract_decision(resp.choices[0].message)
        tokens = getattr(getattr(resp, "usage", None), "total_tokens", 0) or 0
        return _validate(raw, ctx, visible), model, int(tokens)

    # -- public API ---------------------------------------------------------
    def decide(self, b, ctx: PlanContext, visible_in_front: bool = False) -> dict:
        ctx.now = max(ctx.now, b.t)
        rule = rule_decide(b, ctx, visible_in_front)
        routine, why_routine = is_routine(b, ctx, visible_in_front, self.margin)

        want_llm = (self.mode == "llm" and not visible_in_front and not ctx.delivered) or \
                   (self.mode == "auto" and not routine)
        row = {"t": round(ctx.now, 2), "mode": self.mode, "routine_reason": why_routine,
               "llm_attempted": False, "llm_ok": False, "model": "", "tokens": 0,
               "fallback_reason": "", "agree_with_rule": ""}

        if not want_llm:
            row.update(engine="rule", action=rule["action"], target=rule["target"],
                       latency_ms=rule["latency_ms"])
            self.log.append(row)
            return rule

        row["llm_attempted"] = True
        t0 = time.perf_counter()
        try:
            p = effective_probs(b, ctx, visible_in_front)
            hard = bool(ctx.ruled_out and ctx.sensor_events) or (ctx.goal_text and ctx.obj is None)
            clean, model, tokens = self._call_llm(b, ctx, visible_in_front, p, "big" if hard else "small")
            latency = (time.perf_counter() - t0) * 1000
            agree = (clean["action"], clean["target"]) == (rule["action"], rule["target"])
            dec = _mk("llm", clean["action"], clean["target"], clean["command"], clean["why"],
                      latency, model=model, agree_with_rule=agree)
            row.update(llm_ok=True, model=model, tokens=tokens, agree_with_rule=agree,
                       engine="llm", action=dec["action"], target=dec["target"], latency_ms=dec["latency_ms"])
            self.log.append(row)
            return dec
        except Exception as e:      # timeout, network, bad output: all end the same way
            latency = (time.perf_counter() - t0) * 1000
            reason = f"{type(e).__name__}: {e}"[:200]
            rule["offline"] = True
            rule["fallback_reason"] = reason
            rule["latency_ms"] = int(latency)
            row.update(fallback_reason=reason, engine="rule", action=rule["action"],
                       target=rule["target"], latency_ms=int(latency))
            self.log.append(row)
            return rule

    def stats(self) -> dict:
        tried = [r for r in self.log if r["llm_attempted"]]
        ok = [r for r in tried if r["llm_ok"]]
        agree = [r for r in ok if r["agree_with_rule"] is True]
        return {
            "decisions": len(self.log),
            "llm_calls": len(tried),
            "llm_ok": len(ok),
            "fallbacks": len(tried) - len(ok),
            "agreement_rate": (len(agree) / len(ok)) if ok else None,
            "mean_llm_latency_ms": (sum(r["latency_ms"] for r in ok) / len(ok)) if ok else None,
            "tokens": sum(r["tokens"] for r in ok),
        }

    def write_log_csv(self, path: str) -> None:
        if not self.log:
            return
        with open(path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(self.log[0].keys()))
            w.writeheader()
            w.writerows(self.log)


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def _demo(mode: str, timeout: float = TIMEOUT_S) -> None:
    planner = Planner(mode=mode, timeout_s=timeout)
    print(f"mode={mode}  timeout={timeout}s\n")
    if mode != "rule":
        print("warm-up:", planner.warm_up(), "\n")

    cases = []
    b = RB.Belief("bottle_blue", "L", 0.75, 25.0)
    cases.append(("plan example: hidden 25 s, no sensor", b, PlanContext(now=25.0, last_seen_t=0.0), False))
    b = RB.Belief("bottle_blue", "L", 0.75 * RB.DISTURB, 25.0)
    c = PlanContext(now=25.0, last_seen_t=0.0, sensor_events=[(13.0, "L")])
    cases.append(("left sensor fired 12 s ago", b, c, False))
    b = RB.Belief("bottle_blue", "L", 0.75 * RB.DISTURB, 33.0)
    c = PlanContext(now=33.0, last_seen_t=0.0, sensor_events=[(13.0, "L")], ruled_out={"R"})
    cases.append(("right screen was empty", b, c, False))
    b = RB.Belief("bottle_blue", "R", 1.0, 40.0)
    cases.append(("object now visible", b, PlanContext(now=40.0), True))

    for title, b, ctx, vis in cases:
        d = planner.decide(b, ctx, vis)
        print(f"## {title}")
        print(json.dumps({k: d[k] for k in ("engine", "action", "target", "command", "why",
                                            "latency_ms", "offline", "fallback_reason") if k in d}, indent=2))
        print()
    print("stats:", json.dumps(planner.stats(), indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="rule", choices=["rule", "auto", "llm"])
    ap.add_argument("--timeout", type=float, default=TIMEOUT_S, help="LLM timeout in seconds (plan: 5)")
    a = ap.parse_args()
    _demo(a.mode, a.timeout)
