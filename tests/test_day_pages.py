"""Self-check for #47 (configurable day pages per day) + #53 (footer 日).

Runnable without a framework:  uv run python tests/test_day_pages.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import Config
from src.dates import a_day, build_pages


def _day_pages(pages):
    return [p for p in pages if p.kind == "day"]


def test_default_is_unchanged():
    """day_pages_per_day defaults to 1 — behaviour identical to before #47."""
    cfg = Config(start_y=2026, start_m=7, months=1)
    assert cfg.day_pages_per_day == 1
    pages, anchors = build_pages(cfg)
    # every day page owns its anchor when N == 1
    for p in _day_pages(pages):
        assert p.anchor == a_day(p.day)
    return pages, anchors


def test_n_pages_per_day_and_anchor_set_unchanged():
    """N>1: page count grows by (day-count)*(N-1); the ANCHOR SET is unchanged."""
    base_pages, base_anchors = build_pages(Config(start_y=2026, start_m=7, months=1))
    base_days = _day_pages(base_pages)
    n_days = len(base_days)

    for N in (2, 3):
        pages, anchors = build_pages(
            Config(start_y=2026, start_m=7, months=1, day_pages_per_day=N)
        )
        # exactly N pages per calendar day
        per_day = Counter(p.day for p in _day_pages(pages))
        assert set(per_day.values()) == {N}, per_day

        # total page delta is exactly the extra day pages
        assert len(pages) == len(base_pages) + n_days * (N - 1)

        # ── the discriminating check ── the anchor set is byte-identical to N==1,
        # so no inbound link breaks and no extra page owns/steals an anchor.
        assert anchors == base_anchors

        # only the FIRST sub-page of each day owns the day anchor; the rest are None
        owners = Counter(p.anchor for p in _day_pages(pages) if p.anchor)
        assert all(c == 1 for c in owners.values())
        assert sum(1 for p in _day_pages(pages) if p.anchor is None) == n_days * (N - 1)


def test_validation_rejects_zero():
    for bad in (0, -1):
        try:
            Config(start_y=2026, start_m=7, months=1, day_pages_per_day=bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"day_pages_per_day={bad} should be rejected")


if __name__ == "__main__":
    test_default_is_unchanged()
    test_n_pages_per_day_and_anchor_set_unchanged()
    test_validation_rejects_zero()
    print("✓ day-pages / footer self-check passed")
