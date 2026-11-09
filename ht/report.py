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

GRAIN = ("url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='180' height='180'>"
         "<filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/>"
         "<feColorMatrix values='0 0 0 0 .12 0 0 0 0 .17 0 0 0 0 .9 0 0 0 .045 0'/></filter>"
         "<rect width='100%' height='100%' filter='url(%23n)'/></svg>\")")

BASE_CSS = """
:root{--blue:#1e2ce6;--navy:#171a3d;--ink2:#4b4f72;--ink3:#8a8daa;--pink:#ff4f9a;--pink-soft:#ffe3ef;--yellow:#ffd23f;
--paper:#f6f7f9;--rule:#d9dbec;--tint:#e9ebff;
--head:"Barlow Condensed","Bahnschrift","Arial Narrow",sans-serif;--mono:"Space Mono","Cascadia Mono",Consolas,monospace;
--sans:"Inter","Segoe UI Variable Text","Segoe UI","Helvetica Neue",Arial,sans-serif}
*{box-sizing:border-box}
.label{font:700 11px/1 var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--ink3)}
.st{display:inline-flex;align-items:center;gap:5px;font:700 12px/1 var(--mono);letter-spacing:.04em;text-transform:uppercase;
  padding:5px 8px 4px;border:2px solid currentColor;white-space:nowrap;transform:rotate(-1.2deg)}
.st.pass{color:var(--blue)} .st.fail{color:var(--pink);background:var(--pink-soft)} .st.warn{color:#a77a00;background:#fff4c9}
.st.muted{color:var(--ink3)}
.cond{display:inline-flex;align-items:center;gap:5px;font:700 11px/1.2 var(--mono);letter-spacing:.03em;text-transform:uppercase;color:var(--blue)}
.av{width:44px;height:44px;flex:none;background:var(--blue);color:#fff;display:flex;align-items:center;justify-content:center;
  overflow:hidden;box-shadow:3px 3px 0 var(--pink)}
.av img{width:100%;height:100%;object-fit:cover;display:block}
.av .ini{font:800 20px var(--head)}
.dots{background-image:radial-gradient(var(--blue) 28%,transparent 31%);background-size:7px 7px}
"""

CSS = BASE_CSS + """
body{margin:0;background:var(--paper) """ + GRAIN + """;color:var(--navy);font:15px/1.6 var(--sans)}
.mast{border-bottom:3px solid var(--blue)}
.mast .bar{display:flex;gap:16px;max-width:1000px;margin:0 auto;padding:18px 32px;font:700 12px var(--mono);color:var(--blue);
  letter-spacing:.06em;text-transform:uppercase}
.mast .bar .when{margin-left:auto}
.mast .pic{height:250px;overflow:hidden}
.mast img{display:block;width:100%;height:100%;object-fit:cover;object-position:50% 30%;mix-blend-mode:multiply}
.wrap{max-width:1000px;margin:0 auto;padding:0 32px 80px}
.kick{display:inline-block;margin-top:34px;font:700 12px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:#fff;
  background:var(--blue);padding:5px 9px 4px}
h1{font:800 64px/.95 var(--head);letter-spacing:-.01em;text-transform:uppercase;color:var(--blue);margin:14px 0 14px;max-width:900px}
.task{margin:0;font-size:18px;color:var(--navy);max-width:760px}
.meta{margin-top:10px;font:12px var(--mono);color:var(--ink3)}
.hero{display:grid;grid-template-columns:auto 1fr;gap:56px;align-items:center;margin:48px 0 8px}
.nums{display:flex;align-items:flex-end;gap:14px}
.num .n{font:800 120px/.82 var(--head);color:var(--blue);text-shadow:4px 3px 0 rgba(255,79,154,.85)}
.num .n small{font-size:52px;color:var(--ink3);text-shadow:none}
.num .label{margin-top:12px} .arrow{font:700 54px/1 var(--head);color:var(--pink);padding-bottom:30px}
.fr{margin-top:16px;font:12px var(--mono);color:var(--ink2)} .fr b{color:var(--blue)}
.glance{margin:0;padding:0;list-style:none;font-size:17px;line-height:1.45}
.glance li{padding:7px 0 7px 22px;position:relative} .glance li:before{content:"";position:absolute;left:0;top:15px;width:10px;height:10px;background:var(--pink)}
h2{display:flex;align-items:center;gap:14px;font:800 28px/1 var(--head);text-transform:uppercase;color:var(--blue);margin:70px 0 18px}
h2:after{content:"";flex:1;height:10px;background-image:radial-gradient(var(--blue) 28%,transparent 31%);background-size:7px 7px;opacity:.55}
table.res{border-collapse:collapse;width:100%}
.res th{text-align:left;font:700 11px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--ink3);padding:0 0 10px}
.res td{padding:14px 16px 14px 0;border-top:1.5px dashed var(--rule);vertical-align:middle}
.who{display:flex;align-items:center;gap:14px} .who b{font:800 21px/1 var(--head);text-transform:uppercase;letter-spacing:.01em}
.sub{display:block;font:11.5px var(--mono);color:var(--ink3);margin-top:6px}
.find{display:grid;grid-template-columns:70px 1fr;padding:26px 0;border-top:1.5px dashed var(--rule);max-width:820px}
.fnum{font:800 46px/.9 var(--head);color:var(--blue);text-shadow:3px 2px 0 rgba(255,79,154,.8)}
.fmeta{display:flex;align-items:center;gap:10px;font:700 11.5px var(--mono);text-transform:uppercase;letter-spacing:.04em;color:var(--ink3)}
.mark{padding:3px 7px 2px;color:var(--navy)} .blocker .mark{background:var(--pink);color:#fff} .major .mark{background:var(--yellow)}
.minor .mark{border:1.5px solid var(--ink3);color:var(--ink2)}
.find h3{margin:10px 0 6px;font:800 26px/1.05 var(--head);text-transform:uppercase;color:var(--navy)}
.what{margin:0 0 8px;font-size:15.5px}
.ev{margin:0 0 14px;padding-left:18px;color:var(--ink2);font-size:14px} .ev li{margin:2px 0}
.fix{position:relative;background:var(--tint);padding:14px 18px 14px;overflow:hidden}
.fix:after{content:"";position:absolute;right:-10px;top:-10px;width:140px;height:90px;background-image:radial-gradient(var(--blue) 28%,transparent 31%);
  background-size:7px 7px;opacity:.35;-webkit-mask-image:linear-gradient(225deg,#000,transparent 70%);mask-image:linear-gradient(225deg,#000,transparent 70%)}
.fix .label{color:var(--blue);font-size:12px} .fix ol{position:relative;margin:8px 0 0;padding-left:20px;font-size:14.5px;color:var(--navy)} .fix li{margin:3px 0}
.people{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:22px}
.subj{background:#fff;padding:18px;border:2px solid var(--navy);box-shadow:5px 5px 0 var(--blue)}
.subj .hd{display:flex;gap:14px;align-items:center} .subj .av{width:64px;height:64px}
.subj .nm{font:800 26px/1 var(--head);text-transform:uppercase;margin-bottom:6px} .subj .hd .st{margin-left:auto}
.quote{position:relative;margin:16px 0 0;padding-left:26px;font:500 16px/1.45 var(--sans)}
.quote:before{content:"“";position:absolute;left:0;top:-14px;font:800 48px/1 var(--head);color:var(--pink)}
.sum{margin-top:8px;font:11.5px var(--mono);color:var(--ink3)}
.film{display:flex;gap:6px;margin-top:14px}
.film .im{width:52px;height:106px;background-size:cover;background-position:top;border:1.5px solid var(--navy)}
details{margin-top:12px} summary{cursor:pointer;font:700 12px var(--mono);letter-spacing:.04em;text-transform:uppercase;color:var(--blue)}
.steps{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:12px;margin-top:12px}
.st2{font-size:12.5px;color:var(--ink2)} .st2 .im{width:100%;aspect-ratio:420/860;background-size:cover;background-position:top;border:1.5px solid var(--navy);position:relative}
.st2 .im.desk{aspect-ratio:1280/800}
.st2 .tap{position:absolute;width:18px;height:18px;margin:-9px 0 0 -9px;border:2.5px solid var(--pink);border-radius:50%;background:rgba(255,79,154,.2)}
.st2 .act{font:700 11px var(--mono);color:var(--navy);margin-top:6px} .st2 .th{margin-top:2px}
.st2 .dead{font:700 11px var(--mono);color:var(--pink);margin-top:3px}
.aft summary{font-size:13px}
.appx{margin-top:56px;padding-top:18px;border-top:1.5px dashed var(--rule)}
.heat{position:relative;width:280px;margin-top:14px;border:2px solid var(--navy)}
.heat .im{width:100%;aspect-ratio:420/860;background-size:cover;background-position:top} .heat .im.desk{aspect-ratio:1280/800}
.heat i{position:absolute;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;background:var(--pink);color:#fff;
  font:700 10px/22px var(--mono);text-align:center;font-style:normal;box-shadow:0 0 0 2px #fff}
.note{font-size:13px;color:var(--ink3)}
.foot{margin-top:56px;font:12px/1.6 var(--mono);color:var(--ink3);max-width:760px}
"""


def fonts_css() -> str:
    """The two print typefaces (SIL OFL), embedded so the report looks the same on every machine."""
    out = []
    for fam, file, weight in (("Barlow Condensed", "barlow-condensed-latin-700-normal", 700),
                              ("Barlow Condensed", "barlow-condensed-latin-800-normal", 800),
                              ("Space Mono", "space-mono-latin-400-normal", 400), ("Space Mono", "space-mono-latin-700-normal", 700)):
        p = ASSETS / "fonts" / f"{file}.woff2"
        if p.exists():
            out.append(f"@font-face{{font-family:'{fam}';font-weight:{weight};font-style:normal;font-display:block;"
                       f"src:url(data:font/woff2;base64,{base64.b64encode(p.read_bytes()).decode()}) format('woff2')}}")
    return "".join(out)


def _asset_b64(name: str, mime: str) -> str:
    p = ASSETS / name
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


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
    quote = f'<p class="quote">{_esc(r["quote"])}</p>' if r.get("quote") else ""
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
    for n, f in enumerate(res["findings"], 1):
        sev = f.get("severity") if f.get("severity") in SEV else "major"
        who = ", ".join(_esc(w) for w in f.get("who", []))
        ev = "".join(f"<li>{_esc(e)}</li>" for e in _as_list(f.get("evidence")))
        fixes = "".join(f"<li>{_esc(x)}</li>" for x in _as_list(f.get("fix")))
        out.append(f'<article class="find {sev}"><div class="fnum">{n:02d}</div><div><div class="fmeta"><span class="mark">{SEV[sev]}</span>'
                   + (f'<span>{who}</span>' if who else "") + f'</div><h3>{_esc(f["title"])}</h3>'
                   + (f'<p class="what">{_esc(f["what"])}</p>' if f.get("what") else "")
                   + (f'<ul class="ev">{ev}</ul>' if ev else "")
                   + (f'<div class="fix"><div class="label">The fix</div><ol>{fixes}</ol></div>' if fixes else "") + "</div></article>")
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
    group = _asset_b64("group.jpg", "image/jpeg")
    mast = (f'<header class="mast"><div class="bar"><span>Hallway / Test</span><span>{_esc(host)}</span>'
            f'<span class="when">{when}</span></div>' + (f'<div class="pic"><img src="{group}" alt=""></div>' if group else "")
            + "</header>")
    body = f"""{mast}<div class="wrap"><span class="kick">Usability session report</span>
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
            f'<title>Hallway Test · {_esc(host)}</title><style>{fonts_css()}{CSS}</style><style id="ht-img">{img.css()}</style></head>'
            f'<body>{body}</body></html>')


CARD_CSS = BASE_CSS + """
body{margin:0;width:1200px;height:675px;overflow:hidden;background:var(--paper) """ + GRAIN + """;color:var(--navy);font:15px/1.4 var(--sans)}
.c{position:relative;display:grid;grid-template-columns:560px 1fr;height:675px}
.c:before{content:"";position:absolute;right:-40px;top:-40px;width:420px;height:300px;background-image:radial-gradient(var(--blue) 28%,transparent 31%);
  background-size:8px 8px;opacity:.22;-webkit-mask-image:radial-gradient(closest-side,#000,transparent);mask-image:radial-gradient(closest-side,#000,transparent)}
.l{position:relative;padding:48px 44px 44px 56px;display:flex;flex-direction:column;border-right:2px dashed var(--rule)}
.brand{display:inline-block;align-self:flex-start;font:700 13px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:#fff;background:var(--blue);padding:6px 10px 5px}
h1{font:800 60px/.92 var(--head);text-transform:uppercase;color:var(--blue);margin:22px 0 14px}
.task{font-size:17px;line-height:1.45;color:var(--navy)}
.sb{margin-top:auto} .nums{display:flex;align-items:flex-end;gap:16px}
.num .n{font:800 150px/.8 var(--head);color:var(--blue);text-shadow:5px 4px 0 rgba(255,79,154,.85)}
.num .n small{font-size:62px;color:var(--ink3);text-shadow:none}
.num .label{margin-top:14px} .arrow{font:700 64px/1 var(--head);color:var(--pink);padding-bottom:36px}
.fr{margin-top:14px;font:13px var(--mono);color:var(--ink2)} .fr b{color:var(--blue)}
.r{position:relative;padding:44px 52px 40px 32px;display:flex;flex-direction:column;justify-content:center;gap:16px}
.p{display:grid;grid-template-columns:72px 1fr auto;gap:18px;align-items:center}
.p .av{width:72px;height:72px;box-shadow:4px 4px 0 var(--pink)}
.p .nm{font:800 30px/1 var(--head);text-transform:uppercase;margin-bottom:6px}
.res2{display:flex;align-items:center;gap:8px} .res2 .to{font:700 20px var(--head);color:var(--pink)}
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
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{fonts_css()}{CARD_CSS}</style></head><body><div class="c"><div class="l">'
            f'<div class="brand">Hallway / Test</div><h1>{_esc(res.get("title") or host)}</h1>'
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
