"""Self-contained HTML report (replays included) and a 1200x675 summary card PNG."""
from __future__ import annotations

import base64
import hashlib
import html
import time
from pathlib import Path
from urllib.parse import urlparse

STATUS = {"success": ("Finished", "ok"), "gave_up": ("Gave up", "bad"), "false_done": ("Thought they finished", "warn"),
          "out_of_steps": ("Still stuck", "bad"), "error": ("Run error", "err")}
HUES = {"first_timer": "#b4532a", "low_vision": "#7c5a2e", "keyboard": "#2f5d62", "colourblind": "#6b4c8a", "shaky": "#8a3b4f"}
SEV = {"blocker": "Blocker", "major": "Major", "minor": "Minor"}

CSS = """
*{box-sizing:border-box} body{margin:0;background:#f5f1ea;color:#2b231d;font:15px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:36px 32px 60px}
.kicker{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#9a7b62;font-weight:600}
h1{font:600 34px/1.15 Georgia,"Times New Roman",serif;margin:6px 0 8px;letter-spacing:-.01em}
.task{font:italic 18px/1.4 Georgia,serif;color:#5b4a3d;margin:0 0 6px}
.meta{font-size:13px;color:#8d7a6a}
.score{display:flex;gap:18px;align-items:stretch;margin:26px 0 30px;flex-wrap:wrap}
.big{background:#fffdf9;border:1px solid #e6dccf;border-radius:18px;padding:18px 24px;min-width:220px}
.big .n{font:600 54px/1 Georgia,serif} .big .n small{font-size:26px;color:#9a8878}
.big .l{font-size:13px;color:#8d7a6a;margin-top:6px} .arrow{align-self:center;font-size:28px;color:#b39b86}
.dots{display:flex;gap:6px;margin-top:10px} .dot{width:14px;height:14px;border-radius:50%;background:#e6dccf}
.dot.ok{background:#3f7d4e} .dot.bad{background:#c0532d} .dot.warn{background:#d39b2a}
h2{font:600 22px Georgia,serif;margin:34px 0 14px}
.find{display:grid;grid-template-columns:34px 1fr;gap:4px 14px;background:#fffdf9;border:1px solid #e6dccf;border-radius:16px;padding:16px 18px;margin-bottom:10px}
.find .num{font:600 24px Georgia,serif;color:#b39b86} .find h3{margin:0;font-size:16px}
.chip{display:inline-block;font-size:11px;font-weight:600;padding:2px 8px;border-radius:99px;margin-right:6px;vertical-align:2px}
.blocker{background:#fbe1d6;color:#9b3412} .major{background:#fbedd0;color:#8a5a0b} .minor{background:#e9e4dc;color:#6b5b4d}
.who{background:#efe6da;color:#5b4a3d;font-weight:500}
.ev{color:#5b4a3d;font-size:14px;margin-top:4px} .fix{font-size:14px;margin-top:6px} .fix b{color:#3f7d4e}
.cols{display:grid;gap:18px} .cols.two{grid-template-columns:1fr 1fr}
.colh{font-size:13px;font-weight:600;color:#8d7a6a;text-transform:uppercase;letter-spacing:.1em;margin-bottom:10px}
.card{background:#fffdf9;border:1px solid #e6dccf;border-radius:18px;padding:16px 18px;margin-bottom:14px;border-left-width:5px}
.card.ok{border-left-color:#3f7d4e} .card.bad{border-left-color:#c0532d} .card.warn{border-left-color:#d39b2a} .card.err{border-left-color:#9a8878}
.hd{display:flex;gap:12px;align-items:center} .av{width:42px;height:42px;border-radius:50%;color:#fff;display:flex;align-items:center;justify-content:center;font:600 15px Georgia,serif;flex:none}
.nm{font-weight:600} .bl{font-size:12.5px;color:#8d7a6a;line-height:1.35}
.badge{margin-left:auto;font-size:12px;font-weight:600;padding:4px 11px;border-radius:99px;white-space:nowrap}
.ok .badge{background:#dcefdc;color:#2e6b3c} .bad .badge{background:#fbe1d6;color:#9b3412} .warn .badge{background:#fbedd0;color:#8a5a0b} .err .badge{background:#e9e4dc;color:#6b5b4d}
blockquote{margin:12px 0 6px;font:17px/1.4 Georgia,serif;color:#3a2c22} blockquote:before{content:"\\201C";color:#c9b29c} blockquote:after{content:"\\201D";color:#c9b29c}
.sum{font-size:13px;color:#7d6b5c}
.film{display:flex;gap:6px;margin-top:10px} .film .im{width:58px;height:118px;border-radius:7px;border:1px solid #e6dccf;background-size:cover;background-position:top}
details{margin-top:10px} summary{cursor:pointer;font-size:13px;font-weight:600;color:#8a5a3c}
.steps{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin-top:10px}
.st{font-size:12px;color:#5b4a3d} .st .im{width:100%;aspect-ratio:420/860;border-radius:8px;border:1px solid #e6dccf;background-size:cover;background-position:top;position:relative}
.st .im.desk{aspect-ratio:1280/800}
.st .tap{position:absolute;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;border:3px solid #e2572b;background:rgba(226,87,43,.25)}
.st .act{font-family:ui-monospace,Consolas,monospace;font-size:11.5px;margin-top:4px;color:#2b231d}
.st .th{font-style:italic;margin-top:2px} .st .dead{color:#c0532d;font-weight:600}
.heat{position:relative;width:300px;border-radius:14px;overflow:hidden;border:1px solid #e6dccf}
.heat .im{width:300px;aspect-ratio:420/860;background-size:cover;background-position:top}
.heat .im.desk{aspect-ratio:1280/800}
.heat i{position:absolute;width:26px;height:26px;margin:-13px 0 0 -13px;border-radius:50%;opacity:.55}
.legend{display:flex;flex-wrap:wrap;gap:8px 14px;font-size:12px;color:#7d6b5c;margin-top:10px} .legend span:before{content:"";display:inline-block;width:10px;height:10px;border-radius:50%;background:var(--c);margin-right:5px}
.side{display:grid;grid-template-columns:1fr 300px;gap:28px;align-items:start}
.foot{margin-top:40px;font-size:12px;color:#9a8878;border-top:1px solid #e6dccf;padding-top:14px}
"""


def _esc(s) -> str:
    return html.escape(str(s or ""))


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


def _card(r: dict, p, img: Images, desk: bool, vw: int, vh: int) -> str:
    label, cls = STATUS[r["status"]]
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
        rows.append(f'<div class="st"><div class="im {"desk " if desk else ""}{img(s.get("shot"))}">{tap}</div>'
                    f'<div class="act">{s["i"] + 1}. {_esc(s["action"])}</div>'
                    + (f'<div class="th">{_esc(s["thought"])}</div>' if s.get("thought") else "") + dead + err + "</div>")
    quote = f"<blockquote>{_esc(r['quote'])}</blockquote>" if r.get("quote") else ""
    return (f'<div class="card {cls}"><div class="hd"><div class="av" style="background:{HUES.get(p.id, "#7c5a2e")}">'
            f'{_esc(p.initials)}</div><div><div class="nm">{_esc(p.name)}</div><div class="bl">{_esc(p.blurb)}</div></div>'
            f'<div class="badge">{label}</div></div>{quote}<div class="sum">{_esc(r.get("summary", ""))}</div>'
            f'<div class="film">{film}</div>'
            + (f'<details><summary>Replay all {len(r["steps"])} steps</summary><div class="steps">{"".join(rows)}</div></details>'
               if rows else "") + "</div>")


def _score_block(res: dict) -> str:
    out = []
    for i, v in enumerate(res["variants"]):
        sc = res["score"][v]
        dots = "".join(f'<span class="dot {STATUS[r["status"]][1]}"></span>'
                       for r in sorted((r for r in res["results"] if r["variant"] == v),
                                       key=lambda r: res["personas_order"].index(r["persona"])))
        label = "people finished the task" if len(res["variants"]) == 1 else (
            "finished · before" if v == "before" else "finished · after changes")
        if i:
            out.append('<div class="arrow">→</div>')
        out.append(f'<div class="big"><div class="n">{sc["passed"]}<small>/{sc["total"]}</small></div>'
                   f'<div class="l">{label}</div><div class="dots">{dots}</div></div>')
    return "".join(out)


def _findings(res: dict) -> str:
    if not res["findings"]:
        return '<p class="meta">No barriers found for these people on this task.</p>'
    out = []
    for n, f in enumerate(res["findings"], 1):
        sev = f.get("severity", "major") if f.get("severity") in SEV else "major"
        who = "".join(f'<span class="chip who">{_esc(w)}</span>' for w in f.get("who", []))
        out.append(f'<div class="find"><div class="num">{n}</div><div><h3><span class="chip {sev}">{SEV[sev]}</span>'
                   f'{_esc(f["title"])}</h3><div style="margin-top:4px">{who}</div><div class="ev">{_esc(f.get("evidence"))}</div>'
                   f'<div class="fix"><b>Fix:</b> {_esc(f.get("fix"))}</div></div></div>')
    return "".join(out)


def build_html(res: dict, personas: dict, shots: Path, viewport=(420, 860)) -> str:
    img = Images(shots)
    vw, vh = viewport
    desk = vw > vh
    host = urlparse(res["url"]).netloc or res["url"]
    cols = []
    for v in res["variants"]:
        cards = "".join(_card(r, personas[r["persona"]], img, desk, vw, vh)
                        for r in sorted((r for r in res["results"] if r["variant"] == v),
                                        key=lambda r: res["personas_order"].index(r["persona"])))
        head = "" if len(res["variants"]) == 1 else f'<div class="colh">{"Before" if v == "before" else "After changes"}</div>'
        cols.append(f"<div>{head}{cards}</div>")
    before = [r for r in res["results"] if r["variant"] == "before" and r.get("first_shot")]
    heat = ""
    if before:
        first = img(before[0]["first_shot"])
        dots = "".join(f'<i style="left:{x / vw * 100:.1f}%;top:{y / vh * 100:.1f}%;background:{HUES.get(r["persona"], "#c0532d")}"></i>'
                       for r in before for x, y in r["first_screen_clicks"] if 0 <= y <= vh)
        legend = "".join(f'<span style="--c:{HUES.get(r["persona"])}">{_esc(personas[r["persona"]].name.split(",")[0])}</span>'
                         for r in before)
        heat = (f'<div><h2 style="margin-top:0">Where people tapped first</h2><div class="heat"><div class="im {"desk " if desk else ""}{first}"></div>'
                f'{dots}</div><div class="legend">{legend}</div></div>')
    when = time.strftime("%d %b %Y, %H:%M", time.localtime(res.get("finished", time.time())))
    body = f"""<div class="wrap"><div class="kicker">Hallway Test · usability report</div>
<h1>{_esc(res.get('title') or host)}</h1><p class="task">“{_esc(res['task'])}”</p>
<div class="meta">{len(res['personas_order'])} people · each in a real browser with their own limits enforced in code · {when} · {_esc(host)}</div>
<div class="score">{_score_block(res)}</div>
<div class="side"><div><h2 style="margin-top:0">What got in the way</h2>{_findings(res)}</div>{heat}</div>
<h2>The people</h2><div class="cols {'two' if len(cols) > 1 else ''}">{''.join(cols)}</div>
<div class="foot">Generated by Hallway Test for Hermes Agent. Perception (text size, contrast, colour vision, screen-reader
access) and abilities (mouse, keyboard, tremor) are enforced by code; the model only decides what each person does next.
Simulated people are not a substitute for testing with real users.</div></div>"""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            f'<title>Hallway Test · {_esc(host)}</title><style>{CSS}{img.css()}</style></head><body>{body}</body></html>')


CARD_CSS = """
*{box-sizing:border-box}body{margin:0;width:1200px;height:675px;background:#f5f1ea;color:#2b231d;font:15px/1.45 ui-sans-serif,system-ui,"Segoe UI",sans-serif;overflow:hidden}
.c{display:grid;grid-template-columns:560px 1fr;height:675px}
.l{padding:48px 40px 40px 52px;display:flex;flex-direction:column}
.k{font-size:13px;letter-spacing:.16em;text-transform:uppercase;color:#9a7b62;font-weight:700}
h1{font:600 34px/1.15 Georgia,serif;margin:10px 0 8px} .t{font:italic 17px/1.4 Georgia,serif;color:#5b4a3d}
.s{display:flex;align-items:center;gap:18px;margin:26px 0 22px} .n{font:600 76px/1 Georgia,serif} .n small{font-size:34px;color:#9a8878}
.a{font-size:30px;color:#b39b86} .sl{font-size:13px;color:#8d7a6a;margin-top:4px}
.f{font-size:14.5px;margin:0 0 9px;display:flex;gap:10px} .f b{font:600 15px Georgia,serif;color:#b39b86}
.chip{font-size:10.5px;font-weight:700;padding:2px 7px;border-radius:99px;margin-right:6px;vertical-align:1px}
.blocker{background:#fbe1d6;color:#9b3412}.major{background:#fbedd0;color:#8a5a0b}.minor{background:#e9e4dc;color:#6b5b4d}
.r{background:#ece4d8;padding:30px 30px 30px 26px;display:flex;flex-direction:column;gap:10px;justify-content:center}
.p{display:grid;grid-template-columns:46px 1fr;gap:12px;background:#fffdf9;border-radius:16px;padding:12px 14px;border-left:5px solid}
.p.ok{border-color:#3f7d4e}.p.bad{border-color:#c0532d}.p.warn{border-color:#d39b2a}.p.err{border-color:#9a8878}
.av{width:46px;height:46px;border-radius:50%;color:#fff;display:flex;align-items:center;justify-content:center;font:600 16px Georgia,serif}
.nm{font-weight:600;font-size:14px}.st{font-size:11.5px;font-weight:700;margin-left:6px}.ok .st{color:#2e6b3c}.bad .st{color:#9b3412}.warn .st{color:#8a5a0b}
.q{font:italic 14px/1.35 Georgia,serif;color:#4a3a2e;margin-top:2px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.ft{margin-top:auto;font-size:12px;color:#9a8878}
.ar{color:#b39b86;margin:0 2px 0 6px;font-size:12px}.okx{color:#2e6b3c!important}.badx{color:#9b3412!important}.warnx{color:#8a5a0b!important}.errx{color:#6b5b4d!important}
"""


def build_card(res: dict, personas: dict) -> str:
    host = urlparse(res["url"]).netloc or res["url"]
    sc = res["score"]
    score = f'<div><div class="n">{sc["before"]["passed"]}<small>/{sc["before"]["total"]}</small></div><div class="sl">{"before" if "after" in sc else "finished the task"}</div></div>'
    if "after" in sc:
        score += (f'<div class="a">→</div><div><div class="n">{sc["after"]["passed"]}<small>/{sc["after"]["total"]}</small></div>'
                  f'<div class="sl">after changes</div></div>')
    finds = "".join(f'<div class="f"><b>{i}</b><div><span class="chip {f.get("severity", "major")}">{SEV.get(f.get("severity"), "Major")}</span>'
                    f'{_esc(f["title"])}</div></div>' for i, f in enumerate(res["findings"][:3], 1))
    rows = []
    for r in sorted((r for r in res["results"] if r["variant"] == "before"), key=lambda r: res["personas_order"].index(r["persona"])):
        p = personas[r["persona"]]
        label, cls = STATUS[r["status"]]
        after = next((a for a in res["results"] if a["variant"] == "after" and a["persona"] == r["persona"]), None)
        arrow = ""
        if after:
            al, ac = STATUS[after["status"]]
            arrow = f'<span class="ar">→</span><span class="st {ac}x">{al}</span>'
        rows.append(f'<div class="p {cls}"><div class="av" style="background:{HUES.get(p.id)}">{_esc(p.initials)}</div><div>'
                    f'<div class="nm">{_esc(p.name)}<span class="st">{label}</span>{arrow}</div>'
                    f'<div class="q">{"“" + _esc(r["quote"]) + "”" if r.get("quote") else _esc(r.get("summary"))}</div></div></div>')
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{CARD_CSS}</style></head><body><div class="c"><div class="l">'
            f'<div class="k">Hallway Test</div><h1>{_esc(res.get("title") or host)}</h1><div class="t">“{_esc(res["task"])}”</div>'
            f'<div class="s">{score}</div>{finds}<div class="ft">Simulated people with enforced limits · Hermes Agent plugin</div>'
            f'</div><div class="r">{"".join(rows)}</div></div></body></html>')


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
