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
    lang: str = "jp-en"            # "jp-en" | "en"
    weeklink: str = "schedule"     # "schedule" | "block"
    include: dict = field(default_factory=lambda: {"block": True, "schedule": True, "days": True})
    categories: list[str] = field(default_factory=lambda: list(DEFAULT_CATEGORIES))
    pages_per_category: int = 5
    cover_page: str | bool = False  # False | "blank" | path
    output: str = "out/planner.pdf"
    blanks: bool = True
    hour_start: int = 5            # week-schedule first hour label (24h); 18 rows fixed (D11)

    def __post_init__(self):
        if self.lang not in ("jp-en", "en"):
            raise ValueError(f"lang must be jp-en|en, got {self.lang!r}")
        if self.weeklink not in ("schedule", "block"):
            raise ValueError(f"weeklink must be schedule|block, got {self.weeklink!r}")
        if len(self.categories) != 4:
            raise ValueError(f"categories must be exactly 4 names, got {len(self.categories)}")
        if self.pages_per_category < 0:
            raise ValueError("pagesPerCategory must be >= 0")
        for c in self.categories:
            if len(c) > 12:
                raise ValueError(f"category name too long for rotated rail tab (<=12): {c!r}")


def _parse_ym(s: str) -> tuple[int, int]:
    y, m = s.split("-")
    return int(y), int(m)


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
    include = {"block": True, "schedule": True, "days": True}
    include.update({k: bool(v) for k, v in inc_in.items()})

    return Config(
        start_y=start_y,
        start_m=start_m,
        months=months,
        lang=data.get("lang", "jp-en"),
        weeklink=data.get("weeklink", "schedule"),
        include=include,
        categories=data.get("categories", list(DEFAULT_CATEGORIES)),
        pages_per_category=int(data.get("pagesPerCategory", 5)),
        cover_page=data.get("coverPage", False),
        output=data.get("output", "out/planner.pdf"),
        blanks=bool(data.get("blanks", True)),
        hour_start=int(data.get("hourStart", 5)),
    )
