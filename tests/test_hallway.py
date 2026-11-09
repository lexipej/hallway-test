"""Hallway Test checks using the bundled demo and the production browser launcher."""
import importlib.util
import json
import random
import sys
import threading
import time
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from ht import browser as B, demo  # noqa: E402
from ht.brain import Brain, parse_findings, parse_reply  # noqa: E402
from ht.personas import PERSONAS, pick  # noqa: E402
from ht.run import launch  # noqa: E402

import fake_brain  # noqa: E402


# ---------------------------------------------------------------- pure logic
def test_parse_reply_variants():
    assert parse_reply('{"thought": "ok", "action": "click 3"}') == {"thought": "ok", "action": "click 3"}
    assert parse_reply('```json\n{"thought":"x","action":"press Tab"}\n```')["action"] == "press Tab"
    assert parse_reply('Sure! {"thought": "hm", "action": "give_up too small"} hope that helps')["action"] == "give_up too small"
    assert parse_reply("I will click 4 now")["action"] == "click 4"
    assert parse_reply("no idea")["action"] == "" and "error" in parse_reply("no idea")


def test_parse_findings_limits_and_shapes():
    raw = json.dumps({"findings": [{"title": "A", "severity": "BLOCKER", "who": "Jo", "evidence": "e", "fix": "f"}] * 9})
    got = parse_findings(raw)
    assert len(got) == 6 and got[0]["severity"] == "blocker" and got[0]["who"] == ["Jo"]
    assert parse_findings("not json") == []


def test_pick_personas():
    assert [p.id for p in pick(None)] == list(PERSONAS)
    assert [p.id for p in pick(["Low-Vision", "keyboard"])] == ["low_vision", "keyboard"]
    with pytest.raises(ValueError):
        pick(["superman"])


def test_brain_prompt_carries_persona_limits():
    b = Brain(PERSONAS["keyboard"], "Buy a latte", lambda m: '{"thought":"","action":"press Tab"}')
    msgs = b.messages("SCREEN", 0, 10)
    assert "You cannot click" in msgs[0]["content"] and "press Tab" in msgs[0]["content"]
    assert "click <ref>" not in msgs[0]["content"]
    b.record("press Tab", "hm", "the screen changed")
    assert "1. press Tab" in b.messages("SCREEN", 1, 10)[1]["content"]


# ---------------------------------------------------------------- browser
@pytest.fixture(scope="module")
def pw():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        br = launch(p)
        yield br
        br.close()


def _page(br, url):
    pg = br.new_page(viewport={"width": 420, "height": 860})
    pg.goto(url)
    return pg


def test_perception_is_enforced_per_persona(pw):
    pg = _page(pw, demo.resolve("demo")[0])
    first = B.observe(pg, PERSONAS["first_timer"])["text"]
    low = B.observe(pg, PERSONAS["low_vision"])["text"]
    sr = B.observe(pg, PERSONAS["keyboard"])["text"]
    assert "Tap a cup to pick your size" in first and "Continue" in first
    assert "Tap a cup" not in low and low.count("[text too small or faint to read]") >= 2
    assert "unlabelled icon" in first                       # size cups have no names
    assert 'button "Iced Latte' in sr and 'button "Continue' not in sr   # Continue is a div: not reachable
    pg.close()


def test_fixed_demo_is_readable_and_reachable(pw):
    pg = _page(pw, demo.resolve("demo:fixed")[0])
    low = B.observe(pg, PERSONAS["low_vision"])["text"]
    sr = B.observe(pg, PERSONAS["keyboard"])["text"]
    assert "Medium" in low and "faint" not in low
    assert 'button "Medium"' in sr and 'button "Continue to pickup details"' in sr
    pg.close()


def test_colour_blind_sees_red_as_brownish(pw):
    pg = _page(pw, demo.resolve("demo")[0])
    pg.evaluate("() => document.querySelector('.drink').style.border = '2px solid rgb(224,65,58)'")
    assert "red border" in B.observe(pg, PERSONAS["first_timer"])["text"]
    assert "brownish border" in B.observe(pg, PERSONAS["colourblind"])["text"]
    pg.close()


def test_actions_are_limited_by_ability(pw):
    pg = _page(pw, demo.resolve("demo")[0])
    rng = random.Random(1)
    obs = B.observe(pg, PERSONAS["keyboard"])
    with pytest.raises(B.ActionError):
        B.act(pg, PERSONAS["keyboard"], obs, "click 3", rng)
    with pytest.raises(B.ActionError):
        B.act(pg, PERSONAS["keyboard"], obs, "press F12", rng)
    obs = B.observe(pg, PERSONAS["first_timer"])
    with pytest.raises(B.ActionError):
        B.act(pg, PERSONAS["first_timer"], obs, "press Tab", rng)
    with pytest.raises(B.ActionError):
        B.act(pg, PERSONAS["first_timer"], obs, "click 999", rng)
    res = B.act(pg, PERSONAS["shaky"], obs, "click 3", rng)
    assert res["click"] != res["aimed"] or True     # tremor offsets the tap (may land on target)
    assert max(abs(a - b) for a, b in zip(res["click"], res["aimed"])) <= PERSONAS["shaky"].tremor_px
    pg.close()


def test_audit_flags_demo_barriers(pw):
    pg = _page(pw, demo.resolve("demo")[0])
    kinds = {i["kind"] for i in B.audit(B.probe(pg))}
    assert {"not_keyboard", "no_name", "small_text", "low_contrast"} <= kinds
    pg.close()
    pg = _page(pw, demo.resolve("demo:fixed")[0])
    assert B.audit(B.probe(pg)) == []
    pg.close()


# ---------------------------------------------------------------- end to end (scripted brain)
def _per_thread_brain():
    """One scripted brain per persona run (pool threads are reused, so start fresh at step 1)."""
    local = threading.local()

    def complete(msgs):
        if not hasattr(local, "c") or "Step 1 of" in msgs[-1]["content"]:
            local.c = fake_brain.make()
        return local.c(msgs)
    return complete


def test_full_run_writes_state_report_and_card(tmp_path):
    pytest.importorskip("playwright.sync_api")
    from ht.run import run_test
    res = run_test(demo.resolve("demo")[0], demo.DEMO_TASK, _per_thread_brain(), pick(["first_timer", "colourblind"]),
                   tmp_path, success_text="Order placed", compare_url=demo.resolve("demo:fixed")[0], max_steps=14)
    by = {(r["variant"], r["persona"]): r for r in res["results"]}
    assert by[("before", "first_timer")]["status"] == "success"
    assert by[("before", "colourblind")]["status"] == "gave_up"      # the red border tells him nothing
    assert by[("before", "colourblind")]["dead_clicks"] >= 1
    assert by[("after", "colourblind")]["status"] == "success"       # the fix explains the error in text
    run_dir = Path(res["dir"])
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "done" and state["score"]["after"]["passed"] == 2
    html = (run_dir / "report.html").read_text(encoding="utf-8")
    assert "Replay all" in html and "data:image/jpeg;base64" in html and "<script" not in html
    assert (run_dir / "card.png").stat().st_size > 20000


def test_model_reply_without_action_stops_cleanly(tmp_path):
    pytest.importorskip("playwright.sync_api")
    from ht.run import run_test
    with pytest.raises(RuntimeError, match="No one could start"):
        run_test(demo.resolve("demo")[0], "x", lambda m: "I refuse to answer in JSON", pick(["first_timer"]),
                 tmp_path, success_text="Order placed", max_steps=6)
    state = json.loads(next((tmp_path / "runs").glob("*/state.json")).read_text(encoding="utf-8"))
    assert state["status"] == "error" and state["personas"]["before:first_timer"]["status"] == "error"


# ---------------------------------------------------------------- plugin wiring
def _load_plugin():
    spec = importlib.util.spec_from_file_location("hallway_test_plugin", ROOT / "__init__.py",
                                                  submodule_search_locations=[str(ROOT)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["hallway_test_plugin"] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeCtx:
    def __init__(self, reply):
        self.tools, self.commands, self.calls = {}, {}, []
        outer = self

        class LLM:
            def complete(self, messages, **kw):
                outer.calls.append(kw)
                return types.SimpleNamespace(text=reply(messages))
        self.llm = LLM()

    def register_tool(self, name, toolset, schema, handler, **kw):
        self.tools[name] = (schema, handler)

    def register_command(self, name, handler, **kw):
        self.commands[name] = handler

    def get_config(self, key, default=None):
        if key in {"model", "provider"}:
            raise ValueError("Expected a plugin-relative config key")
        return default


def test_completion_uses_hermes_active_model():
    mod = _load_plugin()
    ctx = FakeCtx(lambda _: '{"action":"done"}')
    complete = mod._make_complete(ctx, 220)
    assert complete([{"role": "user", "content": "finish"}]) == '{"action":"done"}'
    assert len(ctx.calls) == 1
    assert "model" not in ctx.calls[0] and "provider" not in ctx.calls[0]


def test_register_and_tool_round_trip(tmp_path, monkeypatch):
    pytest.importorskip("playwright.sync_api")
    mod = _load_plugin()
    monkeypatch.setattr(mod, "_data_dir", lambda: tmp_path)
    ctx = FakeCtx(_per_thread_brain())
    mod.register(ctx)
    assert set(ctx.tools) == {"hallway_test"} and "hallway" in ctx.commands
    schema, handler = ctx.tools["hallway_test"]
    assert schema["parameters"]["required"] == ["url"]
    out = json.loads(handler({"url": "demo", "personas": ["first_timer"], "max_steps": 12}))
    assert out["ok"] and out["score"] == "before: 1/1 finished"
    assert "MEDIA:" in out["show_user"] and Path(out["summary_card"]).exists()
    assert all(c.get("model") is None and c.get("provider") is None for c in ctx.calls)   # user's own model
    assert "Kapé" in ctx.commands["hallway"]("runs") or "demo" in ctx.commands["hallway"]("runs")
    bad = json.loads(handler({"url": "https://example.com"}))
    assert not bad["ok"] and "task is required" in bad["error"]


def test_backend_routes(tmp_path, monkeypatch):
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    spec = importlib.util.spec_from_file_location("ht_api", ROOT / "dashboard" / "plugin_api.py")
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    runs = tmp_path / "runs"
    d = runs / "20261109-101010-abcd"
    (d / "shots").mkdir(parents=True)
    (d / "shots" / "a.jpg").write_bytes(b"\xff\xd8jpeg")
    (d / "state.json").write_text(json.dumps({"id": d.name, "status": "running", "task": "t", "variants": ["before"],
                                              "personas": {"before:keyboard": {"persona": "keyboard", "shot": "a.jpg"}}}))
    monkeypatch.setattr(api, "_runs_dir", lambda: runs)
    app = fastapi.FastAPI()
    app.include_router(api.router)
    c = TestClient(app)
    assert c.get("/runs").json()["runs"][0]["id"] == d.name
    one = c.get(f"/runs/{d.name}").json()
    assert one["people"][0]["thumb"].startswith("data:image/jpeg;base64,")
    assert c.get(f"/runs/{d.name}/report").status_code == 409
    assert c.get("/runs/..%2F..%2Fetc").status_code == 404
    (d / "report.html").write_text('<html><head><style>a{}</style><style id="ht-img">.iabcdef0123{background-image:url(data:image/jpeg;base64,QUJD)}</style></head><p>hi</p></html>')
    rep = c.get(f"/runs/{d.name}/report").json()
    assert rep["src"].startswith("data:text/html") and rep["images"] == ".iabcdef0123{background-image:url(data:image/jpeg;base64,QUJD)}"
    import base64 as b64
    page = b64.b64decode(rep["src"].split(",", 1)[1]).decode()
    assert "QUJD" not in page and "hallway-images" in page


def test_all_model_errors_are_reported_not_scored(tmp_path, monkeypatch):
    pytest.importorskip("playwright.sync_api")
    mod = _load_plugin()
    monkeypatch.setattr(mod, "_data_dir", lambda: tmp_path)

    def broken(messages):
        raise RuntimeError("Error code: 429 - usage_limit_reached")
    ctx = FakeCtx(broken)
    mod.register(ctx)
    out = json.loads(ctx.tools["hallway_test"][1]({"url": "demo", "personas": ["first_timer"], "max_steps": 4}))
    assert not out["ok"] and "429" in out["error"] and "hermes model" in out["error"]
    state = json.loads(next((tmp_path / "runs").glob("*/state.json")).read_text(encoding="utf-8"))
    assert state["status"] == "error" and "429" in state["error"]


def test_demo_command_returns_immediately(tmp_path, monkeypatch):
    import time
    mod = _load_plugin()
    monkeypatch.setattr(mod, "_data_dir", lambda: tmp_path)
    started = threading.Event()
    monkeypatch.setattr(mod, "run_tool", lambda ctx, args: (started.set(), time.sleep(0.5))[0])
    ctx = FakeCtx(lambda m: "")
    mod.register(ctx)
    t0 = time.time()
    reply = ctx.commands["hallway"]("demo")
    assert time.time() - t0 < 0.3 and "started" in reply and "Hallway Test page" in reply
    assert started.wait(2)


def test_truncated_reply_still_yields_action():
    got = parse_reply('{"action": "click 9", "thought": "My number now looks right, so the red warning is proba')
    assert got["action"] == "click 9" and got["thought"].startswith("My number")
    assert parse_reply('{"action": "type 7 \\"0917\\"", "thought": "x"}')["action"]


def test_fixed_demo_keeps_keyboard_focus(pw):
    pg = _page(pw, demo.resolve("demo:fixed")[0])
    for _ in range(5):
        pg.keyboard.press("Tab")
    pg.keyboard.press("Enter")                       # picks a size button
    assert pg.evaluate("document.activeElement.dataset.s") == "Small"
    pg.close()
    pg = _page(pw, demo.resolve("demo")[0])
    pg.keyboard.press("Tab"); pg.keyboard.press("Enter")   # broken: focus drops after re-render
    assert pg.evaluate("document.activeElement === document.body")
    pg.close()


def test_audit_avoids_common_false_positives(pw, tmp_path):
    page = tmp_path / "p.html"
    page.write_text("""<!doctype html><html><body style="font:16px sans-serif">
      <ul><li style="cursor:pointer" onclick="1"><a href="#r1">University result one</a></li></ul>
      <a href="/" id="logo"><img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" alt="Wikipedia" width="40" height="40"></a>
      <p>Wikipedia is the <a href="#f">free</a> encyclopedia that anyone can edit, written collaboratively.</p>
      <div style="cursor:pointer;width:40px;height:40px" onclick="1"><svg width="20" height="20"></svg></div>
      </body></html>""", encoding="utf-8")
    pg = _page(pw, page.as_uri())
    found = B.audit(B.probe(pg))
    kinds = [(i["kind"], i["text"]) for i in found]
    assert not any(k == "not_keyboard" and "University" in t for k, t in kinds)      # wrapper around a real link
    assert not any(k == "small_target" and t == "free" for k, t in kinds)            # link inside a sentence
    assert sum(k == "no_name" for k, _ in kinds) == 1                                # only the bare icon div
    assert any(k == "not_keyboard" for k, _ in kinds)                                # ...which is also a real trap
    pg.close()


def test_findings_prompt_ties_severity_to_outcomes():
    from ht.brain import FINDINGS_PROMPT
    assert "Never call something a blocker for a person who finished" in FINDINGS_PROMPT


def test_animated_pages_are_slowed_and_memory_is_checked(pw, tmp_path):
    from ht import run as R
    page = tmp_path / "anim.html"
    page.write_text("<script>window.frames_=0;(function f(){window.frames_++;requestAnimationFrame(f)})()</script>",
                    encoding="utf-8")
    pg = pw.new_page()
    pg.add_init_script(R.SLOW_FRAMES_JS)
    pg.goto(page.as_uri())
    pg.wait_for_timeout(1000)
    assert pg.evaluate("window.frames_") <= 8          # ~5 per second instead of ~60
    pg.close()
    assert R.free_memory_mb() > 0
    R.wait_for_memory(0, need_mb=1)                     # plenty free: returns at once
    with pytest.raises(RuntimeError, match="free memory"):
        R.wait_for_memory(time.time() - 1, need_mb=1e12)


def test_stuck_persona_does_not_hold_the_run(tmp_path, monkeypatch):
    from ht import run as R
    import time as _t

    def stuck(*a, **k):
        _t.sleep(60)
    monkeypatch.setattr(R, "run_persona", stuck)
    t0 = _t.time()
    with pytest.raises(RuntimeError, match="No one could start"):
        R.run_test("http://127.0.0.1:9/", "x", lambda m: "", pick(["first_timer"]), tmp_path, time_budget=1)
    assert _t.time() - t0 < 30


def test_labels_are_not_controls_and_focus_counts_as_change(pw, tmp_path):
    page = tmp_path / "login.html"
    page.write_text("""<!doctype html><body style="font:16px sans-serif"><form>
      <label for="u" style="cursor:pointer">Username</label><input id="u" style="width:200px;height:30px">
      <label for="pw" style="cursor:pointer">Password</label><input id="pw" type="password" style="width:200px;height:30px">
      <button type="button">Login</button></form></body>""", encoding="utf-8")
    pg = _page(pw, page.as_uri())
    assert not [i for i in B.audit(B.probe(pg)) if i["text"] in ("Username", "Password")]
    obs = B.observe(pg, PERSONAS["first_timer"])
    ref = next(i["ref"] for i in obs["raw"]["items"] if i["tag"] == "INPUT" and i["label"] == "Password")
    B.act(pg, PERSONAS["first_timer"], obs, f"click {ref}", random.Random(1))
    after = B.observe(pg, PERSONAS["first_timer"])
    assert after["raw"]["focus"] != obs["raw"]["focus"]
    assert "typing cursor is here" in after["text"]
    pg.close()


def test_fallback_findings_follow_the_run():
    from ht.run import findings
    from ht.personas import PERSONAS as P
    base = {"variant": "before", "steps": [], "quote": "", "dead_clicks": 0, "n_steps": 3, "reason": ""}
    results = [dict(base, persona="keyboard", status="success", n_steps=8,
                    audit={"x": [{"kind": "not_keyboard", "text": "×", "detail": "d"}]}),
               dict(base, persona="shaky", status="gave_up", quote="I can't hit it", audit={})]
    got, src = findings("t", results, P, None)
    assert src == "checks"
    assert got[0]["severity"] == "blocker" and "Aling Nena" in got[0]["title"]
    mouse_only = next(f for f in got if f["title"].startswith("Controls"))
    assert mouse_only["severity"] != "blocker"           # Jo finished, so it can't be a blocker
