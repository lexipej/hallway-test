"""Small line icons (24x24, currentColor) for each person's condition and for pass/fail marks."""

_SVG = '<svg viewBox="0 0 24 24" width="{s}" height="{s}" fill="none" stroke="currentColor" stroke-width="1.8" ' \
       'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{body}</svg>'

ICONS = {
    # first visit: a compass
    "new": '<circle cx="12" cy="12" r="9"/><path d="M15.6 8.4l-2.1 5.1-5.1 2.1 2.1-5.1z"/>',
    # low vision: reading glasses
    "low_vision": '<circle cx="7" cy="14.5" r="3.6"/><circle cx="17" cy="14.5" r="3.6"/>'
                  '<path d="M10.6 14.2c.9-.6 1.9-.6 2.8 0M3.4 14 5.2 7.5M20.6 14 18.8 7.5"/>',
    # screen reader: headphones
    "screen_reader": '<path d="M4 15.5V12a8 8 0 0 1 16 0v3.5"/><rect x="3" y="14" width="4.2" height="6.5" rx="1.6"/>'
                     '<rect x="16.8" y="14" width="4.2" height="6.5" rx="1.6"/>',
    # keyboard only
    "keyboard": '<rect x="2.5" y="6" width="19" height="12" rx="2"/><path d="M6.5 10h.01M10.5 10h.01M14.5 10h.01'
                'M18 10h.01M7.5 14h9"/>',
    # colour blind: a half-filled disc
    "colour": '<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 0 0 18z" fill="currentColor" stroke="none"/>',
    # tremor: a target with an off-centre tap
    "tremor": '<circle cx="11" cy="13" r="7.5"/><circle cx="11" cy="13" r="2.6"/>'
              '<circle cx="18.2" cy="5.8" r="1.7" fill="currentColor" stroke="none"/><path d="M15.6 3.6l.9-.9M20.4 8.4l.9-.9"/>',
    "check": '<path d="M5 12.5l4.2 4.2L19 7"/>',
    "cross": '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
    "alert": '<path d="M12 4 2.8 19.5h18.4z"/><path d="M12 10v4.2M12 17h.01"/>',
    "tap": '<circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3"/>',
}


def icon(name: str, size: int = 16) -> str:
    return _SVG.format(s=size, body=ICONS.get(name, ICONS["new"]))
