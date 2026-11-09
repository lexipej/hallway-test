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
:root{--ink:#0e1013;--ink2:#4a4f59;--ink3:#8a909b;--paper:#f6f7f9;--card:#fff;--rule:#dfe2e8;--blue:#2a3cff;
--blue-soft:#e9ebff;--fail:#e5341d;--fail-soft:#fde9e6;--pass:#0f8a4f;--pass-soft:#e3f4ea;--warn:#b86e00;--warn-soft:#fff2db;
--sans:"Inter","Segoe UI Variable Text","Segoe UI","Helvetica Neue",Arial,sans-serif;
--mono:"JetBrains Mono","Cascadia Mono","SF Mono",Consolas,"Liberation Mono",monospace}
*{box-sizing:border-box}
.mono{font-family:var(--mono)}
.label{font:600 11px/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--ink3)}
.stamp{display:inline-flex;align-items:center;gap:5px;font:700 11px/1 var(--mono);letter-spacing:.06em;text-transform:uppercase;
  padding:5px 7px;border:1.5px solid currentColor;white-space:nowrap}
.stamp.pass{color:var(--pass);background:var(--pass-soft)} .stamp.fail{color:var(--fail);background:var(--fail-soft)}
.stamp.warn{color:var(--warn);background:var(--warn-soft)} .stamp.muted{color:var(--ink3)}
.cond{display:inline-flex;align-items:center;gap:6px;font:600 11px/1 var(--mono);letter-spacing:.05em;text-transform:uppercase;
  color:var(--blue);background:var(--blue-soft);padding:5px 7px}
.av{width:56px;height:56px;flex:none;background:var(--blue);color:#fff;display:flex;align-items:center;justify-content:center;
  overflow:hidden;position:relative}
.av img{width:100%;height:100%;object-fit:cover;display:block}
.av .ini{font:800 20px var(--sans);letter-spacing:-.02em}
"""

CSS = BASE_CSS + """
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 var(--sans)}
.wrap{max-width:1180px;margin:0 auto;padding:0 32px 64px}
.top{display:flex;gap:18px;flex-wrap:wrap;align-items:center;border-bottom:1.5px solid var(--ink);padding:18px 0 12px;margin-bottom:28px}
.top .brand{font:800 13px var(--mono);letter-spacing:.12em;color:var(--ink)} .top .brand b{color:var(--blue)}
.top .label{margin-left:auto}
h1{font:800 44px/1.02 var(--sans);letter-spacing:-.035em;margin:0 0 16px;max-width:900px}
.task{display:grid;grid-template-columns:90px 1fr;border:1.5px solid var(--ink);background:var(--card);max-width:900px}
.task .label{padding:14px 12px;border-right:1.5px solid var(--ink);color:var(--ink)}
.task p{margin:0;padding:12px 14px;font-size:16px}
.meta{margin-top:10px;font:12px var(--mono);color:var(--ink3)}
.score{display:grid;grid-template-columns:auto 1fr;gap:28px;margin:34px 0 8px;align-items:stretch}
.nums{display:flex;align-items:flex-end;gap:16px}
.num .n{font:800 92px/.9 var(--sans);letter-spacing:-.05em} .num .n small{font-size:40px;color:var(--ink3);letter-spacing:-.02em}
.num .label{margin-top:10px} .arrow{font:300 52px/1 var(--sans);color:var(--ink3);padding-bottom:22px}
.fr{display:flex;gap:18px;margin-top:16px;font:12px var(--mono);color:var(--ink2)} .fr b{color:var(--ink)}
table.matrix{border-collapse:collapse;width:100%;background:var(--card);border:1.5px solid var(--ink)}
.matrix th{text-align:left;padding:9px 12px;border-bottom:1.5px solid var(--ink)}
.matrix td{padding:8px 12px;border-bottom:1px solid var(--rule);vertical-align:middle}
.matrix tr:last-child td{border-bottom:0}
.who{display:flex;align-items:center;gap:10px;font-weight:700} .who .av{width:30px;height:30px} .who .av .ini{font-size:12px}
.small{font:12px var(--mono);color:var(--ink3);margin-left:6px}
h2{font:800 13px var(--mono);letter-spacing:.12em;text-transform:uppercase;margin:46px 0 14px;display:flex;align-items:center;gap:10px}
h2:after{content:"";flex:1;height:1.5px;background:var(--ink)}
.cols{display:grid;grid-template-columns:1fr 300px;gap:28px;align-items:start}
.find{background:var(--card);border:1px solid var(--rule);border-top:4px solid var(--ink3);margin-bottom:14px}
.find.blocker{border-top-color:var(--fail)} .find.major{border-top-color:var(--warn)}
.fh{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;padding:12px 16px;border-bottom:1px solid var(--rule)}
.fh .id{font:700 12px var(--mono);color:var(--ink3)} .fh h3{margin:0;font:750 17px/1.25 var(--sans);letter-spacing:-.01em;flex:1 1 260px}
.sev{font:700 10.5px var(--mono);letter-spacing:.08em;text-transform:uppercase;padding:3px 6px;border:1.5px solid currentColor}
.blocker .sev{color:var(--fail)} .major .sev{color:var(--warn)} .minor .sev{color:var(--ink3)}
.tags{display:flex;flex-wrap:wrap;gap:6px} .tags span{font:600 11px var(--mono);background:var(--paper);border:1px solid var(--rule);padding:3px 6px}
.fb{display:grid;grid-template-columns:1fr 1fr;align-items:stretch}
.prob{padding:12px 16px 14px} .prob .what{margin:0 0 10px;font-size:14.5px;font-weight:600}
.prob ul,.fixbox ol{margin:6px 0 0;padding-left:18px;font-size:13.5px;color:var(--ink2)} .prob li,.fixbox li{margin:3px 0}
.fixbox{background:var(--blue-soft);border-left:3px solid var(--blue);padding:12px 16px 14px}
.fixbox .label{color:var(--blue);font-weight:800} .fixbox ol{color:var(--ink)}
.glance{background:var(--card);border:1.5px solid var(--ink);padding:14px 18px;margin-top:22px}
.glance ul{margin:8px 0 0;padding-left:18px;font-size:15.5px;font-weight:600} .glance li{margin:4px 0}
@media (max-width:760px){.fb{grid-template-columns:1fr}}
.heat{position:relative;border:1.5px solid var(--ink);background:var(--card)} .heat .im{width:100%;aspect-ratio:420/860;background-size:cover;background-position:top}
.heat .im.desk{aspect-ratio:1280/800}
.heat i{position:absolute;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;background:var(--blue);color:#fff;
  font:700 10px/22px var(--mono);text-align:center;font-style:normal;box-shadow:0 0 0 2px #fff;opacity:.9}
.note{font:12px var(--mono);color:var(--ink3);margin-top:8px}
.grid2{display:grid;gap:16px} .grid2.two{grid-template-columns:1fr 1fr}
.colh{font:700 12px var(--mono);letter-spacing:.1em;text-transform:uppercase;margin-bottom:10px}
.subj{background:var(--card);border:1px solid var(--rule);margin-bottom:14px}
.subj .hd{display:flex;gap:14px;align-items:flex-start;padding:14px;border-bottom:1px solid var(--rule)}
.subj .nm{font:800 18px/1.15 var(--sans);letter-spacing:-.02em} .subj .bl{font-size:13px;color:var(--ink2);margin:4px 0 8px}
.subj .st{margin-left:auto}
.quote{margin:0;padding:14px 16px;font:600 17px/1.4 var(--sans);letter-spacing:-.01em;border-left:4px solid var(--blue);background:#fbfbfd}
.sum{padding:8px 16px;font:12px var(--mono);color:var(--ink2);border-top:1px solid var(--rule)}
.film{display:flex;gap:6px;padding:12px 16px;border-top:1px solid var(--rule)}
.film .im{width:62px;height:126px;background-size:cover;background-position:top;border:1px solid var(--rule)}
details{border-top:1px solid var(--rule)} summary{cursor:pointer;padding:10px 16px;font:700 12px var(--mono);letter-spacing:.06em;
  text-transform:uppercase;color:var(--blue)}
.steps{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;padding:4px 16px 16px}
.st2{font-size:12.5px;color:var(--ink2)} .st2 .im{width:100%;aspect-ratio:420/860;background-size:cover;background-position:top;border:1px solid var(--rule);position:relative}
.st2 .im.desk{aspect-ratio:1280/800}
.st2 .tap{position:absolute;width:20px;height:20px;margin:-10px 0 0 -10px;border:2.5px solid var(--blue);border-radius:50%;background:rgba(42,60,255,.18)}
.st2 .act{font:600 11.5px var(--mono);color:var(--ink);margin-top:5px} .st2 .th{margin-top:2px}
.st2 .dead{font:700 11px var(--mono);color:var(--fail);margin-top:3px}
.foot{margin-top:50px;border-top:1.5px solid var(--ink);padding-top:12px;font:12px/1.6 var(--mono);color:var(--ink3)}
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
    return f'<span class="stamp {cls}">{icon(ic, 12)}{label}</span>'


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
        dead = '<div class="dead">✕ nothing happened</div>' if s.get("kind") == "click" and s.get("changed") is False else ""
        err = f'<div class="dead">{_esc(s["error"][:90])}</div>' if s.get("error") else ""
        rows.append(f'<div class="st2"><div class="im {"desk " if desk else ""}{img(s.get("shot"))}">{tap}</div>'
                    f'<div class="act">{s["i"] + 1:02d} · {_esc(s["action"])}</div>'
                    + (f'<div class="th">{_esc(s["thought"])}</div>' if s.get("thought") else "") + dead + err + "</div>")
    quote = f'<p class="quote">“{_esc(r["quote"])}”</p>' if r.get("quote") else ""
    return (f'<div class="subj"><div class="hd">{avatar(person, av)}<div><div class="nm">{_esc(person["name"])}</div>'
            f'<div class="bl">{_esc(person["blurb"])}</div>{cond(person)}</div><div class="st">{stamp(r["status"])}</div></div>'
            f'{quote}<div class="sum">{_esc(r.get("summary", ""))} · {r.get("seconds", 0):.0f}s</div>'
            f'<div class="film">{film}</div>'
            + (f'<details><summary>Replay · {len(r["steps"])} steps</summary><div class="steps">{"".join(rows)}</div></details>'
               if rows else "") + "</div>")


def _matrix(res: dict, people: dict, av: dict) -> str:
    variants = res["variants"]
    head = "".join(f'<th class="label">{"Result" if len(variants) == 1 else ("Before" if v == "before" else "After")}</th>'
                   for v in variants)
    rows = []
    for r in _order(res, "before"):
        person = people.get(r["persona"], {"id": r["persona"], "name": r["persona"], "initials": "?", "icon": "new", "condition": ""})
        cells = []
        for v in variants:
            x = next((y for y in res["results"] if y["variant"] == v and y["persona"] == r["persona"]), None)
            if x:
                extra = f'{x["n_steps"]} steps' + (f' · {x["dead_clicks"]} dead taps' if x["dead_clicks"] else "")
                cells.append(f'<td>{stamp(x["status"])}<span class="small">{extra}</span></td>')
            else:
                cells.append("<td></td>")
        rows.append(f'<tr><td><div class="who">{avatar(person, av)}<span>{_esc(person.get("first") or person["name"])}</span>'
                    f'</div></td><td>{cond(person)}</td>{"".join(cells)}</tr>')
    return (f'<table class="matrix"><tr><th class="label">Person</th><th class="label">Condition</th>{head}</tr>'
            f'{"".join(rows)}</table>')


def _friction(res: dict) -> str:
    """Dead taps and steps, before -> after: the improvement when the pass count alone doesn't show it."""
    if len(res["variants"]) < 2:
        return ""
    tot = {v: (sum(r["dead_clicks"] for r in res["results"] if r["variant"] == v),
               sum(r["n_steps"] for r in res["results"] if r["variant"] == v)) for v in res["variants"]}
    (d0, s0), (d1, s1) = tot["before"], tot["after"]
    if d0 == d1 and s0 == s1:
        return ""
    return (f'<div class="fr"><span>Dead taps <b>{d0} → {d1}</b></span><span>Total steps <b>{s0} → {s1}</b></span></div>')


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
    for n, f in enumerate(res["findings"], 1):
        sev = f.get("severity") if f.get("severity") in SEV else "major"
        tags = "".join(f"<span>{_esc(w)}</span>" for w in f.get("who", []))
        ev = "".join(f"<li>{_esc(e)}</li>" for e in _as_list(f.get("evidence")))
        fixes = "".join(f"<li>{_esc(x)}</li>" for x in _as_list(f.get("fix")))
        what = f'<p class="what">{_esc(f["what"])}</p>' if f.get("what") else ""
        out.append(f'<div class="find {sev}"><div class="fh"><span class="id">F-{n:02d}</span><span class="sev">{SEV[sev]}</span>'
                   f'<h3>{_esc(f["title"])}</h3><div class="tags">{tags}</div></div>'
                   f'<div class="fb"><div class="prob">{what}' + (f'<div class="label">What happened</div><ul>{ev}</ul>' if ev else "")
                   + f'</div><div class="fixbox"><div class="label">Fix</div><ol>{fixes}</ol></div></div></div>')
    return "".join(out)


def _glance(res: dict) -> str:
    items = res.get("summary") or []
    if not items:
        return ""
    return ('<div class="glance"><div class="label">At a glance</div><ul>'
            + "".join(f"<li>{_esc(s)}</li>" for s in items) + "</ul></div>")


def build_html(res: dict, personas: dict, shots: Path, viewport=(420, 860)) -> str:
    img, av, people = Images(shots), {}, _people(res)
    vw, vh = viewport
    desk = vw > vh
    host = urlparse(res["url"]).netloc or res["url"]
    cols = []
    for v in res["variants"]:
        cards = "".join(_subject(r, people.get(r["persona"], {"id": r["persona"], "name": r["persona"], "initials": "?",
                                                               "icon": "new", "condition": "", "blurb": ""}),
                                 img, desk, vw, vh, av) for r in _order(res, v))
        head = "" if len(res["variants"]) == 1 else f'<div class="colh">{"Before" if v == "before" else "After changes"}</div>'
        cols.append(f"<div>{head}{cards}</div>")
    before = [r for r in _order(res, "before") if r.get("first_shot")]
    heat = ""
    if before:
        first = img(before[0]["first_shot"])
        dots = "".join(f'<i style="left:{x / vw * 100:.1f}%;top:{y / vh * 100:.1f}%">{_esc(people.get(r["persona"], {}).get("initials", "?"))}</i>'
                       for r in before for x, y in r["first_screen_clicks"] if 0 <= y <= vh)
        heat = (f'<div><h2>First screen · taps</h2><div class="heat"><div class="im {"desk " if desk else ""}{first}"></div>{dots}</div>'
                f'<div class="note">Each mark is one tap, labelled with the person’s initial.</div></div>')
    when = time.strftime("%d %b %Y · %H:%M", time.localtime(res.get("finished", time.time())))
    body = f"""<div class="wrap"><div class="top"><span class="brand">HALLWAY<b>/</b>TEST</span>
<span class="label">Session {_esc(res.get('id', ''))}</span><span class="label">{when}</span></div>
<h1>{_esc(res.get('title') or host)}</h1>
<div class="task"><div class="label">Task</div><p>{_esc(res['task'])}</p></div>
<div class="meta">{_esc(res['url'])} · {len(res['personas_order'])} people · real browsers · limits enforced in code</div>
<div class="score">{_nums(res)}{_matrix(res, people, av)}</div>{_glance(res)}
<div class="cols"><div><h2>What got in the way</h2>{_findings(res)}</div>{heat}</div>
<h2>Sessions</h2><div class="grid2 {'two' if len(cols) > 1 else ''}">{''.join(cols)}</div>
<div class="foot">Generated by Hallway Test for Hermes Agent. Perception (text size, contrast, colour vision, screen-reader
access) and abilities (mouse, keyboard, tremor) are enforced by code; the model only decides what each person does next.
Simulated people are not a substitute for testing with real users.</div></div>"""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            f'<title>Hallway Test · {_esc(host)}</title><style>{CSS}</style><style id="ht-img">{img.css()}</style></head>'
            f'<body>{body}</body></html>')


CARD_CSS = BASE_CSS + """
body{margin:0;width:1200px;height:675px;overflow:hidden;background:var(--paper);color:var(--ink);font:15px/1.4 var(--sans)}
.c{display:grid;grid-template-columns:540px 1fr;height:675px}
.l{padding:40px 40px 34px 48px;display:flex;flex-direction:column;border-right:1.5px solid var(--ink)}
.brand{font:800 14px var(--mono);letter-spacing:.14em} .brand b{color:var(--blue)}
h1{font:800 40px/1.02 var(--sans);letter-spacing:-.035em;margin:22px 0 14px}
.task{font:13.5px/1.5 var(--mono);color:var(--ink2);border-left:3px solid var(--blue);padding-left:12px}
.l .sb{margin-top:auto} .nums{display:flex;align-items:flex-end;gap:16px}
.num .n{font:800 110px/.88 var(--sans);letter-spacing:-.055em} .num .n small{font-size:46px;color:var(--ink3)}
.num .label{margin-top:10px} .arrow{font:300 56px/1 var(--sans);color:var(--ink3);padding-bottom:26px}
.fr{display:flex;gap:18px;margin-top:14px;font:13px var(--mono);color:var(--ink2)} .fr b{color:var(--ink)}
.r{padding:34px 40px 30px 34px;display:flex;flex-direction:column;justify-content:center;gap:10px}
.p{display:grid;grid-template-columns:56px 1fr auto;gap:14px;align-items:center;background:var(--card);border:1px solid var(--rule);padding:10px 12px 10px 10px}
.p .nm{font:800 17px/1.1 var(--sans);letter-spacing:-.02em;margin-bottom:6px}
.p .q{font:13px/1.35 var(--sans);color:var(--ink2);margin-top:6px;display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden}
.res{display:flex;align-items:center;gap:6px} .res .to{font:300 18px var(--sans);color:var(--ink3)}
.fx{margin-top:26px;display:grid;gap:8px} .fx div{font:600 14.5px/1.35 var(--sans);display:grid;grid-template-columns:86px 1fr;gap:10px}
.fx span{font:700 10.5px/1.9 var(--mono);letter-spacing:.08em;text-transform:uppercase}
.fx .blocker span{color:var(--fail)} .fx .major span{color:var(--warn)} .fx .minor span{color:var(--ink3)}
.foot{font:11px var(--mono);color:var(--ink3);letter-spacing:.06em;text-transform:uppercase;margin-top:14px}
"""


def _top_findings(res: dict) -> str:
    items = [f for f in res.get("findings", []) if f.get("severity") in ("blocker", "major")][:2]
    if not items:
        return ""
    return '<div class="fx">' + "".join(f'<div class="{f["severity"]}"><span>{SEV[f["severity"]]}</span>{_esc(f["title"])}</div>'
                                        for f in items) + "</div>"


def build_card(res: dict, personas: dict) -> str:
    host = urlparse(res["url"]).netloc or res["url"]
    people, av = _people(res), {}
    rows = []
    for r in _order(res, "before")[:5]:
        person = people.get(r["persona"], {"id": r["persona"], "name": r["persona"], "first": r["persona"], "initials": "?",
                                           "icon": "new", "condition": ""})
        after = next((a for a in res["results"] if a["variant"] == "after" and a["persona"] == r["persona"]), None)
        res_html = stamp(r["status"]) if not after else f'{stamp(r["status"])}<span class="to">→</span>{stamp(after["status"])}'
        q = f'<div class="q">“{_esc(r["quote"])}”</div>' if r.get("quote") and not after else ""
        rows.append(f'<div class="p">{avatar(person, av)}<div><div class="nm">{_esc(person.get("first") or person["name"])}</div>'
                    f'{cond(person)}{q}</div><div class="res">{res_html}</div></div>')
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{CARD_CSS}</style></head><body><div class="c"><div class="l">'
            f'<div class="brand">HALLWAY<b>/</b>TEST</div><h1>{_esc(res.get("title") or host)}</h1>'
            f'<div class="task">{_esc(res["task"])}</div>{_top_findings(res)}{_nums(res)}'
            f'<div class="foot">Simulated people · real browsers · limits enforced in code</div></div>'
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
