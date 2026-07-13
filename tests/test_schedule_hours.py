"""Self-check for configurable week-schedule hours (hourStart + hourIncrement).

Runnable without a framework:  uv run python tests/test_schedule_hours.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lxml import etree

import src.svgutil as SU
from src.config import Config
from src.dates import MASTER, Page, a_week
from src.fill import fill_page

TEMPLATES = Path(__file__).resolve().parent.parent / "assets" / "templates" / "rm2"
_MONDAY = date(2026, 7, 6)


def _hour_labels(cfg: Config) -> list[str]:
    """Fill a week-schedule page and return its ws-hour-pos label texts, in row order."""
    anchor = a_week(_MONDAY, "s")
    page = Page(kind="week-schedule", anchor=anchor, master=MASTER["week-schedule"],
                monday=_MONDAY, month=(2026, 7), active_month=(2026, 7))
    svg, _ = fill_page(page, cfg, {anchor}, TEMPLATES)
    idm = SU.id_map(etree.fromstring(svg.encode()))
    ids = sorted((k for k in idm if k.startswith("ws-hour-pos-")),
                 key=lambda k: int(k.rsplit("-", 1)[1]))
    out = []
    for k in ids:
        ts = idm[k].find(SU.S + "tspan")
        out.append(((ts.text if ts is not None else idm[k].text) or ""))
    return out


def test_default_is_8am_half_hour():
    """Default: 08:00 in 30-min steps. 18 rows → 08:00…16:30 (covers 8am–5pm as blocks)."""
    labels = _hour_labels(Config(start_y=2026, start_m=7, months=1))
    assert labels[0] == "08:00" and labels[1] == "08:30", labels
    assert labels[-1] == "16:30", labels
    assert len(labels) == 18 and "" not in labels, labels     # every row filled, none blank


def test_part_hour_start():
    """hourStart accepts a part hour as decimal (7.25) or a 'H:MM' string ('8:30')."""
    assert _hour_labels(Config(start_y=2026, start_m=7, months=1, hour_start=7.25))[0] == "07:15"
    assert _hour_labels(Config(start_y=2026, start_m=7, months=1, hour_start="8:30"))[0] == "08:30"
    assert _hour_labels(Config(start_y=2026, start_m=7, months=1, hour_start="6:45"))[0] == "06:45"


def test_hourly_increment_wraps_midnight():
    """hourIncrement=1 gives whole-hour labels; the %24 formula renders midnight as 00:00."""
    labels = _hour_labels(Config(start_y=2026, start_m=7, months=1,
                                 hour_start=10, hour_increment=1))
    assert labels[0] == "10:00", labels
    assert labels[14] == "00:00", labels          # 10:00 + 14h = 24:00 → 00:00
    assert "" not in labels, labels


def test_config_validation():
    for bad in (dict(hour_increment=0),        # increment must be > 0
                dict(hour_increment=-0.5),
                dict(hour_start=24)):           # start out of 0–23
        try:
            Config(start_y=2026, start_m=7, months=1, **bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {bad}")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("✓ schedule-hours self-check passed")
