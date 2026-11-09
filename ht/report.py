"""Self-contained HTML report (replays included) and a 1200x675 summary card PNG.

Visual language: a usability lab's session log. Ink on cool white, one ultramarine accent, square edges,
hairlines, monospace for metadata. Pass/fail always carries a symbol as well as a colour.
"""
from __future__ import annotations

import base64
import hashlib
import html
import time
from pathlib import Path
from urllib.parse import urlparse

from .icons import icon

ASSETS = Path(__file__).resolve().parent.parent / "assets"
STATUS = {"success": ("Finished", "pass", "check"), "gave_up": ("Gave up", "fail", "cross"),
          "false_done": ("False finish", "warn", "alert"), "out_of_steps": ("Stuck", "fail", "cross"),
          "error": ("Run error", "muted", "alert")}
SEV = {"blocker": "Blocker", "major": "Major", "minor": "Minor"}

BASE_CSS = """
:root{--ink:#111316;--ink2:#555b66;--ink3:#8d939d;--paper:#fafafa;--rule:#e7e8ec;--blue:#2a3cff;--blue-soft:#f1f2ff;
--fail:#d93a24;--pass:#13834f;--warn:#b26a00;
--sans:"Inter","Segoe UI Variable Text","Segoe UI","Helvetica Neue",Arial,sans-serif;
--mono:"JetBrains Mono","Cascadia Mono","SF Mono",Consolas,"Liberation Mono",monospace}
*{box-sizing:border-box}
.label{font:600 11px/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--ink3)}
.st{display:inline-flex;align-items:center;gap:5px;font:600 13px/1 var(--sans);white-space:nowrap}
.st.pass{color:var(--pass)} .st.fail{color:var(--fail)} .st.warn{color:var(--warn)} .st.muted{color:var(--ink3)}
.cond{display:inline-flex;align-items:center;gap:5px;font:13px/1.2 var(--sans);color:var(--ink3)}
.av{width:40px;height:40px;flex:none;border-radius:50%;background:var(--blue);color:#fff;display:flex;align-items:center;
  justify-content:center;overflow:hidden}
.av img{width:100%;height:100%;object-fit:cover;display:block}
.av .ini{font:700 15px var(--sans)}
"""

CSS = BASE_CSS + """
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.6 var(--sans)}
.wrap{max-width:1000px;margin:0 auto;padding:0 32px 80px}
.top{display:flex;gap:16px;align-items:center;padding:22px 0;color:var(--ink3);font:12px var(--mono)}
.top .brand{font:700 12px var(--mono);letter-spacing:.14em;color:var(--ink)} .top .brand b{color:var(--blue)}
.top .when{margin-left:auto}
h1{font:800 40px/1.08 var(--sans);letter-spacing:-.03em;margin:18px 0 10px}
.task{margin:0;font-size:18px;color:var(--ink2);max-width:760px} .meta{margin-top:8px;font:12px var(--mono);color:var(--ink3)}
.hero{display:grid;grid-template-columns:auto 1fr;gap:56px;align-items:center;margin:48px 0 8px}
.nums{display:flex;align-items:flex-end;gap:14px}
.num .n{font:800 84px/.9 var(--sans);letter-spacing:-.05em} .num .n small{font-size:34px;color:var(--ink3);letter-spacing:-.02em}
.num .label{margin-top:10px} .arrow{font:300 44px/1 var(--sans);color:var(--ink3);padding-bottom:20px}
.fr{margin-top:14px;font:12px var(--mono);color:var(--ink3)} .fr b{color:var(--ink);font-weight:600}
.glance{margin:0;padding:0;list-style:none;font-size:17px;line-height:1.5}
.glance li{padding:6px 0 6px 18px;position:relative} .glance li:before{content:"";position:absolute;left:0;top:16px;width:6px;height:6px;background:var(--blue);border-radius:50%}
h2{font:700 13px var(--sans);letter-spacing:.02em;color:var(--ink3);margin:64px 0 14px;text-transform:none}
table.res{border-collapse:collapse;width:100%}
.res th{text-align:left;font:600 11px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--ink3);padding:0 0 10px}
.res td{padding:12px 16px 12px 0;border-top:1px solid var(--rule);vertical-align:middle}
.who{display:flex;align-items:center;gap:12px} .who .av{width:32px;height:32px} .who .av .ini{font-size:12px}
.who b{font-weight:650}
.sub{display:block;font:12px var(--mono);color:var(--ink3);margin-top:3px}
.find{padding:26px 0;border-top:1px solid var(--rule);max-width:780px}
.fmeta{display:flex;align-items:center;gap:8px;font:12.5px var(--sans);color:var(--ink3)}
.dot{width:8px;height:8px;border-radius:50%;background:var(--ink3)} .blocker .dot{background:var(--fail)} .major .dot{background:var(--warn)}
.sevw{font-weight:650} .blocker .sevw{color:var(--fail)} .major .sevw{color:var(--warn)}
.find h3{margin:6px 0 6px;font:700 20px/1.3 var(--sans);letter-spacing:-.015em}
.what{margin:0 0 8px;font-size:15.5px;color:var(--ink)}
.ev{margin:0 0 14px;padding-left:18px;color:var(--ink2);font-size:14px} .ev li{margin:2px 0}
.fix{background:var(--blue-soft);padding:14px 18px;border-radius:6px}
.fix .label{color:var(--blue)} .fix ol{margin:8px 0 0;padding-left:18px;font-size:14.5px} .fix li{margin:3px 0}
.people{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:20px}
.colh{font:600 13px var(--sans);color:var(--ink3);margin:0 0 10px}
.subj{background:#fff;border-radius:10px;padding:18px;box-shadow:0 1px 0 var(--rule),0 0 0 1px var(--rule)}
.subj .hd{display:flex;gap:12px;align-items:center}
.subj .nm{font:700 16px/1.2 var(--sans)} .subj .hd .st{margin-left:auto}
.quote{margin:14px 0 0;font:500 16px/1.45 var(--sans);color:var(--ink)}
.sum{margin-top:8px;font:12px var(--mono);color:var(--ink3)}
.film{display:flex;gap:6px;margin-top:14px}
.film .im{width:52px;height:106px;background-size:cover;background-position:top;border-radius:4px;box-shadow:0 0 0 1px var(--rule)}
details{margin-top:12px} summary{cursor:pointer;font:600 13px var(--sans);color:var(--blue)}
.steps{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:12px;margin-top:12px}
.st2{font-size:12.5px;color:var(--ink2)} .st2 .im{width:100%;aspect-ratio:420/860;background-size:cover;background-position:top;border-radius:4px;box-shadow:0 0 0 1px var(--rule);position:relative}
.st2 .im.desk{aspect-ratio:1280/800}
.st2 .tap{position:absolute;width:18px;height:18px;margin:-9px 0 0 -9px;border:2px solid var(--blue);border-radius:50%;background:rgba(42,60,255,.15)}
.st2 .act{font:500 11.5px var(--mono);color:var(--ink);margin-top:6px} .st2 .th{margin-top:2px}
.st2 .dead{font:600 11px var(--mono);color:var(--fail);margin-top:3px}
.aft summary{font-size:14px}
.appx{margin-top:56px;border-top:1px solid var(--rule);padding-top:18px}
.appx summary{color:var(--ink3)} .heat{position:relative;width:280px;margin-top:14px;border-radius:6px;overflow:hidden;box-shadow:0 0 0 1px var(--rule)}
.heat .im{width:100%;aspect-ratio:420/860;background-size:cover;background-position:top} .heat .im.desk{aspect-ratio:1280/800}
.heat i{position:absolute;width:20px;height:20px;margin:-10px 0 0 -10px;border-radius:50%;background:var(--blue);color:#fff;
  font:700 9.5px/20px var(--mono);text-align:center;font-style:normal;box-shadow:0 0 0 2px #fff}
.note{font-size:13px;color:var(--ink3)}
.foot{margin-top:56px;font-size:12.5px;color:var(--ink3);max-width:720px}
"""


def _esc(s) -> str:
    return html.escape(str(s or ""))


def _avatar_b64(pid: str) -> str:
    for ext in ("jpg", "png"):
        p = ASSETS / "avatars" / f"{pid}.{ext}"
        if p.exists():
            return f"data:image/{'jpeg' if ext == 'jpg' else 'png'};base64," + base64.b64encode(p.read_bytes()).decode()
    return ""


def avatar(person: dict, cache: dict) -> str:
    pid = person["id"]
    if pid not in cache:
        cache[pid] = _avatar_b64(pid)
    src = cache[pid]
    inner = f'<img src="{src}" alt="">' if src else f'<span class="ini">{_esc(person["initials"])}</span>'
    return f'<div class="av">{inner}</div>'


def cond(person: dict) -> str:
    return f'<span class="cond">{icon(person["icon"], 14)}{_esc(person["condition"])}</span>'


def stamp(status: str) -> str:
    label, cls, ic = STATUS.get(status, STATUS["error"])
    return f'<span class="st {cls}">{icon(ic, 14)}{label}</span>'


class Images:
    """Embeds each distinct screenshot once as a CSS class (keeps the report one file, without duplicates)."""

    def __init__(self, shots: Path):
        self.shots, self.cls = shots, {}

    def __call__(self, name: str) -> str:
        if not name:
            return ""
        p = self.shots / name
        if not p.exists():
            return ""
        data = p.read_bytes()
        key = hashlib.sha1(data).hexdigest()[:10]
        if key not in self.cls:
            self.cls[key] = base64.b64encode(data).decode()
        return f"i{key}"

    def css(self) -> str:
        return "".join(f".i{k}{{background-image:url(data:image/jpeg;base64,{v})}}" for k, v in self.cls.items())


def _people(res: dict) -> dict:
    """Person metadata by id (from the run; older runs fall back to the built-in list)."""
    if res.get("people"):
        return {p["id"]: p for p in res["people"]}
    from .personas import PERSONAS
    return {k: {"id": k, "name": p.name, "first": p.first_name, "initials": p.initials, "icon": p.icon,
                "condition": p.condition, "blurb": p.blurb} for k, p in PERSONAS.items()}


def _order(res: dict, variant: str) -> list:
    order = res["personas_order"]
    return sorted((r for r in res["results"] if r["variant"] == variant),
                  key=lambda r: order.index(r["persona"]) if r["persona"] in order else 99)


def _subject(r: dict, person: dict, img: Images, desk: bool, vw: int, vh: int, av: dict) -> str:
    steps = [s for s in r["steps"] if s.get("shot")]
    picks = steps[:: max(1, len(steps) // 4)][:4] if steps else []
    film = "".join(f'<div class="im {img(s["shot"])}"></div>' for s in picks)
    if r.get("final_shot"):
        film += f'<div class="im {img(r["final_shot"])}"></div>'
    rows = []
    for s in r["steps"]:
        tap = ""
        if s.get("click"):
            x, y = s["click"]
            tap = f'<span class="tap" style="left:{x / vw * 100:.1f}%;top:{y / vh * 100:.1f}%"></span>'
        dead = '<div class="dead">nothing happened</div>' if s.get("kind") == "click" and s.get("changed") is False else ""
        err = f'<div class="dead">{_esc(s["error"][:90])}</div>' if s.get("error") else ""
        rows.append(f'<div class="st2"><div class="im {"desk " if desk else ""}{img(s.get("shot"))}">{tap}</div>'
                    f'<div class="act">{s["i"] + 1}. {_esc(s["action"])}</div>'
                    + (f'<div class="th">{_esc(s["thought"])}</div>' if s.get("thought") else "") + dead + err + "</div>")
    quote = f'<p class="quote">“{_esc(r["quote"])}”</p>' if r.get("quote") else ""
    return (f'<div class="subj"><div class="hd">{avatar(person, av)}<div><div class="nm">{_esc(person.get("first") or person["name"])}</div>'
            f'{cond(person)}</div>{stamp(r["status"])}</div>{quote}<div class="sum">{_esc(r.get("summary", ""))}</div>'
            f'<div class="film">{film}</div>'
            + (f'<details><summary>Replay {len(r["steps"])} steps</summary><div class="steps">{"".join(rows)}</div></details>'
               if rows else "") + "</div>")


def _matrix(res: dict, people: dict, av: dict) -> str:
    variants = res["variants"]
    head = "".join(f'<th>{"Result" if len(variants) == 1 else ("Before" if v == "before" else "After")}</th>' for v in variants)
    rows = []
    for r in _order(res, "before"):
        person = people.get(r["persona"], {"id": r["persona"], "name": r["persona"], "initials": "?", "icon": "new", "condition": ""})
        cells = []
        for v in variants:
            x = next((y for y in res["results"] if y["variant"] == v and y["persona"] == r["persona"]), None)
            if x:
                extra = f'{x["n_steps"]} steps' + (f' · {x["dead_clicks"]} dead taps' if x["dead_clicks"] else "")
                cells.append(f'<td>{stamp(x["status"])}<span class="sub">{extra}</span></td>')
            else:
                cells.append("<td></td>")
        rows.append(f'<tr><td><div class="who">{avatar(person, av)}<div><b>{_esc(person.get("first") or person["name"])}</b>'
                    f'<span class="sub" style="font-family:var(--sans)">{_esc(person.get("condition", ""))}</span></div></div></td>'
                    f'{"".join(cells)}</tr>')
    return f'<table class="res"><tr><th>Person</th>{head}</tr>{"".join(rows)}</table>'


def _friction(res: dict) -> str:
    """Dead taps and steps, before -> after: the improvement when the pass count alone doesn't show it."""
    if len(res["variants"]) < 2:
        return ""
    tot = {v: (sum(r["dead_clicks"] for r in res["results"] if r["variant"] == v),
               sum(r["n_steps"] for r in res["results"] if r["variant"] == v)) for v in res["variants"]}
    (d0, s0), (d1, s1) = tot["before"], tot["after"]
    if d0 == d1 and s0 == s1:
        return ""
    return f'<div class="fr">Dead taps <b>{d0} → {d1}</b> &nbsp;·&nbsp; Steps <b>{s0} → {s1}</b></div>'


def _nums(res: dict) -> str:
    out = []
    for i, v in enumerate(res["variants"]):
        sc = res["score"][v]
        label = "finished" if len(res["variants"]) == 1 else ("before" if v == "before" else "after changes")
        if i:
            out.append('<div class="arrow">→</div>')
        out.append(f'<div class="num"><div class="n">{sc["passed"]}<small>/{sc["total"]}</small></div>'
                   f'<div class="label">{label}</div></div>')
    return f'<div class="sb"><div class="nums">{"".join(out)}</div>{_friction(res)}</div>'


def _as_list(v) -> list:
    return [x for x in (v if isinstance(v, list) else [v] if v else []) if str(x).strip()]


def _findings(res: dict) -> str:
    if not res["findings"]:
        return '<p class="note">No barriers found for these people on this task.</p>'
    out = []
    for f in res["findings"]:
        sev = f.get("severity") if f.get("severity") in SEV else "major"
        who = ", ".join(_esc(w) for w in f.get("who", []))
        ev = "".join(f"<li>{_esc(e)}</li>" for e in _as_list(f.get("evidence")))
        fixes = "".join(f"<li>{_esc(x)}</li>" for x in _as_list(f.get("fix")))
        out.append(f'<article class="find {sev}"><div class="fmeta"><span class="dot"></span><span class="sevw">{SEV[sev]}</span>'
                   + (f'<span>·</span><span>{who}</span>' if who else "") + f'</div><h3>{_esc(f["title"])}</h3>'
                   + (f'<p class="what">{_esc(f["what"])}</p>' if f.get("what") else "")
                   + (f'<ul class="ev">{ev}</ul>' if ev else "")
                   + (f'<div class="fix"><div class="label">Fix</div><ol>{fixes}</ol></div>' if fixes else "") + "</article>")
    return "".join(out)


def _glance(res: dict) -> str:
    items = res.get("summary") or []
    return ('<ul class="glance">' + "".join(f"<li>{_esc(s)}</li>" for s in items) + "</ul>") if items else "<div></div>"


def build_html(res: dict, personas: dict, shots: Path, viewport=(420, 860)) -> str:
    img, av, people = Images(shots), {}, _people(res)
    vw, vh = viewport
    desk = vw > vh
    host = urlparse(res["url"]).netloc or res["url"]
    blank = {"name": "?", "initials": "?", "icon": "new", "condition": "", "blurb": ""}
    cols = []
    for v in res["variants"]:
        cards = "".join(_subject(r, people.get(r["persona"], {**blank, "id": r["persona"]}), img, desk, vw, vh, av)
                        for r in _order(res, v))
        if v == "after":  # the results table already says how the fix went; keep these sessions one click away
            cols.append(f'<details class="aft"><summary>Sessions after changes</summary><div class="people" '
                        f'style="margin-top:14px">{cards}</div></details>')
        else:
            cols.append(f'<div class="people">{cards}</div>')
    before = [r for r in _order(res, "before") if r.get("first_shot")]
    heat = ""
    if before:
        first = img(before[0]["first_shot"])
        dots = "".join(f'<i style="left:{x / vw * 100:.1f}%;top:{y / vh * 100:.1f}%">{_esc(people.get(r["persona"], {}).get("initials", "?"))}</i>'
                       for r in before for x, y in r["first_screen_clicks"] if 0 <= y <= vh)
        heat = (f'<details class="appx"><summary>Where people tapped on the first screen</summary>'
                f'<div class="heat"><div class="im {"desk " if desk else ""}{first}"></div>{dots}</div>'
                f'<p class="note">Each mark is one tap, labelled with the person’s initial.</p></details>')
    when = time.strftime("%d %b %Y, %H:%M", time.localtime(res.get("finished", time.time())))
    body = f"""<div class="wrap"><div class="top"><span class="brand">HALLWAY<b>/</b>TEST</span><span>{_esc(host)}</span>
<span class="when">{when}</span></div>
<h1>{_esc(res.get('title') or host)}</h1>
<p class="task">{_esc(res['task'])}</p>
<div class="meta">{len(res['personas_order'])} people · real browsers · limits enforced in code</div>
<div class="hero">{_nums(res)}{_glance(res)}</div>
<h2>Results</h2>{_matrix(res, people, av)}
<h2>What got in the way</h2>{_findings(res)}
<h2>Sessions</h2><div style="display:grid;gap:28px">{''.join(cols)}</div>
{heat}
<p class="foot">Generated by Hallway Test for Hermes Agent. Perception (text size, contrast, colour vision, screen-reader
access) and abilities (mouse, keyboard, tremor) are enforced by code; the model only decides what each person does next.
Simulated people are not a substitute for testing with real users.</p></div>"""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            f'<title>Hallway Test · {_esc(host)}</title><style>{CSS}</style><style id="ht-img">{img.css()}</style></head>'
            f'<body>{body}</body></html>')


CARD_CSS = BASE_CSS + """
body{margin:0;width:1200px;height:675px;overflow:hidden;background:var(--paper);color:var(--ink);font:15px/1.4 var(--sans)}
.c{display:grid;grid-template-columns:560px 1fr;height:675px}
.l{padding:52px 48px 46px 60px;display:flex;flex-direction:column}
.brand{font:700 13px var(--mono);letter-spacing:.14em} .brand b{color:var(--blue)}
h1{font:800 42px/1.05 var(--sans);letter-spacing:-.035em;margin:26px 0 12px}
.task{font-size:17px;line-height:1.45;color:var(--ink2)}
.sb{margin-top:auto} .nums{display:flex;align-items:flex-end;gap:16px}
.num .n{font:800 112px/.88 var(--sans);letter-spacing:-.055em} .num .n small{font-size:44px;color:var(--ink3)}
.num .label{margin-top:12px} .arrow{font:300 54px/1 var(--sans);color:var(--ink3);padding-bottom:26px}
.fr{margin-top:14px;font:13px var(--mono);color:var(--ink3)} .fr b{color:var(--ink);font-weight:600}
.r{padding:52px 60px 46px 20px;display:flex;flex-direction:column;justify-content:center}
.p{display:grid;grid-template-columns:52px 1fr auto;gap:16px;align-items:center;padding:13px 0;border-top:1px solid var(--rule)}
.p:first-child{border-top:0} .p .av{width:52px;height:52px}
.p .nm{font:700 18px/1.1 var(--sans);margin-bottom:5px}
.res2{display:flex;align-items:center;gap:8px} .res2 .to{color:var(--ink3)} .res2 .st{font-size:14px}
"""


def build_card(res: dict, personas: dict) -> str:
    host = urlparse(res["url"]).netloc or res["url"]
    people, av = _people(res), {}
    rows = []
    for r in _order(res, "before")[:5]:
        person = people.get(r["persona"], {"id": r["persona"], "name": r["persona"], "first": r["persona"], "initials": "?",
                                           "icon": "new", "condition": ""})
        after = next((a for a in res["results"] if a["variant"] == "after" and a["persona"] == r["persona"]), None)
        res_html = stamp(r["status"]) + (f'<span class="to">→</span>{stamp(after["status"])}' if after else "")
        rows.append(f'<div class="p">{avatar(person, av)}<div><div class="nm">{_esc(person.get("first") or person["name"])}</div>'
                    f'{cond(person)}</div><div class="res2">{res_html}</div></div>')
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{CARD_CSS}</style></head><body><div class="c"><div class="l">'
            f'<div class="brand">HALLWAY<b>/</b>TEST</div><h1>{_esc(res.get("title") or host)}</h1>'
            f'<div class="task">{_esc(res["task"])}</div>{_nums(res)}</div>'
            f'<div class="r">{"".join(rows)}</div></div></body></html>')


def write_report(run_dir: Path, res: dict, personas: dict, viewport=(420, 860)) -> dict:
    run_dir = Path(run_dir)
    (run_dir / "report.html").write_text(build_html(res, personas, run_dir / "shots", viewport), encoding="utf-8")
    (run_dir / "card.html").write_text(build_card(res, personas), encoding="utf-8")
    from playwright.sync_api import sync_playwright
    from .run import launch
    with sync_playwright() as pw:
        br = launch(pw)
        try:
            pg = br.new_page(viewport={"width": 1200, "height": 675}, device_scale_factor=2)
            pg.goto((run_dir / "card.html").resolve().as_uri())
            pg.screenshot(path=str(run_dir / "card.png"))
        finally:
            br.close()
    return {"report": str(run_dir / "report.html"), "card": str(run_dir / "card.png")}
