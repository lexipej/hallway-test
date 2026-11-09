"""Hallway Test backend, mounted at /api/plugins/hallway-test/. Read-only views over finished and live runs."""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()
_ID = re.compile(r"^[0-9]{8}-[0-9]{6}-[0-9a-f]{4}$")


def _runs_dir() -> Path:
    from plugins.plugin_storage import plugin_data_dir
    return plugin_data_dir("hallway-test") / "runs"


def _run(run_id: str) -> Path:
    if not _ID.fullmatch(run_id or ""):
        raise HTTPException(404, "unknown run")
    d = _runs_dir() / run_id
    if not (d / "state.json").exists():
        raise HTTPException(404, "unknown run")
    return d


def _read(p: Path) -> dict:
    for _ in range(3):  # the writer replaces the file atomically; retry a torn read once or twice
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
    return {}


def _b64(p: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


_AVATARS = Path(__file__).resolve().parent.parent / "assets" / "avatars"


@router.get("/avatars")
async def avatars():
    """The built-in people's portraits as data URLs, keyed by persona id."""
    return {p.stem: _b64(p, "image/jpeg") for p in sorted(_AVATARS.glob("*.jpg"))}


@router.get("/runs")
async def runs():
    d = _runs_dir()
    out = []
    for sd in sorted((p for p in d.glob("*") if _ID.fullmatch(p.name)), reverse=True)[:40]:
        s = _read(sd / "state.json")
        if s:
            out.append({k: s.get(k) for k in ("id", "title", "url", "task", "status", "score", "created", "variants")})
    return {"runs": out}


@router.get("/runs/{run_id}")
async def run(run_id: str):
    d = _run(run_id)
    s = _read(d / "state.json")
    people = []
    for key, p in s.get("personas", {}).items():
        shot = p.get("shot")
        people.append({**p, "key": key, "thumb": _b64(d / "shots" / shot, "image/jpeg") if shot else ""})
    s["people_live"] = people
    s.pop("personas", None)
    return s


@router.get("/runs/{run_id}/report")
async def report(run_id: str):
    d = _run(run_id)
    p = d / "report.html"
    if not p.exists():
        raise HTTPException(409, "report not ready")
    html = p.read_text(encoding="utf-8")
    # Chromium refuses data: URLs over 2 MB, and screenshots make a report bigger than that. Ship the page
    # without its screenshot stylesheet and let the Desktop page post the screenshots in after it loads.
    images = "".join(_IMG_RULE.findall(html))
    html = _IMG_RULE.sub("", html).replace('<style id="ht-img"></style>', "").replace("</head>", _RECEIVER + "</head>", 1)
    return {"src": "data:text/html;charset=utf-8;base64," + base64.b64encode(html.encode("utf-8")).decode(),
            "images": images, "card": _b64(d / "card.png", "image/png"), "path": str(p.resolve())}


_IMG_RULE = re.compile(r"\.i[0-9a-f]{10}\{background-image:url\(data:image/jpeg;base64,[A-Za-z0-9+/=]*\)\}")
_RECEIVER = ("<script>addEventListener('message',function(e){var d=e.data;if(d&&d.type==='hallway-images'&&"
             "typeof d.css==='string'&&!document.getElementById('ht-img')){var s=document.createElement('style');"
             "s.id='ht-img';s.textContent=d.css;document.head.appendChild(s);}});</script>")
