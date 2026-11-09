"""Hallway Test: watch five simulated people try your site, each with real, code-enforced limits.

Registers the ``hallway_test`` tool and a ``/hallway`` command. Every persona decision is one call to
the user's own model through ``ctx.llm`` (no extra API keys). Results are written under
``<hermes home>/plugin-data/hallway-test/runs/<id>/`` and shown by the Desktop page.
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from .ht import demo
from .ht.personas import PERSONAS, pick

log = logging.getLogger(__name__)
PLUGIN = "hallway-test"

SCHEMA = {
    "name": "hallway_test",
    "description": (
        "Usability-test a web page with simulated people who have real, code-enforced limits: a first-time visitor, "
        "a 72-year-old with low vision (can't read small or faint text), a blind screen-reader user (keyboard only, "
        "hears only the accessibility tree), a red-green colour-blind user, and a user with a hand tremor (taps land "
        "off target). Each one tries the task in their own real browser, one decision at a time; you get who finished, "
        "who gave up and why in their own words, taps that did nothing, prioritised findings with fixes, a full HTML "
        "report with step-by-step replays, and a summary card image. Use url='demo' (and compare_url='demo:fixed') to "
        "try the bundled coffee-shop app. Takes 1-5 minutes. Works on http(s) pages the machine can reach, including "
        "localhost dev servers."),
    "parameters": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Page to test: http(s)://… or file:///…, or 'demo' for the bundled Kapé app."},
            "task": {"type": "string", "description": "What the people should try to do, in plain words, e.g. "
                     "'Sign up for the newsletter with the email sam@example.com'. Optional for the demo."},
            "success_text": {"type": "string", "description": "Text that appears on the page only when the task is "
                             "done (e.g. 'Thanks for subscribing'). Strongly recommended: it lets the test verify "
                             "success instead of trusting the persona."},
            "compare_url": {"type": "string", "description": "Optional second version (e.g. your fix on another port, "
                            "or 'demo:fixed') to run the same people on for a before/after comparison."},
            "personas": {"type": "array", "items": {"type": "string", "enum": list(PERSONAS)},
                         "description": "Subset of people to run. Default: all five."},
            "facts": {"type": "string", "description": "Details the people know, such as test login credentials."},
            "device": {"type": "string", "enum": ["mobile", "desktop"], "description": "Viewport. Default mobile."},
            "max_steps": {"type": "integer", "minimum": 4, "maximum": 40,
                          "description": "Most actions per person (keyboard users get 1.8x). Default 16."},
            "title": {"type": "string", "description": "Short name for the report, e.g. 'Checkout v2'."},
        },
        "required": ["url"],
        "additionalProperties": False,
    },
}


def _data_dir() -> Path:
    from plugins.plugin_storage import plugin_data_dir
    return plugin_data_dir(PLUGIN)


def _make_complete(ctx, max_tokens: int, timeout: float = 90):
    def complete(messages: list[dict]) -> str:
        last = None
        for _ in range(2):  # one retry for a transient provider error
            try:
                res = ctx.llm.complete(messages, temperature=0.4,
                                       max_tokens=max_tokens, timeout=timeout, purpose="hallway-test persona step")
                return res.text
            except Exception as exc:  # noqa: BLE001 - surfaced after the retry
                last = exc
        raise last
    return complete


def run_tool(ctx, args: dict) -> dict:
    from .ht.run import run_test

    url, is_demo = demo.resolve(args.get("url", ""))
    if not url:
        raise ValueError("url is required")
    compare = demo.resolve(args.get("compare_url", ""))[0] if args.get("compare_url") else ""
    task = (args.get("task") or "").strip() or (demo.DEMO_TASK if is_demo else "")
    if not task:
        raise ValueError("task is required: say what the people should try to do")
    success = (args.get("success_text") or "").strip() or (demo.DEMO_SUCCESS if is_demo else "")
    viewport = (1280, 800) if args.get("device") == "desktop" else (420, 860)
    max_steps = int(args.get("max_steps") or ctx.get_config("max_steps", 16))
    title = args.get("title") or ("Kapé coffee app (demo)" if is_demo else "")
    try:
        return _run(ctx, args, url, is_demo, compare, task, success, viewport, max_steps, title)
    except RuntimeError as exc:
        if str(exc).startswith("No one could start"):
            raise RuntimeError(f"{exc} {MODEL_HINT}") from None
        raise


def _run(ctx, args, url, is_demo, compare, task, success, viewport, max_steps, title) -> dict:
    from .ht.run import run_test
    return run_test(url, task, _make_complete(ctx, 700), pick(args.get("personas")), _data_dir(),
                    success_text=success, compare_url=compare, facts=args.get("facts", ""), max_steps=max_steps,
                    parallel=int(ctx.get_config("parallel", 10)), viewport=viewport, title=title,
                    findings_complete=_make_complete(ctx, 8000, timeout=180),
                    time_budget=float(ctx.get_config("time_budget_seconds", 330)))


MODEL_HINT = ("Hallway Test uses Hermes's default model (the one `hermes model` saves), not the model picked in a "
              "single chat. Check that model works, then run the test again.")


def check_model_errors(res: dict) -> None:
    """Every person failing on the model call is a setup problem, not a usability result: say so plainly."""
    errs = [r for r in res["results"] if r["status"] == "error"]
    if res["results"] and len(errs) == len(res["results"]):
        raise RuntimeError(f"No one could start: {errs[0]['reason'][:300]} {MODEL_HINT}")


def tool_summary(res: dict) -> dict:
    check_model_errors(res)
    lines = []
    for v in res["variants"]:
        sc = res["score"][v]
        lines.append(f"{v}: {sc['passed']}/{sc['total']} finished")
    people = [{"variant": r["variant"], "persona": PERSONAS[r["persona"]].name, "status": r["status"],
               "summary": r.get("summary", ""), "in_their_words": r.get("quote", "")} for r in res["results"]]
    return {
        "ok": True, "run_id": res["id"], "score": "; ".join(lines), "people": people,
        "findings": res["findings"], "report_html": res["report"], "summary_card": res["card"],
        "show_user": (f"Share the summary card by writing this line on its own: MEDIA:{res['card']} . "
                      "The full report with replays is in the Hallway page of Hermes Desktop and at report_html."),
    }


def register(ctx) -> None:
    def handler(args: dict, **_kw) -> str:
        try:
            return json.dumps(tool_summary(run_tool(ctx, args or {})), ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001 - returned to the agent as a tool error
            log.exception("hallway_test failed")
            return json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    ctx.register_tool(name="hallway_test", toolset="hallway_test", schema=SCHEMA, handler=handler,
                      description="Usability-test a page with five simulated people", emoji="🚶")

    def command(raw: str = "", **_kw) -> str:
        arg = (raw or "").strip()
        if arg in ("", "help"):
            return ("Hallway Test: ask me to test a page, e.g. “hallway test http://localhost:3000 — sign up with "
                    "sam@example.com; success text: Welcome”.\n/hallway demo runs the bundled coffee app before and "
                    "after fixes. /hallway runs lists recent runs.")
        if arg == "runs":
            runs = sorted((_data_dir() / "runs").glob("*/result.json"), reverse=True)[:8]
            if not runs:
                return "No runs yet. Try /hallway demo."
            out = []
            for p in runs:
                r = json.loads(p.read_text(encoding="utf-8"))
                sc = " → ".join(f"{r['score'][v]['passed']}/{r['score'][v]['total']}" for v in r["variants"])
                out.append(f"{r['id']}  {sc}  {r.get('title') or r['url']}  ({p.parent / 'report.html'})")
            return "\n".join(out)
        if arg == "demo":
            # Desktop gives a command ~30 s to answer; a run takes minutes, so it runs in the background.
            def work():
                try:
                    check_model_errors(run_tool(ctx, {"url": "demo", "compare_url": "demo:fixed"}))
                except Exception:  # noqa: BLE001 - the run's state.json records the failure
                    log.exception("hallway demo failed")
            threading.Thread(target=work, name="hallway-demo-run", daemon=True).start()
            return ("Hallway Test started: five people are trying the demo coffee app, before and after fixes. "
                    "Watch it live on the Hallway Test page in the sidebar (about 1-3 minutes), or type "
                    "/hallway runs to see results here.")
        return "Unknown option. Use /hallway, /hallway demo or /hallway runs."

    ctx.register_command("hallway", command, description="Hallway Test: run the demo or list recent runs",
                         args_hint="[demo|runs]")
