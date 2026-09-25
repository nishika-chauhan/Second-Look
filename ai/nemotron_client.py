"""TEMPLATE - NOT TESTED (needs a Nebius Token Factory API key). Role B owns this file.

Setup:   pip install openai
         export NEBIUS_API_KEY="..."        (Windows PowerShell:  $Env:NEBIUS_API_KEY="...")
Never commit the key. Keep it in your shell or in a .env file that is listed in .gitignore.

Docs:    https://docs.tokenfactory.nebius.com/quickstart
         https://docs.tokenfactory.nebius.com/ai-models-inference/function-calling

Things to check on DAY 1 (they change over time):
  1. Which Nemotron model IDs exist right now?  -> run:  python ai/nemotron_client.py --list
  2. Some Nemotron models are "reasoning" models: the answer can arrive in `reasoning_content` and
     `content` can be empty if max_tokens is too small. This client asks for JSON in plain text and
     handles both cases. Test tool/function calling separately before relying on it.
  3. Never hard-code a model ID in many places. Put it in one variable (NEBIUS_MODEL_ID).
"""
import argparse
import json
import os
import re
import time

from openai import OpenAI

client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",
    api_key=os.environ.get("NEBIUS_API_KEY", ""),
)

SYSTEM = """You are the decision module of a tabletop robot.
You get a goal and a table of beliefs about objects: where each was last seen, how confident
the robot still is (0..1), and whether it is hidden. Choose ONE action:
  "act"    - confidence is high enough: go and pick the target now
  "relook" - confidence is low or the hidden area was disturbed: look at that spot again first
  "search" - the object was not where expected: look in another place
Reply with ONE JSON object and nothing else:
{"action": "act|relook|search", "target": "<object name>", "command": "<short imperative command>",
 "why": "<one sentence a non-expert can read>"}"""


def list_models():
    return [m.id for m in client.models.list().data]


def decide(beliefs, goal, model, retries=2, timeout_s=30):
    """Ask the model for a decision. Returns a dict, or None (caller must fall back to the rule engine)."""
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": json.dumps({"goal": goal, "beliefs": beliefs})},
    ]
    for _ in range(retries + 1):
        try:
            t0 = time.time()
            r = client.chat.completions.create(
                model=model, messages=msgs, max_tokens=1500, temperature=0.2, timeout=timeout_s)
            msg = r.choices[0].message
            text = (msg.content or "").strip()
            if not text:                                    # reasoning models may leave content empty
                text = (getattr(msg, "reasoning_content", None) or "").strip()
            m = re.search(r"\{.*\}", text, re.S)             # take the first {...} block
            if m:
                out = json.loads(m.group(0))
                out["latency_ms"] = int((time.time() - t0) * 1000)
                return out
        except Exception as e:                               # network error, rate limit, bad JSON...
            print("LLM call failed:", repr(e))
            time.sleep(1.0)
    return None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="print available model IDs")
    ap.add_argument("--model", default=os.environ.get("NEBIUS_MODEL_ID", ""))
    args = ap.parse_args()
    if args.list:
        print("\n".join(list_models()))
    else:
        demo = {"bottle_blue": {"xy": [0.0, 0.12], "conf": 0.78, "hidden_by": "screen",
                                "last_seen_s_ago": 11, "area_disturbed": True}}
        print(decide(demo, "bring me the blue bottle", args.model))
