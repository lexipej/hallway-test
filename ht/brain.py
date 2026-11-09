"""The persona's brain: one model call per screen, one action per call.

``Brain`` takes any ``complete(messages) -> str`` callable, so tests can drive it with a script
and the plugin drives it with ``ctx.llm`` (the user's own model; no extra keys).
"""
from __future__ import annotations

import json
import re
from typing import Callable

from .browser import KEY_ACTIONS, MOUSE_ACTIONS

SYSTEM = """You are role-playing a real person trying to use a website, for a usability test.

WHO YOU ARE: {name}. {blurb} {temperament}
YOUR GOAL: {task}
{facts}
RULES
- You only know what is described under the screen description. Never assume a control exists that isn't listed,
  and never use technical knowledge a normal person wouldn't have (no URLs, no developer tools).
- If you can't read, find or reach something, say so honestly. Real people give up when they're stuck.
- Do one action per turn. When the goal is achieved, answer with the action "done".
- If you have tried everything reasonable, answer "give_up <short reason in your own words>".

ACTIONS YOU CAN TAKE: {actions}
{ref_hint}
Reply with ONLY a JSON object on one line, action first:
{{"action": "<one action>", "thought": "<one short first-person sentence, at most 20 words, in character>"}}"""

REF_HINT_MOUSE = "Refer to things on screen by their [number], e.g. click 4 or type 7 Maria."
REF_HINT_KEYS = ("You cannot click. Tab moves focus forward through things the screen reader lets you reach; "
                 "Enter or Space activates the focused control; type_focused types into the focused field.")


class Brain:
    def __init__(self, persona, task: str, complete: Callable[[list[dict]], str], facts: str = ""):
        self.p = persona
        self.complete = complete
        self.history: list[dict] = []
        self.system = SYSTEM.format(
            name=persona.name, blurb=persona.blurb, temperament=persona.temperament, task=task,
            facts=f"THINGS YOU KNOW: {facts}\n" if facts else "",
            actions=MOUSE_ACTIONS if persona.mouse else KEY_ACTIONS,
            ref_hint=REF_HINT_MOUSE if persona.mouse else REF_HINT_KEYS)

    def messages(self, screen: str, step: int, max_steps: int) -> list[dict]:
        past = "\n".join(
            f"{i + 1}. {h['action']}" + (f"  — you thought: {h['thought']}" if h.get("thought") else "")
            + (f"  [{h['outcome']}]" if h.get("outcome") else "")
            for i, h in enumerate(self.history[-12:]))
        user = (f"Step {step + 1} of at most {max_steps}.\n"
                + (f"WHAT YOU DID SO FAR:\n{past}\n\n" if past else "")
                + f"{screen}\n\nWhat do you do next? JSON only.")
        return [{"role": "system", "content": self.system}, {"role": "user", "content": user}]

    def decide(self, screen: str, step: int, max_steps: int) -> dict:
        raw = self.complete(self.messages(screen, step, max_steps))
        return parse_reply(raw)

    def record(self, action: str, thought: str, outcome: str) -> None:
        self.history.append({"action": action, "thought": thought, "outcome": outcome})


def parse_reply(raw: str) -> dict:
    """Pull {thought, action} out of a model reply, tolerating fences and chatter."""
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    for m in re.finditer(r"\{.*?\}", text, re.S):
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("action"):
            return {"thought": str(obj.get("thought", "")).strip()[:240], "action": str(obj["action"]).strip()}
    # A reply cut off mid-thought still names its action when the action comes first.
    m = re.search(r'"action"\s*:\s*"((?:[^"\\]|\\.)+)"', text)
    if m:
        t = re.search(r'"thought"\s*:\s*"((?:[^"\\]|\\.)*)', text)
        return {"thought": (t.group(1) if t else "").strip()[:240], "action": m.group(1).strip()}
    m = re.search(r"\b(click \d+|type \d+ .+|press \S+|type_focused .+|scroll (?:up|down)|done|give_up.*)", text)
    if m:
        return {"thought": "", "action": m.group(1).strip()}
    return {"thought": "", "action": "", "error": f"could not read a JSON action from: {text[:120]!r}"}


FINDINGS_PROMPT = """You are a senior UX researcher. Several simulated people with different abilities tried the same
task on a website. Their perception and abilities were enforced by software, so their failures are real barriers.

TASK: {task}

WHAT HAPPENED (per person: outcome, steps, and their own words):
{outcomes}

AUTOMATED CHECKS FOUND ON SCREENS THEY SAW:
{audit}

Write the 3 to 5 most important findings, most severe first. Each finding must name who it blocked or slowed,
point to concrete evidence above, and give one specific fix a developer can apply.
Severity must match what happened in THIS run: "blocker" only if it actually stopped someone from finishing;
"major" if it clearly slowed or confused someone; an automated check that no one ran into is at most "minor".
Never call something a blocker for a person who finished. Prefer fewer, well-evidenced findings over a long list.
Reply with ONLY JSON: {{"findings": [{{"title": "...", "severity": "blocker|major|minor", "who": ["persona name", ...],
"evidence": "...", "fix": "..."}}]}}"""


def parse_findings(raw: str) -> list[dict]:
    text = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(), flags=re.M)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        return []
    try:
        obj = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []
    out = []
    for f in obj.get("findings", [])[:6]:
        if isinstance(f, dict) and f.get("title"):
            who = f.get("who") or []
            out.append({"title": str(f["title"])[:120], "severity": str(f.get("severity", "major")).lower(),
                        "who": [str(w) for w in (who if isinstance(who, list) else [who])][:5],
                        "evidence": str(f.get("evidence", ""))[:300], "fix": str(f.get("fix", ""))[:300]})
    return out
