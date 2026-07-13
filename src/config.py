"""Configuration (PIPELINE_SPEC §5). JSON in, validated Config out."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CATEGORIES = ["Lists", "Projects", "Meetings", "Scratchpad"]


@dataclass
class Config:
    start_y: int
    start_m: int
    months: int = 12
    weeklink: str = "schedule"     # "schedule" | "block"
    include: dict = field(default_factory=lambda: {"year": True, "block": True, "schedule": True, "days": True})
    categories: list[str] = field(default_factory=lambda: list(DEFAULT_CATEGORIES))
    pages_per_category: int = 5
    cover_page: str | bool = False  # False | "blank" | path
    output: str = "out/planner.pdf"
    blanks: bool = True
    hour_start: float = 8          # week-schedule first row time — decimal hours or "H:MM" (e.g. 7.25 / "7:15")
    hour_increment: float = 0.5    # hours per schedule row (0.5 or 1); all rows fill from hour_start
    dot_scale: float = 0.8         # scales all dot-grid tile sizes (1.0 = original density)
    day_pages_per_day: int = 1     # #47: consecutive day pages per calendar day (default 1)

    def __post_init__(self):
        self.hour_start = _parse_hour(self.hour_start)   # accept "H:MM" or decimal hours
        if self.weeklink not in ("schedule", "block"):
            raise ValueError(f"weeklink must be schedule|block, got {self.weeklink!r}")
        if not 1 <= len(self.categories) <= 4:
            raise ValueError(f"categories must be 1–4 names, got {len(self.categories)}")
        if not 1 <= self.months <= 12:
            raise ValueError(f"months must be 1–12, got {self.months}")
        if self.pages_per_category < 0:
            raise ValueError("pagesPerCategory must be >= 0")
        if self.day_pages_per_day < 1:
            raise ValueError(f"dayPagesPerDay must be >= 1, got {self.day_pages_per_day}")
        if not 0 <= self.hour_start < 24:
            raise ValueError(f"hourStart must be in [0, 24), got {self.hour_start}")
        if round(self.hour_increment * 60) < 1:   # < 1 min/row → rows collapse to identical labels
            raise ValueError(f"hourIncrement must be at least 1 minute, got {self.hour_increment}")
        for c in self.categories:
            if len(c) > 12:
                raise ValueError(f"category name too long for rotated rail tab (<=12): {c!r}")


def _parse_ym(s: str) -> tuple[int, int]:
    y, m = s.split("-")
    return int(y), int(m)


def _parse_hour(v) -> float:
    """A clock time as decimal hours (7.25) or a 'H:MM' string ('7:15') → decimal hours."""
    if isinstance(v, str) and ":" in v:
        h, m = v.split(":", 1)
        h, m = int(h), int(m)
        if not 0 <= m < 60:
            raise ValueError(f"minutes must be 0–59 in hourStart {v!r}")
        return h + m / 60
    return float(v)


def load_config(path_or_dict) -> Config:
    if isinstance(path_or_dict, (str, Path)):
        data = json.loads(Path(path_or_dict).read_text(encoding="utf-8"))
    else:
        data = dict(path_or_dict)

    start_y, start_m = _parse_ym(data["start"])

    if "end" in data and data["end"]:
        ey, em = _parse_ym(data["end"])
        months = (ey - start_y) * 12 + (em - start_m) + 1
        if months < 1:
            raise ValueError("end is before start")
    else:
        months = int(data.get("months", 12))

    inc_in = data.get("include", {})
    include = {"year": True, "block": True, "schedule": True, "days": True}
    include.update({k: bool(v) for k, v in inc_in.items()})

    return Config(
        start_y=start_y,
        start_m=start_m,
        months=months,
        weeklink=data.get("weeklink", "schedule"),
        include=include,
        categories=data.get("categories", list(DEFAULT_CATEGORIES)),
        pages_per_category=int(data.get("pagesPerCategory", 5)),
        cover_page=data.get("coverPage", False),
        output=data.get("output", "out/planner.pdf"),
        blanks=bool(data.get("blanks", True)),
        hour_start=data.get("hourStart", 8),   # parsed by _parse_hour in __post_init__ ("H:MM" or hours)
        hour_increment=float(data.get("hourIncrement", 0.5)),
        dot_scale=float(data.get("dotScale", 0.8)),
        day_pages_per_day=int(data.get("dayPagesPerDay", 1)),
    )
