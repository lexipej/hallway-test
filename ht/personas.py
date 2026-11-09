"""Personas: what each one can perceive and what each one can do.

The limits are enforced by code (browser.py), not by asking the model to pretend. The model only ever
sees a persona's filtered view and can only use that persona's actions. Custom personas combine the
same enforced limits with a name and a description.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Persona:
    id: str
    name: str
    blurb: str
    mouse: bool = True              # False: keyboard only
    tremor_px: int = 0              # random click offset in CSS pixels
    min_font_px: float = 0          # text smaller than this is unreadable
    min_contrast: float = 1.1       # text below this contrast ratio is unreadable
    colour_vision: str = "normal"   # normal | deuteranopia
    a11y_tree_only: bool = False    # perceives only what a screen reader announces
    css_filter: str = ""            # how this persona's screenshots are rendered
    temperament: str = ""           # extra role-play guidance (patience, habits)
    initials: str = ""
    icon: str = "new"               # condition icon key (see icons.py)
    condition: str = ""             # short label shown with the icon
    tags: tuple = field(default_factory=tuple)

    @property
    def first_name(self) -> str:
        return self.name.split(",")[0].strip()


PERSONAS: dict[str, Persona] = {
    "first_timer": Persona(
        "first_timer", "Maya, first-time visitor",
        "Has never used this site. Reads labels literally and won't hunt for hidden controls.",
        temperament="Busy and a little impatient; if something is unclear she guesses once, then moves on.",
        initials="M", icon="new", condition="First visit", tags=("new user",)),
    "low_vision": Persona(
        "low_vision", "Walter, 72, low vision",
        "Uses the default zoom. Text under 13.5px or with weak contrast is unreadable to him.",
        min_font_px=13.5, min_contrast=3.0, css_filter="blur(1.4px) contrast(0.85)",
        temperament="Patient but easily discouraged; he won't press things he can't read more than twice.",
        initials="W", icon="low_vision", condition="Low vision", tags=("low vision", "older adult")),
    "keyboard": Persona(
        "keyboard", "Jordan, screen-reader user",
        "Blind. Moves with Tab, arrow keys, Enter and Space, and hears only what the screen reader announces.",
        mouse=False, a11y_tree_only=True,
        temperament="Experienced and methodical; explores the whole page before concluding something is missing.",
        initials="J", icon="screen_reader", condition="Screen reader", tags=("blind", "keyboard only")),
    "colourblind": Persona(
        "colourblind", "Ryan, red-green colour blind",
        "Deuteranopia: reds and greens look the same muddy brown to him.",
        colour_vision="deuteranopia", css_filter="url(#ht-deut)",
        temperament="Confident with apps; relies on text and symbols, not colour.",
        initials="R", icon="colour", condition="Colour blind", tags=("colour blind",)),
    "shaky": Persona(
        "shaky", "Nina, hand tremor",
        "Her taps land up to 9 pixels away from where she aims.",
        tremor_px=9,
        temperament="Careful; if a tap does the wrong thing she notices and tries again.",
        initials="N", icon="tremor", condition="Hand tremor", tags=("motor",)),
}

DEFAULT_PERSONAS = list(PERSONAS)

# Building blocks for custom personas: each one is a limit the code enforces.
TRAITS = {
    "low_vision": dict(min_font_px=13.5, min_contrast=3.0, css_filter="blur(1.4px) contrast(0.85)"),
    "screen_reader": dict(mouse=False, a11y_tree_only=True),
    "keyboard_only": dict(mouse=False),
    "colour_blind": dict(colour_vision="deuteranopia", css_filter="url(#ht-deut)"),
    "tremor": dict(tremor_px=9),
}
TRAIT_ICON = {"screen_reader": "screen_reader", "keyboard_only": "keyboard", "low_vision": "low_vision",
              "colour_blind": "colour", "tremor": "tremor"}
TRAIT_LABEL = {"screen_reader": "Screen reader", "keyboard_only": "Keyboard only", "low_vision": "Low vision",
               "colour_blind": "Colour blind", "tremor": "Hand tremor"}


def custom(spec: dict, index: int) -> Persona:
    """Build a persona from {name, about, traits: [...], text_size_px?, tremor_px?}."""
    name = str(spec.get("name") or f"Guest {index + 1}").strip()[:60]
    about = str(spec.get("about") or "").strip()[:240]
    traits = [str(t).strip().lower().replace(" ", "_").replace("-", "_") for t in (spec.get("traits") or [])]
    bad = [t for t in traits if t not in TRAITS]
    if bad:
        raise ValueError(f"unknown trait(s) {', '.join(bad)}; choose from {', '.join(TRAITS)}")
    fields: dict = {}
    for t in traits:
        fields.update(TRAITS[t])
    if "screen_reader" in traits and "low_vision" in traits:
        fields.pop("css_filter", None)
    if spec.get("text_size_px"):
        fields["min_font_px"] = float(spec["text_size_px"])
        fields.setdefault("min_contrast", 3.0)
    if spec.get("tremor_px"):
        fields["tremor_px"] = max(1, min(int(spec["tremor_px"]), 30))
    first = name.split(",")[0].split()[0] if name.split() else name
    blurbs = {"low_vision": "small or faint text is unreadable", "screen_reader": "hears only what a screen reader announces",
              "keyboard_only": "uses only the keyboard", "colour_blind": "can't tell red from green",
              "tremor": "taps land off target"}
    blurb = about or ("; ".join(blurbs[t] for t in traits).capitalize() + "." if traits else "No extra limits.")
    pid = "custom_" + "".join(c for c in first.lower() if c.isalnum())[:20] + f"_{index}"
    main = traits[0] if traits else ""
    return Persona(pid, name, blurb, initials=first[:1].upper(), icon=TRAIT_ICON.get(main, "new"),
                   condition=" + ".join(TRAIT_LABEL[t] for t in traits) or "Custom", tags=tuple(traits),
                   temperament=about, **fields)


def pick(ids: list[str] | None, customs: list[dict] | None = None) -> list[Persona]:
    """The chosen built-in people (all five by default) plus any custom ones."""
    out = []
    for i in (ids or DEFAULT_PERSONAS):
        key = str(i).strip().lower().replace("-", "_").replace(" ", "_")
        if key not in PERSONAS:
            raise ValueError(f"unknown persona {i!r}; choose from {', '.join(PERSONAS)}")
        out.append(PERSONAS[key])
    for n, spec in enumerate(customs or []):
        if not isinstance(spec, dict):
            raise ValueError("each custom persona must be an object with name, about and traits")
        out.append(custom(spec, n))
    if len(out) > 8:
        raise ValueError("at most 8 people per run")
    return out
