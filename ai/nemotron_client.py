"""
Second Look -- Nemotron client via Nebius Token Factory (role B)

Tests three things your plan (Part 6.3) specifically calls out as risks
before you build the real planner on top of this:
  1. Can we list models without hard-coding IDs?
  2. Does native OpenAI-style tool calling actually work on this model?
     (Your doc flags a May-2026 Token Factory issue where Nemotron
     returned answers in a non-standard field with empty `content`,
     and tool calls failed through the OpenAI-compatible route.)
  3. If tool calling is broken, does the "ask for plain JSON and parse
     it" fallback from the doc actually work instead?

Usage:
    pip install openai
    export NEBIUS_API_KEY="<your Token Factory key>"
    python nemotron_client.py --list              # just list models
    python nemotron_client.py                     # run both tests
    python nemotron_client.py --test-tools         # tool calling only

        python nemotron_client.py --test-fallback       # JSON fallback only
    python nemotron_client.py --model <id>         # override auto-picked model
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dotenv import load_dotenv

try:
    from openai import OpenAI
except ImportError:
    sys.exit("pip install openai  (Token Factory speaks the OpenAI-compatible API)")
    
load_dotenv()
BASE_URL = os.environ.get("TOKEN_FACTORY_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
API_KEY_ENV = "NEBIUS_API_KEY"

# Matches the `decision` message shape from Part 2.2 / 6.3 of the team plan.
DECISION_TOOL = {
    "type": "function",
    "function": {
        "name": "decide",
        "description": "Choose the robot's next action: look at a hiding place, pick up the target, ask the user, or finish.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["look", "pick", "ask", "finish"]},
                "target": {"type": "string", "description": "object name, or hiding place id like 'L' or 'R'"},
                "command": {"type": "string", "description": "short natural-language command for the VLA, e.g. 'pick up the blue bottle and place it in the tray'"},
                "why": {"type": "string", "description": "one sentence explaining the choice, for the dashboard"},
            },
            "required": ["action", "target", "command", "why"],
        },
    },
}

DECISION_JSON_INSTRUCTIONS = (
    "Respond with ONLY a single JSON object, no prose, no markdown fences, matching this shape: "
    '{"action": "look"|"pick"|"ask"|"finish", "target": "<id>", "command": "<short command>", "why": "<one sentence>"}'
)


def get_client() -> OpenAI:
    key = os.environ.get(API_KEY_ENV)
    if not key:
        sys.exit(f"Set {API_KEY_ENV} first: export {API_KEY_ENV}=<your Token Factory key>")
    return OpenAI(base_url=BASE_URL, api_key=key)


def list_models(client: OpenAI) -> list:
    models = client.models.list()
    ids = [m.id for m in models.data]
    for mid in ids:
        print(" -", mid)
    return ids


def pick_default_model(model_ids: list, prefer: str = "nemotron") -> str:
    candidates = [m for m in model_ids if prefer in m.lower()]
    if not candidates:
        sys.exit(f"No model containing {prefer!r} found. Pass --model explicitly from the --list output.")
    # Prefer a small/nano/mini variant for routine calls, per the plan's
    # tiering note in Part 6.3 (small model for routine, big one only for
    # hard cases).
    small = [m for m in candidates if any(s in m.lower() for s in ("nano", "mini", "small"))]
    return small[0] if small else candidates[0]


def _extract_json_obj(text: str) -> dict:
    """Pull the first {...} JSON object out of arbitrary text -- handles
    stray markdown fences or reasoning text wrapped around the JSON."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON object found in: {text!r}")
    return json.loads(match.group(0))


def extract_decision(message) -> tuple[dict, str]:
    """Given a chat completion's message, return (decision_dict, path).

    path is one of: 'tool_call', 'json_in_text', 'json_in_<field>'.

    Handles the known failure mode from the plan's Part 6.3: some
    responses come back with empty `content` and the actual answer
    sitting in a non-standard field (commonly surfaced by OpenAI-
    compatible SDKs as `reasoning_content` or `reasoning`)."""

    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        args_str = tool_calls[0].function.arguments
        return json.loads(args_str), "tool_call"

    content = (getattr(message, "content", None) or "").strip()
    if content:
        return _extract_json_obj(content), "json_in_text"

    # content empty -- check known alternate fields before giving up
    for alt_field in ("reasoning_content", "reasoning"):
        alt = getattr(message, alt_field, None)
        if alt:
            try:
                return _extract_json_obj(alt), f"json_in_{alt_field}"
            except ValueError:
                pass

    raise ValueError("message had no tool_calls, no content, and nothing usable in known fallback fields")


def test_tool_calling(client: OpenAI, model: str) -> bool:
    print(f"\n--- testing native tool calling on {model} ---")
    situation = (
        "The blue bottle was last seen behind the LEFT screen 25 seconds ago. "
        "Half-life is 60s, so confidence it's still there is about 0.75. "
        "No sensor evidence. Decide what to do next."
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": situation}],
            tools=[DECISION_TOOL],
            tool_choice={"type": "function", "function": {"name": "decide"}},
        )
        decision, path = extract_decision(resp.choices[0].message)
        print("decision:", decision)
        print("path:", path)
        if path == "tool_call":
            print("RESULT: native tool calling WORKS on this model.")
            return True
        print(f"RESULT: tool calling degraded (got an answer via {path}, not a real tool_call).")
        return False
    except Exception as e:
        print(f"RESULT: tool calling call failed outright: {e}")
        return False


def test_json_fallback(client: OpenAI, model: str) -> bool:
    print(f"\n--- testing plain-JSON fallback on {model} ---")
    situation = (
        "The blue bottle was last seen behind the LEFT screen 25 seconds ago. "
        "Half-life is 60s, so confidence it's still there is about 0.75. "
        "A touch sensor under the left screen just fired, cutting confidence by x0.35. "
        f"Decide what to do next. {DECISION_JSON_INSTRUCTIONS}"
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": situation}],
        )
        decision, path = extract_decision(resp.choices[0].message)
        print("decision:", decision)
        print("path:", path)
        print("RESULT: JSON-in-text fallback WORKS on this model.")
        return True
    except Exception as e:
        print(f"RESULT: JSON-in-text fallback also failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Nemotron / Token Factory smoke tests")
    parser.add_argument("--list", action="store_true", help="list available models and exit")
    parser.add_argument("--model", default=None, help="model id to use (default: auto-pick a nemotron nano/mini variant)")
    parser.add_argument("--test-tools", action="store_true", help="test native tool calling only")
    parser.add_argument("--test-fallback", action="store_true", help="test plain-JSON fallback only")
    args = parser.parse_args()

    client = get_client()
    print(f"connected to {BASE_URL}\navailable models:")
    model_ids = list_models(client)

    if args.list:
        return

    model = args.model or pick_default_model(model_ids)
    print(f"\nusing model: {model}")

    run_tools = args.test_tools or not (args.test_tools or args.test_fallback)
    run_fallback = args.test_fallback or not (args.test_tools or args.test_fallback)

    tools_ok = test_tool_calling(client, model) if run_tools else None
    fallback_ok = test_json_fallback(client, model) if run_fallback else None

    print("\n=== summary ===")
    if tools_ok is not None:
        print("native tool calling:", "OK -- use tools= in the real planner" if tools_ok else "BROKEN -- use the JSON-in-text fallback")
    if fallback_ok is not None:
        print("JSON-in-text fallback:", "OK -- safe as your planner's real path" if fallback_ok else "ALSO BROKEN -- fall back further to the rule planner for this model")


if __name__ == "__main__":
    main()
