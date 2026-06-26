"""Date logic + page model (PIPELINE_SPEC §6, §7).

Pure, dependency-free. Ports the Planner.html date helpers and builds the
ordered page list + the set of all anchors that will exist (so links to a
non-generated page can degrade to plain text).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

# ---- constants (§6) --------------------------------------------------------
WD_LET = ["M", "T", "W", "T", "F", "S", "S"]
EN_WD = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
JP_WD = ["月", "火", "水", "木", "金", "土", "日"]
EN_MON = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
EN_MON_A = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ---- helpers (§6) ----------------------------------------------------------
def dim(y: int, m: int) -> int:
    """Days in month."""
    nm = date(y + (m == 12), (m % 12) + 1, 1)
    return (nm - date(y, m, 1)).days


def first_weekday(y: int, m: int) -> int:
    """Weekday of the 1st, Mon=0..Sun=6."""
    return date(y, m, 1).weekday()


def mon_monday(d: date) -> date:
    """Monday of d's week."""
    return d - timedelta(days=d.weekday())


def iso_week(d: date) -> tuple[int, int]:
    """(iso_year, iso_week)."""
    y, w, _ = d.isocalendar()
    return y, w


def mini_rows(y: int, m: int) -> list[list[dict]]:
    """6-or-fewer week rows of a month (Monday-start). Each cell: {d, col, valid}."""
    first, days = first_weekday(y, m), dim(y, m)
    n = (first + days + 6) // 7  # 4, 5, or 6
    rows, dd = [], 1 - first
    for _ in range(n):
        wk = []
        for c in range(7):
            valid = 1 <= dd <= days
            wk.append({"d": dd if valid else "", "col": c, "valid": valid})
            dd += 1
        rows.append(wk)
    return rows


def month_range(start_y: int, start_m: int, months: int) -> list[tuple[int, int]]:
    """List of (year, month) tuples, chronological, length = months."""
    out = []
    y, m = start_y, start_m
    for _ in range(months):
        out.append((y, m))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def weeks_of_month(y: int, m: int) -> list[date]:
    """Mondays whose month is (y, m) — i.e. the weeks belonging to this month
    (a week belongs to the month of its Monday, §7.2)."""
    mondays = set()
    for d in range(1, dim(y, m) + 1):
        mo = mon_monday(date(y, m, d))
        if mo.year == y and mo.month == m:
            mondays.add(mo)
    return sorted(mondays)


# ---- anchors (§6) ----------------------------------------------------------
def a_year(window_index: int) -> str:
    return "year" if window_index == 0 else f"year-{window_index + 1}"


def a_month(y: int, m: int) -> str:
    return f"month-{y:04d}-{m:02d}"


def a_week(monday: date, kind: str) -> str:
    """kind: 'b' (block) or 's' (schedule)."""
    iy, iw = iso_week(monday)
    return f"week-{iy:04d}-{iw:02d}-{kind}"


def a_day(d: date) -> str:
    return f"day-{d.year:04d}-{d.month:02d}-{d.day:02d}"


def a_cat(y: int, m: int, slot: int, nn: int) -> str:
    return f"cat-{y:04d}-{m:02d}-s{slot}-{nn:02d}"


# ---- page model (§7) -------------------------------------------------------
@dataclass
class Page:
    kind: str                 # cover|year|month|week-block|week-schedule|day|category
    anchor: str | None
    master: str | None        # template stem, e.g. '01-year' (None for cover)
    # context (only the relevant fields are set per kind)
    window: list[tuple[int, int]] | None = None   # year page: its <=12 months
    window_index: int = 0
    month: tuple[int, int] | None = None          # (y, m)
    monday: date | None = None                    # week pages
    day: date | None = None                       # day page
    slot: int | None = None                       # category 1..4
    index: int | None = None                      # category page 1..N
    active_month: tuple[int, int] | None = None   # rail highlight
    cover_source: str | None = None               # 'blank' or file path


MASTER = {
    "year": "01-year",
    "month": "02-month",
    "week-block": "03-week-block",
    "week-schedule": "04-week-schedule",
    "day": "05-day",
    "category": "06-category",
}


def build_pages(cfg) -> tuple[list[Page], set[str]]:
    """Build the ordered page list and the set of anchors that will exist.

    cfg duck-typed: .start_y .start_m .months .include (dict block/schedule/days)
                    .pages_per_category .cover_page
    """
    pages: list[Page] = []

    # optional cover (§7.3) — no anchor, never breaks links
    if cfg.cover_page:
        pages.append(Page(kind="cover", anchor=None, master=None,
                          cover_source=cfg.cover_page))

    months = month_range(cfg.start_y, cfg.start_m, cfg.months)
    months_set = set(months)
    windows = [months[i:i + 12] for i in range(0, len(months), 12)]

    for wi, win in enumerate(windows):
        full_win = month_range(win[0][0], win[0][1], 12)
        pages.append(Page(kind="year", anchor=a_year(wi), master=MASTER["year"],
                          window=full_win, window_index=wi))
        for (y, m) in win:
            am = (y, m)
            pages.append(Page(kind="month", anchor=a_month(y, m),
                              master=MASTER["month"], month=(y, m), active_month=am))
            month_mondays = weeks_of_month(y, m)  # sorted list
            month_mondays_set = set(month_mondays)

            # Partial first week: days before the first Monday owned by this month
            first_partial_days: list[date] = []
            for d in range(1, dim(y, m) + 1):
                dd = date(y, m, d)
                if mon_monday(dd) not in month_mondays_set:
                    first_partial_days.append(dd)
                else:
                    break

            if first_partial_days:
                partial_monday = mon_monday(first_partial_days[0])
                partial_ym = (partial_monday.year, partial_monday.month)
                # Only emit week pages if the Monday's month isn't already covered
                if partial_ym not in months_set:
                    if cfg.include.get("block", True):
                        pages.append(Page(kind="week-block",
                                          anchor=a_week(partial_monday, "b"),
                                          master=MASTER["week-block"],
                                          monday=partial_monday,
                                          month=(y, m), active_month=am))
                    if cfg.include.get("schedule", True):
                        pages.append(Page(kind="week-schedule",
                                          anchor=a_week(partial_monday, "s"),
                                          master=MASTER["week-schedule"],
                                          monday=partial_monday,
                                          month=(y, m), active_month=am))
                if cfg.include.get("days", True):
                    for dd in first_partial_days:
                        pages.append(Page(kind="day", anchor=a_day(dd),
                                          master=MASTER["day"], day=dd, month=(y, m),
                                          active_month=am))

            for monday in month_mondays:
                if cfg.include.get("block", True):
                    pages.append(Page(kind="week-block", anchor=a_week(monday, "b"),
                                      master=MASTER["week-block"], monday=monday,
                                      month=(y, m), active_month=am))
                if cfg.include.get("schedule", True):
                    pages.append(Page(kind="week-schedule", anchor=a_week(monday, "s"),
                                      master=MASTER["week-schedule"], monday=monday,
                                      month=(y, m), active_month=am))
                if cfg.include.get("days", True):
                    for offset in range(7):
                        dd = monday + timedelta(days=offset)
                        if dd.month == m:
                            pages.append(Page(kind="day", anchor=a_day(dd),
                                              master=MASTER["day"], day=dd, month=(y, m),
                                              active_month=am))
            for slot in range(1, 5):
                for nn in range(1, cfg.pages_per_category + 1):
                    pages.append(Page(kind="category", anchor=a_cat(y, m, slot, nn),
                                      master=MASTER["category"], month=(y, m),
                                      slot=slot, index=nn, active_month=am))

    anchors = {p.anchor for p in pages if p.anchor}
    return pages, anchors


def week_existing(anchors: set[str], monday: date, prefer: str) -> str | None:
    """Resolve a week link target with fallback (§5 weekExisting).

    prefer: 'schedule' or 'block'. Returns an existing anchor or None.
    """
    s, b = a_week(monday, "s"), a_week(monday, "b")
    order = (s, b) if prefer == "schedule" else (b, s)
    for a in order:
        if a in anchors:
            return a
    return None
