"""Self-checks for the planner-polish batch: #67, #68, #69, #70, #71, #73.

Runnable without a framework:  uv run python tests/test_polish_67_73.py

Covers the surfaces a screenshot can't: link tap-rects tracking re-anchored
text (#67/#69), the --no-year index fallback target (#71/#73), and the dot
colour resolver/emission (#68).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lxml import etree

from src import svgutil as SU
from src.config import Config, PALETTE, resolve_color
from src.dates import a_cat, build_pages
from src.fill import _index_link, _text_approx_bbox, fill_page, ACCENT, INK, SUNDAY
from src.background import DOT_COLOR, prepare_background

TPL = Path(__file__).resolve().parent.parent / "assets" / "templates" / "rm2"


def _fill(cfg, kind):
    pages, anchors = build_pages(cfg)
    page = next(p for p in pages if p.kind == kind)
    svg, links = fill_page(page, cfg, anchors, TPL)
    return etree.fromstring(svg.encode()), links, anchors


def _x(node):
    return float(node.find(SU.S + "tspan").get("x"))


def _text(node):
    return node.find(SU.S + "tspan").text or ""


# --- #67 / #69: anchor-aware link geometry (the invisible merge-blocker) --------

def test_text_approx_bbox_is_anchor_aware():
    """`x` is the left edge only for start-anchored text; middle/end shift it."""
    def mk(anchor):
        return etree.fromstring(
            f'<text xmlns="http://www.w3.org/2000/svg" font-size="16" '
            f'text-anchor="{anchor}"><tspan x="100" y="50">W27</tspan></text>'.encode())
    w = max(len("W27") * 0.60 * 16, 16 * 1.5)          # 28.8
    assert abs(_text_approx_bbox(mk("start"))[0] - 100) < 0.01
    assert abs(_text_approx_bbox(mk("middle"))[0] - (100 - w / 2)) < 0.01
    assert abs(_text_approx_bbox(mk("end"))[0] - (100 - w)) < 0.01


def test_month_weeknum_centered_and_link_tracks_it():
    """#67: weeknums middle-anchored in their column, link rect centred on glyphs."""
    root, _, _ = _fill(Config(start_y=2026, start_m=7, months=1), "month")
    node = SU.id_map(root)["mrow-1-weeknum"]
    assert node.get("text-anchor") == "middle"
    cx = _x(node)
    assert 150 < cx < 160, cx                          # column centre ≈ 155
    bx, _, bw, _ = _text_approx_bbox(node)
    assert abs((bx + bw / 2) - cx) < 0.01              # tap-rect centred on the text


def test_day_mini_columns_uniform():
    """#69: single- and double-digit dates in a column share one centred x."""
    root, _, _ = _fill(Config(start_y=2026, start_m=7, months=1), "day")
    idm = SU.id_map(root)
    xs = []
    for r in (1, 2, 3, 4, 5):                           # col W (c3): 1, 8, 15, 22, 29
        n = idm[f"day-mini-r{r}c3"]
        assert n.get("text-anchor") == "middle"
        xs.append(round(_x(n), 2))
    assert len(set(xs)) == 1, xs                        # no single-vs-double drift


# --- #70: Sunday no longer emphasised (month grid + day mini-cal) ---------------

def test_sunday_not_emphasised():
    cfg = Config(start_y=2026, start_m=7, months=1)
    idm = SU.id_map(_fill(cfg, "month")[0])
    assert idm["mcell-r1c7-num"].get("fill").lower() == INK.lower()   # Sun (Jul 5)
    assert idm["mcell-r1c3-num"].get("fill").lower() == INK.lower()   # Wed (Jul 1)
    idm2 = SU.id_map(_fill(cfg, "day")[0])
    assert idm2["day-mini-r1c7"].get("fill").lower() == INK.lower()   # Sun, not today
    assert SUNDAY != INK                                              # the constant still differs


# --- #71 / #73: index/year-overview fallback when no year page ------------------

def test_index_link_helper():
    am = (2026, 7)
    cat = a_cat(2026, 7, 1, 1)
    assert _index_link({"year", cat}, am) == ("year", None)          # year wins
    assert _index_link({cat}, am) == (cat, "↳ sections")             # fall back to sections
    assert _index_link(set(), am) == (None, "")                     # nothing → blank
    assert _index_link(set(), None) == (None, "")


def _noyear(**kw):
    inc = {"year": False, "block": True, "schedule": True, "days": True}
    return Config(start_y=2026, start_m=7, months=1, include=inc, **kw)


def test_no_year_footer_falls_back_to_sections():
    cat = a_cat(2026, 7, 1, 1)
    for kind in ("month", "category"):
        root, links, anchors = _fill(_noyear(), kind)
        assert "year" not in anchors
        assert "year" not in [t for *_, t in links]                 # no dead link anywhere
        assert SU.id_map(root)["footer-right"].find(SU.S + "tspan").text == "↳ sections"
        assert cat in [t for *_, t in links]


def test_year_present_keeps_year_target():
    _, links, anchors = _fill(Config(start_y=2026, start_m=7, months=1), "month")
    assert "year" in anchors and "year" in [t for *_, t in links]


def test_no_year_no_sections_blanks_footer():
    root, links, _ = _fill(_noyear(pages_per_category=0), "month")
    assert _text(SU.id_map(root)["footer-right"]) == ""             # dead label removed
    assert "year" not in [t for *_, t in links]


# --- #68: dot-grid colour ------------------------------------------------------

def test_resolve_color():
    assert resolve_color("grid-border") == "#808080"
    assert resolve_color("Grid-Border") == "#808080"                # case-insensitive
    assert resolve_color("#12AbCd") == "#12abcd"                    # explicit hex ok
    assert set(PALETTE) >= {"grid-border", "grid-primary", "grid-subtle", "base"}
    for bad in ("chartreuse", "#fff", "123456"):
        try:
            resolve_color(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{bad!r} should be rejected")


def test_default_darker_and_color_reaches_svg():
    assert DOT_COLOR == "#808080"                                   # default = Grid/Border (#68)
    tree = SU.parse(str(TPL / "02-month.svg"))
    prepare_background(tree, "02-month", 1.0, "#4d4d4d")
    s = SU.tostring(tree)
    assert 'fill="#4d4d4d"' in s and 'fill="#b8b8b8"' not in s


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("✓ planner-polish (#67/#68/#69/#70/#71/#73) self-check passed")
