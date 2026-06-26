"""Dot-grid writing texture (PIPELINE_SPEC §10, decision D9).

`prepare_background(tree)` injects a `<defs>` of dot patterns and fills each
writable zone with a `<rect fill="url(#dotNN)">`, inserted as the first children
of `#background` so the dots sit *under* every rule / label / shading / date
(document order: page-bg ▸ [our dots] ▸ rest of #background ▸ #var-ink).
Weekend shading is opacity-0.3, so dots show through it.

Zone geometry is derived from the named frames (so the grid follows any Figma
nudge); only small structural constants (header heights, the week-block date
divider) are documented inline. Mini-calendars get no dots.

GH issue #6.
"""
from __future__ import annotations

from lxml import etree

from . import svgutil as SU

S = SU.S
DOT_COLOR = "#c7c4be"

# pattern id -> (tile size, translate offset)  — densities from the original HTML (§10)
_PATTERNS = {
    "dot30": (30, 16),
    "dot26": (26, 8),
    "dot24": (24, 10),
    "dot23": (23, 8),
    "dot22": (22, 11),
}

# structural constants (px), documented:
_BOX_HEADER_H = 34       # wb-box-*-header-bg height (sand title bar)
_WB_DATE_DIV_X = 180     # week-block navy vertical rule: date column | writing band
_WS_HEADER_H = 40        # week-schedule day-header row (day# + weekday) height
_DAY_NOTES_TITLE_H = 42  # day-page "NOTES" title band height
_INSET = 1               # keep dots inside frame strokes


def _make_defs(scale: float = 1.0) -> etree._Element:
    defs = etree.Element(S + "defs", {"id": "dotgrid-defs"})
    for pid, (size, off) in _PATTERNS.items():
        s = max(4, round(size * scale))
        o = max(1, round(off * scale))
        pat = etree.SubElement(defs, S + "pattern", {
            "id": pid, "width": str(s), "height": str(s),
            "patternUnits": "userSpaceOnUse",
            "patternTransform": f"translate({o} {o})",
        })
        etree.SubElement(pat, S + "circle", {
            "cx": "1.1", "cy": "1.1", "r": "1.1", "fill": DOT_COLOR,
        })
    return defs


def detect_stem(tree) -> str:
    root = tree.getroot() if isinstance(tree, etree._ElementTree) else tree
    stems = {"01-year", "02-month", "03-week-block",
             "04-week-schedule", "05-day", "06-category"}
    for g in root.iter(S + "g"):
        if g.get("id") in stems:
            return g.get("id")
    raise ValueError("could not detect master stem from root group id")


def _zones(stem: str, idm: dict) -> list[tuple[float, float, float, float, str]]:
    """List of (x, y, w, h, pattern_id) writable zones for this master."""
    Z: list[tuple] = []

    def frame_inset(node_id, pat, l=_INSET, t=_INSET, r=_INSET, b=_INSET):
        x, y, w, h = SU.bbox(idm[node_id])
        Z.append((x + l, y + t, w - l - r, h - t - b, pat))

    if stem == "01-year":
        return Z  # mini-calendars only — no writing dots

    if stem == "02-month":
        # grid body == the vertical-rules group bbox (week-number column excluded)
        frame_inset("month-vertical-rules", "dot24")

    elif stem == "03-week-block":
        # writing band: from the navy date-divider to the band's right edge
        x, y, w, h = SU.bbox(idm["wb-left"])
        Z.append((_WB_DATE_DIV_X + 1, y + 1,
                  (x + w) - (_WB_DATE_DIV_X + 1) - 1, h - 2, "dot23"))
        # right-hand boxes: body below each sand header bar
        for name in ("carryover", "projects", "tasks", "discuss"):
            bx, by, bw, bh = SU.bbox(idm[f"wb-box-{name}"])
            Z.append((bx + 1, by + _BOX_HEADER_H + 1,
                      bw - 2, bh - _BOX_HEADER_H - 2, "dot23"))

    elif stem == "04-week-schedule":
        x, y, w, h = SU.bbox(idm["week-schedule-grid"])
        top = y + _WS_HEADER_H  # below the day-header row
        Z.append((x + 1, top, w - 2, (y + h) - top - 1, "dot22"))

    elif stem == "05-day":
        frame_inset("day-schedule-frame", "dot30")
        nx, ny, nw, nh = SU.bbox(idm["day-notes-frame"])
        top = ny + _DAY_NOTES_TITLE_H  # below the "NOTES" title
        Z.append((nx + 1, top, nw - 2, (ny + nh) - top - 1, "dot26"))

    elif stem == "06-category":
        frame_inset("cat-grid-frame", "dot30")

    return Z


def prepare_background(tree, stem: str | None = None, scale: float = 1.0) -> None:
    """Mutate `tree` in place: add dot-pattern defs + patterned rects to #background.

    Idempotent: skips if dot-grid already applied."""
    root = tree.getroot() if isinstance(tree, etree._ElementTree) else tree
    if root.find(".//" + S + "defs[@id='dotgrid-defs']") is not None:
        return
    stem = stem or detect_stem(tree)
    idm = SU.id_map(tree)

    root.insert(0, _make_defs(scale))

    bg = idm["background"]
    zones = _zones(stem, idm)
    # insert at the front of #background, preserving zone order
    for i, (x, y, w, h, pat) in enumerate(zones):
        if w <= 0 or h <= 0:
            continue
        rect = etree.Element(S + "rect", {
            "x": f"{x:.2f}", "y": f"{y:.2f}",
            "width": f"{w:.2f}", "height": f"{h:.2f}",
            "fill": f"url(#{pat})",
        })
        bg.insert(i, rect)
