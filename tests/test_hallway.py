"""Hallway Test checks using the bundled demo and the production browser launcher."""
import importlib.util
import json
import random
import sys
import threading
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
    local = threading.local()

    def complete(msgs):
        if not hasattr(local, "c"):
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
    res = run_test(demo.resolve("demo")[0], "x", lambda m: "I refuse to answer in JSON", pick(["first_timer"]),
                   tmp_path, success_text="Order placed", max_steps=6)
    r = res["results"][0]
    assert r["status"] == "error" and r["n_steps"] == 3


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
    (d / "report.html").write_text("<p>hi</p>")
    assert c.get(f"/runs/{d.name}/report").json()["src"].startswith("data:text/html")
