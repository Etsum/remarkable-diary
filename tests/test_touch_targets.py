"""Self-check for #41 (link tap targets grown to a minimum size).

Runnable without a framework:  uv run python tests/test_touch_targets.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.render import MIN_TOUCH, W, H, _inflate, _page_div


def test_inflate_grows_small_link_centred():
    """A thin text link grows to MIN_TOUCH on both axes, keeping its centre."""
    x, y, w, h = 100.0, 100.0, 20.0, 20.0
    x2, y2, w2, h2, tgt = _inflate(x, y, w, h, "day-2026-07-15")
    assert (w2, h2) == (MIN_TOUCH, MIN_TOUCH)
    assert x2 + w2 / 2 == x + w / 2 and y2 + h2 / 2 == y + h / 2   # centre unchanged
    assert tgt == "day-2026-07-15"


def test_inflate_leaves_large_link_untouched():
    """A rail tab (66×98) already exceeds MIN_TOUCH — passes through unchanged."""
    assert _inflate(100.0, 100.0, 66.0, 98.0, "year") == (100.0, 100.0, 66.0, 98.0, "year")


def test_inflate_only_one_small_axis():
    """Footer text (92×20): wide enough already, only the height grows."""
    x2, y2, w2, h2, _ = _inflate(132.0, 1818.3, 92.4, 19.6, "year")
    assert w2 == 92.4 and h2 == MIN_TOUCH


def test_inflate_clamps_to_page_bounds():
    """Links near an edge grow inward, never off-page."""
    for x, y, w, h in [(0.0, 0.0, 10.0, 10.0), (W - 10.0, H - 10.0, 10.0, 10.0)]:
        x2, y2, w2, h2, _ = _inflate(x, y, w, h, "t")
        assert 0 <= x2 and x2 + w2 <= W
        assert 0 <= y2 and y2 + h2 <= H


def test_page_div_emits_inflated_target():
    """The load-bearing check: emitted <a> rects are actually the inflated size.

    Fails if _inflate is ever un-wired from _page_div (the real regression risk) —
    a passing _inflate unit test wouldn't catch that.
    """
    small = (300.0, 400.0, 22.0, 20.0, "day-2026-07-15")     # mini-cal-cell sized
    out = _page_div("anchor", "<svg/>", [small])
    assert f"width:{MIN_TOUCH:.2f}px" in out, out
    assert f"height:{MIN_TOUCH:.2f}px" in out, out


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("✓ touch-target self-check passed")
