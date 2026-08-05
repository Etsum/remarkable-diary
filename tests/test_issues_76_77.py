"""Self-checks for #76 (day-page WEEK → week-block link) and #77 (skip weekend day pages).

Runnable without a framework:  uv run python tests/test_issues_76_77.py

Covers the surfaces a screenshot can't: the new WEEK meta link target + its
tap-rect (and the disjoint date→year zone), the block→schedule fallback, and the
page-model / anchor / inbound-link consequences of dropping weekend day pages.
"""
from __future__ import annotations

import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lxml import etree

from src import svgutil as SU
from src.config import Config, load_config
from src.dates import a_day, a_week, build_pages, dim, is_weekend, week_existing
from src.fill import _idm_bbox, fill_page

TPL = Path(__file__).resolve().parent.parent / "assets" / "templates" / "rm2"


def _day_pages(pages):
    return [p for p in pages if p.kind == "day"]


def _first_day(cfg):
    """Build, fill the first day page, return (page, root, links, anchors)."""
    pages, anchors = build_pages(cfg)
    page = next(p for p in pages if p.kind == "day")
    svg, links = fill_page(page, cfg, anchors, TPL)
    return page, etree.fromstring(svg.encode()), links, anchors


def _rects_for(links, target):
    return [l for l in links if l[4] == target]


def _matches(link, bb) -> bool:
    return bb is not None and all(abs(a - b) < 1e-6 for a, b in zip(link[:4], bb))


# ============================ #76: day-page WEEK link ========================

def test_week_meta_links_to_block_page():
    """The 'WEEK <n>' meta text links to that week's block page, on the WEEK rect."""
    cfg = Config(start_y=2026, start_m=7, months=1)          # block + schedule both on
    page, root, links, anchors = _first_day(cfg)
    monday = page.day - timedelta(days=page.day.weekday())
    block = a_week(monday, "b")
    assert block in anchors

    block_links = _rects_for(links, block)
    assert len(block_links) == 1, block_links               # exactly one WEEK → block link
    idm = SU.id_map(root)
    week_bb = _idm_bbox(idm, "hdr-meta-top", "hdr-meta-bottom")
    assert _matches(block_links[0], week_bb), (block_links[0], week_bb)


def test_date_meta_links_to_year_and_zones_disjoint():
    """The date text keeps a year 'zoom out'; its rect never overlaps the WEEK rect."""
    cfg = Config(start_y=2026, start_m=7, months=1)
    page, root, links, anchors = _first_day(cfg)
    monday = page.day - timedelta(days=page.day.weekday())
    idm = SU.id_map(root)

    date_bb = _idm_bbox(idm, "hdr-big", "hdr-big-label", "hdr-month-name")
    week_bb = _idm_bbox(idm, "hdr-meta-top", "hdr-meta-bottom")

    # the datebox year link is the one whose rect matches the date text (the rail
    # index chip also targets 'year', so match by geometry rather than target alone)
    date_year = [l for l in _rects_for(links, "year") if _matches(l, date_bb)]
    week_block = _rects_for(links, a_week(monday, "b"))
    assert len(date_year) == 1 and len(week_block) == 1

    yx, _, yw, _ = date_year[0][:4]
    wx, _, _, _ = week_block[0][:4]
    assert yx + yw <= wx, (date_year[0], week_block[0])     # date on the left, WEEK on the right


def test_week_meta_falls_back_to_schedule_without_block():
    """With --no-block the WEEK meta link degrades to the schedule page (#76 fallback)."""
    inc = {"year": True, "block": False, "schedule": True, "days": True}
    cfg = Config(start_y=2026, start_m=7, months=1, include=inc)
    page, root, links, anchors = _first_day(cfg)
    monday = page.day - timedelta(days=page.day.weekday())
    assert a_week(monday, "b") not in anchors and a_week(monday, "s") in anchors

    idm = SU.id_map(root)
    week_bb = _idm_bbox(idm, "hdr-meta-top", "hdr-meta-bottom")
    meta_links = [l for l in links if _matches(l, week_bb)]
    assert len(meta_links) == 1
    assert meta_links[0][4] == a_week(monday, "s")          # points at the schedule page


def test_no_dead_week_links_across_full_year():
    """Every day page's WEEK meta link resolves to its week-block anchor (#76).

    Sweeps a full 12-month span so partial first weeks and ISO year-boundary weeks
    are covered — the exact cases where a naive Monday→block lookup could dangle.
    """
    cfg = Config(start_y=2026, start_m=7, months=12)
    pages, anchors = build_pages(cfg)
    day_pages = [p for p in pages if p.kind == "day"]
    assert len(day_pages) == 365
    for p in day_pages:
        monday = p.day - timedelta(days=p.day.weekday())
        tgt = week_existing(anchors, monday, "block")   # exactly what _fill_day resolves
        assert tgt == a_week(monday, "b") and tgt in anchors, (p.day, tgt)


def test_week_meta_absent_when_no_week_pages():
    """No block/schedule pages → no WEEK link (and no crash); the year link survives."""
    inc = {"year": True, "block": False, "schedule": False, "days": True}
    cfg = Config(start_y=2026, start_m=7, months=1, include=inc)
    page, root, links, _ = _first_day(cfg)
    idm = SU.id_map(root)

    week_bb = _idm_bbox(idm, "hdr-meta-top", "hdr-meta-bottom")
    assert [l for l in links if _matches(l, week_bb)] == []  # nothing to link to

    date_bb = _idm_bbox(idm, "hdr-big", "hdr-big-label", "hdr-month-name")
    assert any(_matches(l, date_bb) and l[4] == "year" for l in links)


# ============================ #77: skip weekend day pages ====================

def test_default_keeps_weekend_day_pages():
    cfg = Config(start_y=2026, start_m=7, months=1)
    assert cfg.skip_weekends is False
    days = {p.day for p in _day_pages(build_pages(cfg)[0])}
    assert any(is_weekend(d) for d in days)                 # weekends present by default


def test_skip_weekends_drops_only_sat_sun():
    y, m = 2026, 7
    pages, anchors = build_pages(Config(start_y=y, start_m=m, months=1, skip_weekends=True))
    days = {p.day for p in _day_pages(pages)}
    expected = {date(y, m, dd) for dd in range(1, dim(y, m) + 1)
                if not is_weekend(date(y, m, dd))}
    assert days == expected                                 # exactly the weekdays
    assert not any(is_weekend(d) for d in days)
    # weekday anchors exist, weekend anchors do not
    assert all(a_day(d) in anchors for d in expected)
    assert all(a_day(date(y, m, dd)) not in anchors
               for dd in range(1, dim(y, m) + 1) if is_weekend(date(y, m, dd)))


def test_skip_weekends_leaves_non_day_pages_identical():
    base, _ = build_pages(Config(start_y=2026, start_m=7, months=3))
    skip, _ = build_pages(Config(start_y=2026, start_m=7, months=3, skip_weekends=True))

    def non_day(ps):
        return Counter(p.kind for p in ps if p.kind != "day")

    assert non_day(base) == non_day(skip)                   # only day pages change
    dropped = len(_day_pages(base)) - len(_day_pages(skip))
    assert dropped == sum(1 for p in _day_pages(base) if is_weekend(p.day))
    assert dropped > 0


def test_skip_weekends_inbound_links_degrade_gracefully():
    """Month grid keeps rendering weekend numbers but no longer links them (#77)."""
    y, m = 2026, 7
    cfg = Config(start_y=y, start_m=m, months=1, skip_weekends=True)
    pages, anchors = build_pages(cfg)
    month = next(p for p in pages if p.kind == "month")
    _, links = fill_page(month, cfg, anchors, TPL)
    targets = {t for *_, t in links}

    weekend_anchors = {a_day(date(y, m, dd)) for dd in range(1, dim(y, m) + 1)
                       if is_weekend(date(y, m, dd))}
    weekday_anchors = {a_day(date(y, m, dd)) for dd in range(1, dim(y, m) + 1)
                       if not is_weekend(date(y, m, dd))}
    assert weekend_anchors.isdisjoint(targets)              # no dead weekend links
    assert weekday_anchors & targets                        # weekday cells still link


def test_skip_weekends_config_json_roundtrip():
    assert load_config({"start": "2026-07", "months": 1, "skipWeekends": True}).skip_weekends is True
    assert load_config({"start": "2026-07", "months": 1}).skip_weekends is False


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("✓ issues #76 / #77 self-check passed")
