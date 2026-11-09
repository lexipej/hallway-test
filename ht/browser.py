"""Perception and action, enforced per persona.

``observe`` turns the live page into the text this persona can perceive. ``act`` executes one
action, refusing anything the persona can't do. Nothing here calls a model.
"""
from __future__ import annotations

import hashlib
import random
import re
from typing import Any

PROBE_JS = r"""
() => {
  const parse = (c) => { const m = (c || '').match(/[\d.]+/g); return m ? m.map(Number) : null; };
  const lum = (c) => { const m = parse(c); if (!m) return null; const [r,g,b,a] = m;
    if (a !== undefined && a < 0.1) return null;
    const f = v => { v/=255; return v<=0.03928? v/12.92 : Math.pow((v+0.055)/1.055,2.4); };
    return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b); };
  const bgOf = (el) => { for (let e = el; e; e = e.parentElement) {
      const L = lum(getComputedStyle(e).backgroundColor); if (L !== null) return L; } return 1; };
  const hue = (c) => { const m = parse(c); if (!m) return ''; const [r,g,b] = m;
    if (r > 170 && g < 120 && b < 120) return 'red'; if (g > 140 && r < 130 && b < 150) return 'green'; return ''; };
  const vw = innerWidth, vh = innerHeight;
  const interactive = new Set(['BUTTON','A','INPUT','SELECT','TEXTAREA','SUMMARY']);
  const roles = new Set(['button','link','checkbox','radio','tab','menuitem','option','switch','combobox','textbox']);
  document.querySelectorAll('[data-ht]').forEach(e => e.removeAttribute('data-ht'));
  const out = []; let n = 0, below = 0;
  for (const el of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    const tag = el.tagName;
    if (['SCRIPT','STYLE','NOSCRIPT','svg','path'].includes(tag)) continue;
    const own = [...el.childNodes].filter(c => c.nodeType === 3).map(c => c.textContent.trim()).join(' ').trim();
    const role = el.getAttribute('role') || '';
    // A <label> is text that focuses its field; keyboard users reach the field itself, so it is not a control.
    const clickable = tag !== 'LABEL' && (interactive.has(tag) || roles.has(role) || cs.cursor === 'pointer' || el.hasAttribute('onclick'));
    const isImg = tag === 'IMG';
    if (!own && !clickable && !isImg) continue;
    if (clickable && !interactive.has(tag) && el.parentElement && el.parentElement.closest('button,a,[role=button]')) continue;
    if (!clickable && el.closest('button,a,[role=button],label,summary')) {
      // text inside a control is reported with the control
      if (!el.closest('label')) continue;
    }
    if (r.bottom < 0 || r.top > vh || r.right < 0 || r.left > vw) { if (r.top > vh) below++; continue; }
    el.setAttribute('data-ht', ++n);
    let text = clickable ? (el.innerText || el.value || '').trim().replace(/\s+/g, ' ') : own;
    // Accessible name the way assistive tech builds it for icon controls: aria-label, aria-labelledby,
    // title, then the alt / <title> of a picture inside the control.
    const lb = el.getAttribute('aria-labelledby');
    const lbText = lb ? lb.split(/\s+/).map(i => (document.getElementById(i) || {}).textContent || '').join(' ').trim() : '';
    const inner = clickable ? el.querySelector('img[alt]:not([alt=""]), svg title, [aria-label]') : null;
    const innerName = inner ? (inner.getAttribute('alt') || inner.getAttribute('aria-label') || inner.textContent || '') : '';
    const aria = (el.getAttribute('aria-label') || lbText || el.getAttribute('title') || innerName || '').trim();
    // A clickable wrapper around a real link or button is not itself a keyboard trap.
    const wraps = clickable && !interactive.has(tag) &&
      !!el.querySelector('a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])');
    // Links inside a sentence are exempt from target-size rules (WCAG 2.5.8).
    const inSentence = tag === 'A' && cs.display === 'inline' && el.parentElement &&
      (el.parentElement.innerText || '').trim().length > (el.innerText || '').trim().length + 15;
    let alt = isImg ? (el.getAttribute('alt') || '') : '';
    const graphic = el.querySelector && el.querySelector('svg,img');
    let fontEl = el;
    if (clickable) {  // measure the text people actually read, not the wrapper
      let best = null;
      for (const d of [el, ...el.querySelectorAll('*')]) {
        if ([...d.childNodes].some(c => c.nodeType === 3 && c.textContent.trim())) {
          const fs = parseFloat(getComputedStyle(d).fontSize);
          if (!best || fs > best.fs) best = { d, fs };
        }
      }
      if (best) fontEl = best.d;
    }
    const fcs = fontEl === el ? cs : getComputedStyle(fontEl);
    const L1 = lum(fcs.color) ?? 0, L2 = bgOf(fontEl);
    const contrast = (Math.max(L1,L2)+0.05)/(Math.min(L1,L2)+0.05);
    let label = '';
    if (['INPUT','SELECT','TEXTAREA'].includes(tag)) {
      label = (el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`)?.innerText) ||
              el.closest('label')?.innerText || aria || el.getAttribute('placeholder') || '';
    }
    const sel = el.getAttribute('aria-pressed') === 'true' || el.getAttribute('aria-selected') === 'true' ||
                el.getAttribute('aria-checked') === 'true' || el.checked === true ||
                /(^|\s)(sel|selected|active|is-active|checked)(\s|$)/.test(el.className && el.className.baseVal === undefined ? el.className : '');
    out.push({ ref: n, tag, role, text: text.slice(0, 90), aria, alt, clickable, wraps, inSentence,
      focusable: el.tabIndex >= 0 && !el.disabled, disabled: !!el.disabled || el.getAttribute('aria-disabled') === 'true',
      font: parseFloat(fcs.fontSize), contrast: Math.round(contrast*10)/10,
      border: hue(cs.borderColor), textHue: hue(fcs.color),
      graphic: !!graphic, graphicH: graphic ? Math.round(graphic.getBoundingClientRect().height) : Math.round(r.height),
      isImg, selected: !!sel, label: (label || '').trim().slice(0, 60), type: el.type || '',
      value: (el.value || '').slice(0, 60), options: tag === 'SELECT' ? [...el.options].map(o => o.text).slice(0, 12) : [],
      x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2), w: Math.round(r.width), h: Math.round(r.height) });
    if (n >= 140) break;
  }
  const f = document.activeElement;
  let focus = null;
  if (f && f !== document.body) {
    const name = (f.getAttribute('aria-label') || (f.labels && f.labels[0] && f.labels[0].innerText) ||
                  f.innerText || f.getAttribute('placeholder') || '').trim().replace(/\s+/g,' ').slice(0, 80);
    focus = { tag: f.tagName.toLowerCase(), role: f.getAttribute('role') || '', name, value: (f.value || '').slice(0, 60),
              pressed: f.getAttribute('aria-pressed') || '', ref: f.getAttribute('data-ht') };
  }
  const body = (document.body && document.body.innerText) || '';
  const maxY = Math.max(0, document.documentElement.scrollHeight - innerHeight);
  return { title: document.title, url: location.href, items: out, focus, below, scrollY: Math.round(scrollY),
           scrollPct: maxY ? Math.round(100 * scrollY / maxY) : -1,
           textLen: body.length, text: body.slice(0, 4000) };
}
"""

DEUT_SVG = ('<svg id="ht-svg" aria-hidden="true" style="position:absolute;width:0;height:0"><filter id="ht-deut">'
            '<feColorMatrix type="matrix" values="0.367 0.861 -0.228 0 0  0.280 0.673 0.047 0 0  '
            '-0.012 0.043 0.969 0 0  0 0 0 1 0"/></filter></svg>')

MOUSE_ACTIONS = ("click <ref> | type <ref> <text> | select <ref> <option text> | scroll down | scroll up | "
                 "scroll to top | scroll to bottom | "
                 "done | give_up <reason>")
KEY_ACTIONS = ("press Tab | press Shift+Tab | press Enter | press Space | press ArrowDown | press ArrowUp | "
               "press Escape | press Control+A | type_focused <text> | done | give_up <reason>")
ALLOWED_KEYS = {"Tab", "Shift+Tab", "Enter", "Space", "ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight",
                "Escape", "Control+A", "Backspace", "Home", "End"}


def probe(page) -> dict:
    return page.evaluate(PROBE_JS)


def fingerprint(raw: dict) -> str:
    """Changes when what's on screen changes (used to detect clicks that did nothing)."""
    h = hashlib.sha1()
    h.update(raw.get("url", "").encode())
    h.update(raw.get("text", "").encode())
    for it in raw.get("items", []):
        h.update(f"{it['text']}|{it['value']}|{it['selected']}|{it['border']}|{it['contrast']}".encode())
    return h.hexdigest()[:12]


def layout(raw: dict) -> str:
    """Same page, ignoring selection and typed values (groups taps on the same screen for the heatmap)."""
    h = hashlib.sha1(raw.get("url", "").split("#")[0].encode())
    for it in raw.get("items", []):
        if it["clickable"]:
            h.update(f"{it['tag']}|{it['text'][:20]}|{it['x'] // 20}|{it['y'] // 20}".encode())
    return h.hexdigest()[:12]


def _describe_item(it: dict, p) -> str | None:
    unreadable = bool(it["text"]) and (it["font"] < p.min_font_px or it["contrast"] < p.min_contrast)
    t = "[text too small or faint to read]" if unreadable else it["text"]
    if it["isImg"]:
        t = f"picture: {it['alt']}" if it["alt"] else f"[unlabelled picture, {it['h']}px tall]"
    elif it["clickable"] and not it["text"]:
        name = it["aria"]
        t = f"[{name}]" if name else f"[unlabelled icon, {it['graphicH']}px tall]"
    if it["tag"] in ("INPUT", "TEXTAREA"):
        kind = "checkbox" if it["type"] in ("checkbox", "radio") else "text field"
        lab = it["label"] or "no label"
        t = f"{kind} labelled '{lab}'" + (f" containing '{it['value']}'" if it["value"] and kind == "text field" else
                                          (" (checked)" if it["selected"] else "" if kind == "checkbox" else " (empty)"))
    if it["tag"] == "SELECT":
        t = f"dropdown labelled '{it['label'] or 'no label'}' showing '{it['value']}' (options: {', '.join(it['options'])})"
    cues = []
    if it["selected"] and it["tag"] not in ("INPUT",):
        cues.append("highlighted")
    for what, hue in (("border", it["border"]), ("text", it["textHue"])):
        if hue:
            cues.append(f"{'brownish' if p.colour_vision == 'deuteranopia' else hue} {what}")
    if it["disabled"] or (it["clickable"] and it["contrast"] < 2.2 and not unreadable and it["text"]):
        cues.append("looks greyed out / disabled")
    if not t:
        return None
    kind = "control" if it["clickable"] else "text"
    return f"[{it['ref']}] {kind}: {t}" + (f" ({', '.join(cues)})" if cues else "")


def observe(page, p) -> dict:
    """What THIS persona perceives, as text, plus raw probe data for the executor."""
    raw = probe(page)
    if p.a11y_tree_only:
        try:
            tree = page.locator("body").aria_snapshot()
        except Exception as exc:  # pragma: no cover - depends on page
            tree = f"(screen reader could not read the page: {exc})"
        if len(tree) > 6000:
            tree = tree[:6000] + "\n… (more content)"
        f = raw.get("focus")
        if f:
            role = f["role"] or f["tag"]
            extra = f", value '{f['value']}'" if f["value"] else ""
            extra += f", pressed {f['pressed']}" if f["pressed"] else ""
            focus = f"{role} '{f['name']}'{extra}"
        else:
            focus = "nothing focused (start of page)"
        text = (f"PAGE: {raw['title']}\nSCREEN READER (everything it can announce on this page):\n{tree}\n\n"
                f"KEYBOARD FOCUS IS ON: {focus}")
        return {"text": text, "raw": raw}
    focus_ref = str((raw.get("focus") or {}).get("ref") or "")
    lines = []
    for it in raw["items"]:
        d = _describe_item(it, p)
        if d and focus_ref and str(it["ref"]) == focus_ref and it["tag"] in ("INPUT", "TEXTAREA", "SELECT"):
            d += " (selected, typing cursor is here)"
        if d:
            lines.append(d)
    pct = raw.get("scrollPct", -1)
    if pct < 0:
        where = "\n(the whole page fits on the screen)"
    elif pct <= 2:
        where = "\n(you are at the top of the page; it continues below)"
    elif pct >= 98:
        where = "\n(you are at the bottom of the page)"
    else:
        where = f"\n(you are about {pct}% of the way down the page)"
    more = where
    return {"text": f"PAGE: {raw['title']}\nWHAT YOU SEE:\n" + "\n".join(lines) + more, "raw": raw}


class ActionError(ValueError):
    pass


def act(page, p, obs: dict, action: str, rng: random.Random) -> dict:
    """Execute one action for persona ``p``. Returns {kind, click?, aimed?}; raises ActionError."""
    a = (action or "").strip()
    items = {it["ref"]: it for it in obs["raw"]["items"]}

    def item(ref: str) -> dict:
        try:
            return items[int(ref)]
        except (KeyError, ValueError):
            raise ActionError(f"there is no item [{ref}] on screen")

    if a == "done":
        return {"kind": "done"}
    if a.startswith("give_up"):
        return {"kind": "give_up", "reason": a[len("give_up"):].strip(" :-") or "gave up"}
    if p.mouse:
        if m := re.fullmatch(r"click\s+\[?(\d+)\]?", a):
            it = item(m[1])
            dx = rng.randint(-p.tremor_px, p.tremor_px) if p.tremor_px else 0
            dy = rng.randint(-p.tremor_px, p.tremor_px) if p.tremor_px else 0
            x, y = it["x"] + dx, it["y"] + dy
            page.mouse.click(x, y)
            return {"kind": "click", "click": [x, y], "aimed": [it["x"], it["y"]], "target": it["text"] or it["label"]}
        if m := re.fullmatch(r"type\s+\[?(\d+)\]?\s+(.+)", a, re.S):
            it = item(m[1])
            page.mouse.click(it["x"], it["y"])
            page.keyboard.press("Control+A")
            page.keyboard.type(m[2].strip().strip('"'), delay=8)
            return {"kind": "type", "click": [it["x"], it["y"]], "aimed": [it["x"], it["y"]], "target": it["label"]}
        if m := re.fullmatch(r"select\s+\[?(\d+)\]?\s+(.+)", a, re.S):
            it = item(m[1])
            if it["tag"] != "SELECT":
                raise ActionError(f"[{m[1]}] is not a dropdown")
            page.locator(f'[data-ht="{it["ref"]}"]').select_option(label=m[2].strip().strip('"'))
            return {"kind": "select", "click": [it["x"], it["y"]], "aimed": [it["x"], it["y"]]}
        if a in ("scroll down", "scroll up"):
            page.mouse.wheel(0, 600 if a.endswith("down") else -600)
            return {"kind": "scroll"}
        if a in ("scroll to top", "scroll to bottom"):  # a quick fling, as people do on long pages
            page.evaluate("(down) => window.scrollTo(0, down ? document.documentElement.scrollHeight : 0)",
                          a.endswith("bottom"))
            return {"kind": "scroll"}
        raise ActionError(f"not an action you can take; allowed: {MOUSE_ACTIONS}")
    if m := re.fullmatch(r"press\s+(.+)", a):
        key = m[1].strip()
        if key not in ALLOWED_KEYS:
            raise ActionError(f"key {key!r} not available; allowed: {KEY_ACTIONS}")
        page.keyboard.press(key)
        return {"kind": "key", "key": key}
    if m := re.fullmatch(r"type_focused\s+(.+)", a, re.S):
        page.keyboard.type(m[1].strip().strip('"'), delay=8)
        return {"kind": "type"}
    raise ActionError(f"you can only use the keyboard; allowed: {KEY_ACTIONS}")


def screenshot(page, p, path, quality: int = 55) -> None:
    if p.css_filter:
        page.evaluate("(f) => document.documentElement.style.filter = f", p.css_filter)
    try:
        page.screenshot(path=str(path), type="jpeg", quality=quality)
    finally:
        if p.css_filter:
            page.evaluate("() => document.documentElement.style.filter = ''")


def install_filters(page) -> None:
    page.evaluate("(svg) => { if (!document.getElementById('ht-svg')) document.body.insertAdjacentHTML('beforeend', svg) }",
                  DEUT_SVG)


def audit(raw: dict) -> list[dict]:
    """Deterministic issues on one screen (independent of any persona)."""
    found = []
    for it in raw.get("items", []):
        name = it["text"] or it["aria"] or it["label"] or it["alt"]
        if it["text"] and it["font"] < 12:
            found.append({"kind": "small_text", "text": it["text"], "detail": f"{it['font']:.0f}px"})
        if it["text"] and it["contrast"] < 4.5 and not it["disabled"]:
            found.append({"kind": "low_contrast", "text": it["text"], "detail": f"contrast {it['contrast']}:1"})
        if (it["clickable"] and not it["focusable"] and not it.get("wraps")
                and it["tag"] not in ("INPUT", "SELECT", "TEXTAREA")):
            found.append({"kind": "not_keyboard", "text": name or f"unlabelled {it['tag'].lower()}",
                          "detail": f"<{it['tag'].lower()}> with a click handler but no keyboard focus"})
        if it["clickable"] and not name and not it.get("wraps"):
            found.append({"kind": "no_name", "text": f"icon control at {it['x']},{it['y']}",
                          "detail": "no text or aria-label"})
        if it["isImg"] and not it["alt"]:
            found.append({"kind": "no_alt", "text": f"image at {it['x']},{it['y']}", "detail": "missing alt text"})
        if it["tag"] in ("INPUT", "SELECT", "TEXTAREA") and not it["label"]:
            found.append({"kind": "no_label", "text": f"{it['tag'].lower()} field", "detail": "no label"})
        if (it["clickable"] and (it["w"] < 24 or it["h"] < 24) and it["tag"] != "INPUT"
                and not it.get("inSentence") and not it.get("wraps")):
            found.append({"kind": "small_target", "text": name or "control", "detail": f"{it['w']}x{it['h']}px"})
        if it["border"] == "red" and it["tag"] in ("INPUT", "TEXTAREA"):
            found.append({"kind": "colour_only", "text": it["label"] or "field",
                          "detail": "red border; check the error is also explained in text"})
    return found
