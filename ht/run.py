"""Run a hallway test: every persona tries the task in its own real browser, in parallel."""
from __future__ import annotations

import json
import os
import random
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

from . import browser as B
from .brain import FINDINGS_PROMPT, Brain, parse_findings
from .netguard import Guard, normalise, settle
from .personas import Persona

Complete = Callable[[list[dict]], str]

HESITANT = re.compile(r"\b(guess|not sure|unsure|confus|can't|cannot|where|hmm|why|nothing happen|no idea|stuck|"
                      r"doesn't say|don't know|hope)\b", re.I)

WHO = {"not_keyboard": ["keyboard"], "no_name": ["keyboard", "first_timer"], "no_label": ["keyboard"],
       "no_alt": ["keyboard"], "small_text": ["low_vision"], "low_contrast": ["low_vision"],
       "small_target": ["shaky"], "colour_only": ["colourblind"]}

FIX_HINTS = {
    "not_keyboard": ("Controls that only work with a mouse", "blocker",
                     "Use a real <button> (or add tabindex=0, role=button and Enter/Space handlers)."),
    "low_contrast": ("Text with too little contrast", "major", "Raise text contrast to at least 4.5:1 (3:1 for large text)."),
    "small_text": ("Text that is too small", "major", "Use at least 14px for body text and hints."),
    "no_name": ("Icon-only controls with no name", "major", "Add visible text or an aria-label to every icon control."),
    "no_label": ("Form fields without labels", "major", "Give every field a <label for=…> or aria-label."),
    "no_alt": ("Images without alt text", "minor", "Add alt text that says what the image means."),
    "small_target": ("Tap targets smaller than 24px", "minor", "Make tap targets at least 24×24px (44×44px is better)."),
    "colour_only": ("Errors shown only by colour", "major",
                    "Explain errors in text next to the field, with role=alert, not just a red border."),
}


class RunState:
    """Live state on disk so the Desktop page can follow a run while it happens."""

    def __init__(self, run_dir: Path, meta: dict):
        self.dir = run_dir
        self.lock = threading.Lock()
        self.data = {**meta, "status": "running", "personas": {}}
        self.flush()

    def update(self, key: str, **fields) -> None:
        with self.lock:
            self.data["personas"].setdefault(key, {}).update(fields)
            self._write()

    def set(self, **fields) -> None:
        with self.lock:
            self.data.update(fields)
            self._write()

    def flush(self) -> None:
        with self.lock:
            self._write()

    def _write(self) -> None:
        tmp = self.dir / f"state.{threading.get_ident()}.tmp"
        tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        for _ in range(20):  # Windows: a reader holding the file makes replace fail briefly
            try:
                os.replace(tmp, self.dir / "state.json")
                return
            except PermissionError:
                time.sleep(0.05)


_install_lock = threading.Lock()


# Personas don't need smooth animation: these keep many headless browsers from swamping the machine.
LIGHT_ARGS = ["--mute-audio", "--disable-extensions", "--disable-background-networking", "--no-first-run",
              "--js-flags=--max-old-space-size=512", "--renderer-process-limit=2"]

# Redraw animated pages (3D, canvas, motion) ~5 times a second instead of 60. Screenshots still show the
# current frame; the CPU cost of WebGL drawn in software drops by an order of magnitude.
SLOW_FRAMES_JS = """(() => {
  const ids = new Map(); let n = 0;
  window.requestAnimationFrame = cb => { const id = ++n; ids.set(id, setTimeout(() => { ids.delete(id); cb(performance.now()); }, 200)); return id; };
  window.cancelAnimationFrame = id => { clearTimeout(ids.get(id)); ids.delete(id); };
})();"""

MIN_FREE_MB = 1200


def free_memory_mb() -> float:
    """Available physical memory in MB (Windows, Linux, macOS best effort); a large number if unknown."""
    try:
        import sys
        if sys.platform == "win32":
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            ms = MS(); ms.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
            return ms.ullAvailPhys / 2**20
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / 1024
    except Exception:  # noqa: BLE001 - unknown platform: don't block
        pass
    return 1e9


def wait_for_memory(deadline: float, need_mb: float = MIN_FREE_MB) -> None:
    """Don't start another browser on a machine that is short of memory: wait a little, then refuse."""
    give_up = time.time() + 45
    while free_memory_mb() < need_mb:
        if time.time() > give_up or (deadline and time.time() > deadline):
            raise RuntimeError(f"skipped: less than {need_mb / 1024:.1f} GB of free memory, so this person's browser "
                               "was not started (close some apps or lower the parallel setting)")
        time.sleep(3)


def launch(pw):
    """Bundled Chromium, else the Edge/Chrome already on the machine."""
    errors = []
    for kw in ({}, {"channel": "msedge"}, {"channel": "chrome"}):
        try:
            return pw.chromium.launch(headless=True, args=LIGHT_ARGS, **kw)
        except Exception as exc:  # try the next browser
            errors.append(f"{kw.get('channel', 'chromium')}: {str(exc).splitlines()[0]}")
    raise RuntimeError("No browser available. Run `python -m playwright install chromium` in the Hermes "
                       "environment, or install Microsoft Edge or Chrome. Details: " + " | ".join(errors))


def _site(host: str) -> str:
    host = (host or "").lower().removeprefix("www.")
    parts = host.split(".")
    if host.replace(".", "").isdigit() or len(parts) <= 2:
        return host
    # keep three labels for short second-level domains (gov.uk, com.ph, co.jp)
    return ".".join(parts[-3:] if len(parts[-2]) <= 3 and len(parts[-1]) == 2 else parts[-2:])


def off_site(start: str, now: str) -> str:
    """The new host if the page left the site under test, else ''."""
    a, b = urlparse(start), urlparse(now)
    if b.scheme not in ("http", "https") or not b.hostname:
        return ""
    x, y = (h.lower().removeprefix("www.") for h in (a.hostname or "", b.hostname))
    same = x == y or y.endswith("." + x) or x.endswith("." + y) or _site(x) == _site(y)
    return "" if same else b.hostname


def run_persona(url: str, p: Persona, variant: str, task: str, complete: Complete, run_dir: Path,
                state: RunState, success_text: str = "", facts: str = "", max_steps: int = 20,
                viewport=(420, 860), seed: int = 7, deadline: float = 0,
                guard: Optional[Guard] = None) -> dict:
    from playwright.sync_api import sync_playwright

    guard = guard or Guard()
    url = guard.check(normalise(url))

    key = f"{variant}:{p.id}"
    shots = run_dir / "shots"
    shots.mkdir(exist_ok=True)
    rng = random.Random(f"{seed}:{p.id}")
    brain = Brain(p, task, complete, facts)
    steps: list[dict] = []
    audit: dict[str, list] = {}
    status, reason, start_fp = "out_of_steps", "", None
    want = success_text.strip().lower()
    state.update(key, persona=p.id, variant=variant, status="starting", step=0)
    t0 = time.time()

    def seen_success(raw: dict) -> bool:
        return bool(want) and (want in raw.get("text", "").lower() or want in raw.get("title", "").lower())

    wait_for_memory(deadline)
    with sync_playwright() as pw:
        br = launch(pw)
        try:
            context = br.new_context(viewport={"width": viewport[0], "height": viewport[1]},
                                     reduced_motion="reduce", service_workers="block")
            guard.install(context)   # every request, redirect hop and in-run navigation is checked
            page = context.new_page()
            page.set_default_timeout(15000)
            page.add_init_script(SLOW_FRAMES_JS)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception:   # one more try after a pause: several browsers opening one site can be throttled
                page.wait_for_timeout(3000 + rng.randrange(4000))
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            settle(page)
            try:
                page.wait_for_load_state("networkidle", timeout=4000)
            except Exception:
                pass
            if p.css_filter:
                B.install_filters(page)
            invalid = 0
            if not p.mouse:
                max_steps = int(max_steps * 1.8)  # tabbing through a page takes more moves than clicking
            for i in range(max_steps):
                if deadline and time.time() > deadline:
                    status, reason = "out_of_steps", "time ran out"
                    break
                settle(page)
                obs = B.observe(page, p)
                fp = B.fingerprint(obs["raw"])
                lay = B.layout(obs["raw"])
                start_fp = start_fp or lay
                audit.setdefault(fp, B.audit(obs["raw"]))
                shot = f"{variant}_{p.id}_{i:02d}.jpg"
                B.screenshot(page, p, shots / shot)
                if seen_success(obs["raw"]):
                    status = "success"
                    steps.append({"i": i, "action": "(task complete)", "thought": "", "shot": shot, "screen": fp})
                    break
                state.update(key, status="thinking", step=i + 1, shot=shot)
                try:
                    d = brain.decide(obs["text"], i, max_steps)
                    if not d.get("action"):  # an unreadable reply is usually a hiccup: ask once more, same screen
                        d = brain.decide(obs["text"], i, max_steps)
                except Exception as exc:
                    status, reason = "error", f"model call failed: {exc}"
                    break
                action, thought = d.get("action", ""), d.get("thought", "")
                rec = {"i": i, "action": action or "(invalid reply)", "thought": thought, "shot": shot, "screen": lay}
                steps.append(rec)
                state.update(key, status="acting", thought=thought, action=action)
                if not action:
                    invalid += 1
                    brain.record("(invalid reply)", "", "reply was not valid JSON; answer with JSON only")
                    if invalid >= 5:  # some models send empty replies in bursts
                        status, reason = "error", d.get("error", "model kept replying without an action")
                        break
                    continue
                refused = len(guard.blocked)
                try:
                    res = B.act(page, p, obs, action, rng)
                except B.ActionError as exc:
                    invalid += 1
                    rec["error"] = str(exc)
                    brain.record(action, thought, f"not possible: {exc}")
                    if invalid >= 4:
                        status, reason = "error", "kept choosing actions it could not take"
                        break
                    continue
                except Exception as exc:  # playwright hiccup (navigation, detached element)
                    rec["error"] = str(exc).splitlines()[0][:160]
                    brain.record(action, thought, "that didn't work")
                    continue
                invalid = 0
                rec.update({k: v for k, v in res.items() if k in ("kind", "click", "aimed", "key")})
                if res["kind"] == "done":
                    if want and not seen_success(B.probe(page)):
                        status, reason = "false_done", "said they had finished, but the task was not complete"
                    else:
                        status = "success"
                    break
                if res["kind"] == "give_up":
                    status, reason = "gave_up", res["reason"]
                    break
                try:
                    page.wait_for_timeout(250)
                    page.wait_for_load_state("domcontentloaded", timeout=5000)
                    settle(page)
                    after = B.probe(page)
                except Exception:
                    page.wait_for_timeout(800)
                    settle(page)
                    after = B.probe(page)
                # Stay on the site under test: a link to GitHub or a sponsor is not part of the task.
                left = off_site(url, page.url)
                if left:
                    rec["offsite"] = left
                    try:
                        page.go_back(wait_until="domcontentloaded", timeout=10000)
                    except Exception:
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    brain.record(action, thought, f"that opened a different website ({left}), so you came back; "
                                 "the task is on this site")
                    continue
                if len(guard.blocked) > refused:   # a link or redirect to an address the test may not open
                    rec["blocked"] = guard.blocked[-1]
                    if not (page.url or "").startswith("http"):
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    brain.record(action, thought, "that led to an address this test is not allowed to open, "
                                 "so nothing loaded; the task is on this site")
                    continue
                # Moving the typing cursor into a field is a visible change too (a tap on an empty field "worked").
                changed = B.fingerprint(after) != fp or after.get("focus") != obs["raw"].get("focus")
                rec["changed"] = changed
                outcome = "the screen changed" if changed else "nothing seemed to happen"
                brain.record(action, thought, outcome)
            final = f"{variant}_{p.id}_final.jpg"
            B.screenshot(page, p, shots / final)
        finally:
            br.close()

    dead = sum(1 for s in steps if s.get("kind") == "click" and s.get("changed") is False)
    thoughts = [s["thought"] for s in steps if s.get("thought")]
    reason = reason.strip(" <>\"'")
    if status == "gave_up" and reason.lower() in ("", "gave up", "give up", "i give up"):
        reason = thoughts[-1] if thoughts else "gave up"
    after_dead = [steps[k + 1]["thought"] for k in range(len(steps) - 1)
                  if steps[k].get("changed") is False and steps[k].get("kind") == "click" and steps[k + 1].get("thought")]
    quote = reason if status == "gave_up" else next((t for t in thoughts if HESITANT.search(t)),
                                                     after_dead[0] if after_dead else (thoughts[-1] if thoughts else ""))
    quote = quote.strip(" <>\"'")
    clicks = [s["click"] for s in steps if s.get("click") and s.get("screen") == start_fp]
    out = {"persona": p.id, "variant": variant, "status": status, "reason": reason, "steps": steps,
           "n_steps": len([s for s in steps if s["action"] != "(task complete)"]), "dead_clicks": dead,
           "quote": quote, "first_screen_clicks": clicks, "first_shot": steps[0]["shot"] if steps else final,
           "final_shot": final, "seconds": round(time.time() - t0, 1), "audit": audit}
    state.update(key, status=status, reason=reason, quote=quote, n_steps=out["n_steps"], dead_clicks=dead, shot=final)
    return out


def summarise(o: dict) -> str:
    n = o["n_steps"]
    base = {"success": f"Finished in {n} steps", "gave_up": f"Gave up after {n} steps",
            "false_done": f"Thought they were done after {n} steps, but weren't",
            "out_of_steps": f"Still trying after {n} steps", "error": f"Run stopped: {o['reason']}"}[o["status"]]
    if o["dead_clicks"]:
        base += f"; {o['dead_clicks']} tap{'s' if o['dead_clicks'] != 1 else ''} did nothing"
    return base


def findings(task: str, results: list[dict], personas: dict, complete: Optional[Complete],
             issues_note: Optional[list] = None, summary_out: Optional[list] = None) -> tuple[list[dict], str]:
    """Findings (title, severity, who, what, evidence[], fix[]) and, via summary_out, 2-3 headline bullets."""
    summary_out = summary_out if summary_out is not None else []
    issues_note = issues_note if issues_note is not None else []
    issues: dict[tuple, dict] = {}
    for r in results:
        for screen in r["audit"].values():
            for it in screen:
                issues.setdefault((it["kind"], it["text"]), it)
    audit_lines = [f"- {FIX_HINTS[k][0]}: '{t}' ({it['detail']})" for (k, t), it in list(issues.items())[:25]]
    if complete:
        outcomes = []
        for r in results:
            p = personas[r["persona"]]
            words = "; ".join(f"step {s['i'] + 1}: {s['action']} — \"{s['thought']}\""
                              for s in r["steps"] if s.get("thought"))[:600]
            outcomes.append(f"- {p.name} ({r['variant']}): {summarise(r)}. {('Reason: ' + r['reason']) if r['reason'] else ''} {words}")
        prompt = FINDINGS_PROMPT.format(task=task, outcomes="\n".join(outcomes), audit="\n".join(audit_lines) or "(none)")
        try:
            sysmsg = {"role": "system", "content": "You are a senior UX researcher. Reply with one JSON object only."}
            raw = complete([sysmsg, {"role": "user", "content": prompt}])
            if not (raw or "").strip():  # reasoning models can spend the whole budget thinking: ask again, briefly
                raw = complete([sysmsg, {"role": "user", "content": prompt[:6000] + "\n\nAnswer straight away with "
                                 "the JSON; keep any reasoning very short."}])
            got, summary = parse_findings(raw)
            if got:
                summary_out.extend(summary or headline(results, personas))
                return got, "model"
            note = f"model reply had no findings: {str(raw)[:200]!r}"
        except Exception as exc:  # noqa: BLE001 - recorded, then the deterministic checks are used
            note = f"model call failed: {str(exc)[:200]}"
        issues_note.append(note)
    by_kind: dict[str, list] = {}
    for (k, t), it in issues.items():
        by_kind.setdefault(k, []).append(t)
    ran = {r["persona"] for r in results}
    status = {r["persona"]: r["status"] for r in results if r["variant"] == "before"}
    steps = sorted(r["n_steps"] for r in results if r["variant"] == "before" and r["status"] == "success") or [0]
    median = steps[len(steps) // 2]
    out = []
    for k in by_kind:
        who = [p for p in WHO.get(k, []) if p in ran]
        # Severity follows what happened in this run, not the rule's worst case.
        if any(status.get(p) not in (None, "success") for p in who):
            sev = FIX_HINTS[k][1]
        elif any(r["persona"] in who and r["n_steps"] > max(4, median * 1.5) for r in results):
            sev = "major" if FIX_HINTS[k][1] != "minor" else "minor"
        else:
            sev = "minor"
        examples = ", ".join(f"'{t}'" for t in by_kind[k][:3])
        out.append({"title": FIX_HINTS[k][0], "severity": sev, "who": [personas[p].first_name for p in who],
                    "what": f"Automated check, found on {len(by_kind[k])} element{'s' if len(by_kind[k]) != 1 else ''}.",
                    "evidence": [f"For example {examples}"] + (["Nobody was held up by it in this run"] if sev == "minor" and who else []),
                    "fix": [FIX_HINTS[k][2]]})
    # What people actually ran into comes first: give-ups and taps that did nothing.
    for r in results:
        p = personas[r["persona"]].first_name
        if r["status"] in ("gave_up", "false_done", "out_of_steps"):
            out.append({"title": f"{p} could not finish", "severity": "blocker", "who": [p],
                        "what": f"{p} stopped after {r['n_steps']} steps.", "evidence": [f"“{r['quote']}”"],
                        "fix": ["Open the replay to see the screen where they got stuck."]})
        elif r["dead_clicks"] >= 2:
            out.append({"title": f"Taps that did nothing for {p}", "severity": "major", "who": [p],
                        "what": f"{r['dead_clicks']} of {p}'s taps changed nothing on screen.",
                        "evidence": [f"{r['dead_clicks']} dead taps in {r['n_steps']} steps"],
                        "fix": ["Make tap targets larger", "Give every tap visible feedback"]})
    rank = {"blocker": 0, "major": 1, "minor": 2}
    out.sort(key=lambda f: rank.get(f["severity"], 2))
    summary_out.extend(headline(results, personas))
    return out[:5], "checks"


def headline(results: list[dict], personas: dict) -> list[str]:
    """2-3 plain bullets that tell the story of the run, without the model."""
    out = []
    variants = [v for v in ("before", "after") if any(r["variant"] == v for r in results)]
    for v in variants:
        rs = [r for r in results if r["variant"] == v]
        ok = sum(r["status"] == "success" for r in rs)
        stuck = [personas[r["persona"]].first_name for r in rs if r["status"] != "success"]
        label = "" if len(variants) == 1 else (" before the fix" if v == "before" else " after the fix")
        out.append(f"{ok} of {len(rs)} people finished{label}" + (f"; {', '.join(stuck)} did not." if stuck else "."))
    dead = sum(r["dead_clicks"] for r in results if r["variant"] == "before")
    if dead:
        out.append(f"{dead} taps did nothing{' before the fix' if len(variants) > 1 else ''}.")
    return out[:3]


def run_test(url: str, task: str, complete: Complete, personas: list[Persona], data_dir: Path,
             success_text: str = "", compare_url: str = "", facts: str = "", max_steps: int = 20,
             parallel: int = 3, viewport=(420, 860), title: str = "", label: str = "",
             findings_complete: Optional[Complete] = None, time_budget: float = 330,
             allow_private_hosts: bool = False) -> dict:
    guard = Guard(allow_private_hosts)
    url = guard.check(normalise(url))
    compare_url = guard.check(normalise(compare_url)) if compare_url else ""
    run_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    run_dir = Path(data_dir) / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    variants = [("before", url)] + ([("after", compare_url)] if compare_url else [])
    meta = {"id": run_id, "url": url, "compare_url": compare_url, "task": task, "title": title or label or url,
            "success_text": success_text, "created": time.time(), "personas_order": [p.id for p in personas],
            "variants": [v for v, _ in variants], "viewport": list(viewport),
            "people": [{"id": p.id, "name": p.name, "first": p.first_name, "initials": p.initials, "icon": p.icon,
                        "condition": p.condition, "blurb": p.blurb} for p in personas]}
    state = RunState(run_dir, meta)
    jobs = [(v, u, p) for v, u in variants for p in personas]
    deadline = time.time() + time_budget if time_budget else 0
    results: list[dict] = []
    try:
        pool = ThreadPoolExecutor(max_workers=max(1, min(parallel, len(jobs))))
        futs = [pool.submit(run_persona, u, p, v, task, complete, run_dir, state, success_text, facts,
                            max_steps, viewport, 7, deadline, guard) for v, u, p in jobs]
        for (v, u, p), f in zip(jobs, futs):
            try:
                # Never wait past the budget for a stuck browser: the tool must answer inside Hermes's timeout.
                wait = max(5.0, deadline + 20 - time.time()) if deadline else None
                res = f.result(timeout=wait)
                if not isinstance(res, dict):
                    raise RuntimeError("this person's browser stopped without a result")
                results.append(res)
            except Exception as exc:
                f.cancel()
                err = "time ran out (the page was too slow to respond)" if isinstance(exc, FuturesTimeout) else \
                    str(exc).splitlines()[0][:300]
                state.update(f"{v}:{p.id}", status="error", reason=err)
                results.append({"persona": p.id, "variant": v, "status": "error", "reason": err, "steps": [],
                                "n_steps": 0, "dead_clicks": 0, "quote": "", "first_screen_clicks": [],
                                "first_shot": "", "final_shot": "", "seconds": 0, "audit": {}})
        pool.shutdown(wait=False, cancel_futures=True)
        if results and all(r["status"] == "error" for r in results):
            raise RuntimeError(f"No one could start: {results[0]['reason'][:300]}")
        state.set(status="writing report")
        pmap = {p.id: p for p in personas}
        notes: list = []
        summary: list = []
        found, source = findings(task, [r for r in results if r["status"] != "error"], pmap,
                                 findings_complete or complete, notes, summary)
        score = {v: {"passed": sum(r["status"] == "success" for r in results if r["variant"] == v),
                     "total": sum(1 for r in results if r["variant"] == v)} for v, _ in variants}
        result = {**meta, "results": results, "findings": found, "findings_source": source, "summary": summary,
                  "findings_note": notes[0] if notes else "", "score": score,
                  "finished": time.time()}
        for r in results:
            r["summary"] = summarise(r) if r["status"] != "error" else f"Run stopped: {r['reason']}"
        (run_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        from .report import write_report
        # Playwright's sync API refuses a thread that runs an asyncio loop (Hermes may call us from one).
        with ThreadPoolExecutor(max_workers=1) as one:
            paths = one.submit(write_report, run_dir, result, pmap, tuple(viewport)).result()
        state.set(status="done", score=score, findings=found, report="report.html", card="card.png")
        result.update(paths)
        result["dir"] = str(run_dir)
        return result
    except Exception as exc:
        state.set(status="error", error=str(exc)[:300])
        raise
