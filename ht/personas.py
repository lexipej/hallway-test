"""Personas: what each one can perceive and what each one can do.

The limits are enforced by code (perceive.py and act.py), not by asking the model to pretend.
The model only ever sees a persona's filtered view and can only use that persona's actions.
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
    tags: tuple = field(default_factory=tuple)


PERSONAS: dict[str, Persona] = {
    "first_timer": Persona(
        "first_timer", "Mara, first-time visitor",
        "Has never used this site. Reads labels literally and won't hunt for hidden controls.",
        temperament="Busy and a little impatient; if something is unclear she guesses once, then moves on.",
        initials="M", tags=("new user",)),
    "low_vision": Persona(
        "low_vision", "Lolo Ben, 72, low vision",
        "Uses the default zoom. Small or faint text is unreadable to him.",
        min_font_px=13.5, min_contrast=3.0, css_filter="blur(1.4px) contrast(0.85)",
        temperament="Patient but easily discouraged; he won't press things he can't read more than twice.",
        initials="LB", tags=("low vision", "older adult")),
    "keyboard": Persona(
        "keyboard", "Jo, screen-reader user",
        "Blind. Moves with Tab, Shift+Tab, Enter, Space and arrow keys and hears what the screen reader announces.",
        mouse=False, a11y_tree_only=True,
        temperament="Experienced and methodical; tabs through the whole page before concluding something is missing.",
        initials="J", tags=("blind", "keyboard only")),
    "colourblind": Persona(
        "colourblind", "Rafael, red-green colour blind",
        "Deuteranopia: reds and greens look the same muddy brown to him.",
        colour_vision="deuteranopia", css_filter="url(#ht-deut)",
        temperament="Confident with apps; relies on text, not colour.",
        initials="R", tags=("colour blind",)),
    "shaky": Persona(
        "shaky", "Aling Nena, hand tremor",
        "Her taps land up to 9 pixels away from where she aims.",
        tremor_px=9,
        temperament="Careful; if a tap does the wrong thing she notices and tries again.",
        initials="AN", tags=("motor",)),
}

DEFAULT_PERSONAS = list(PERSONAS)


def pick(ids: list[str] | None) -> list[Persona]:
    if not ids:
        return [PERSONAS[i] for i in DEFAULT_PERSONAS]
    out = []
    for i in ids:
        key = str(i).strip().lower().replace("-", "_").replace(" ", "_")
        if key not in PERSONAS:
            raise ValueError(f"unknown persona {i!r}; choose from {', '.join(PERSONAS)}")
        out.append(PERSONAS[key])
    return out
