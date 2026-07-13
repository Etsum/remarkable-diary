"""Per-page fill contract (PIPELINE_SPEC §8) + link geometry (§9).

Public API
----------
fill_page(page, cfg, anchors, templates_dir) -> (svg_str, links)

`links` is a list of (x, y, w, h, target_anchor) in SVG user units (1 unit = 1 px).
Geometry comes from named node bboxes (rects/paths) or font-size approximations
for text nodes (accurate enough for click targets).
"""
from __future__ import annotations

import copy
import re
from datetime import date, timedelta
from pathlib import Path

from lxml import etree

from . import svgutil as SU
from .config import Config
from .dates import (
    EN_MON, EN_MON_A, EN_WD, JP_WD,
    Page, a_cat, a_day, a_month, a_week,
    dim, first_weekday, iso_week, mini_rows, month_range, week_existing,
)

# Colour tokens — e-ink palette (assets/e-ink-palette.tokens.json).
# The palette is greyscale-only for e-ink, so the former navy/maroon accents
# collapse onto Text/Primary (emphasis) vs Text/Secondary (regular text).
# These constants only restyle data-dependent states (active tab, Sunday, faded
# adjacent months); the SVG export is the style source of truth — PIPELINE_SPEC §3.5.
TEXT_PRIMARY   = "#000000"   # Text/Primary   — headers, today, active tab, weekend emphasis
TEXT_SECONDARY = "#4d4d4d"   # Text/Secondary — regular grid & mini-cal numbers
GRID_PRIMARY   = "#b8b8b8"   # Grid/Primary   — de-emphasised (adjacent-month) numbers
BASE           = "#ffffff"   # Other/Base     — inverse text on dark chips

# Fill-contract roles (§4)
ACCENT = TEXT_PRIMARY        # active rail tab / toolbar chip background (inverse text on it)
SUNDAY = TEXT_PRIMARY        # Sunday / weekend day-number emphasis
INK    = TEXT_SECONDARY      # regular day numbers
FAINT  = GRID_PRIMARY        # adjacent-month / out-of-range numbers
WHITE  = BASE                # inverse text on dark chips

Link = tuple[float, float, float, float, str]   # (x, y, w, h, target_anchor)


# ---------------------------------------------------------------------------
# Geometry helpers (§9)
# ---------------------------------------------------------------------------

def _el_bbox(el) -> tuple[float, float, float, float] | None:
    """Geometric bbox for rect/path/group; approximate bbox for text."""
    bb = SU.bbox(el)
    if bb is not None:
        return bb
    return _text_approx_bbox(el)


def _text_approx_bbox(el) -> tuple[float, float, float, float] | None:
    """Approximate bbox from tspan x/y + font-size (monospace assumption)."""
    tspans = el.findall(SU.S + "tspan")
    ts = tspans[0] if tspans else el
    try:
        x = float(ts.get("x") or el.get("x") or 0)
        y = float(ts.get("y") or el.get("y") or 0)
    except (TypeError, ValueError):
        return None
    fs = float(el.get("font-size") or 12)
    text = (ts.text or "") if ts is not None else (el.text or "")
    w = max(len(text) * 0.60 * fs, fs * 1.5)
    h = fs * 1.4
    return (x, y - h + fs * 0.2, w, h)


def _union_bbox(*bbs) -> tuple[float, float, float, float] | None:
    valid = [b for b in bbs if b is not None]
    if not valid:
        return None
    xs = [b[0] for b in valid] + [b[0] + b[2] for b in valid]
    ys = [b[1] for b in valid] + [b[1] + b[3] for b in valid]
    x0, y0 = min(xs), min(ys)
    return (x0, y0, max(xs) - x0, max(ys) - y0)


def _idm_bbox(idm: dict, *ids: str) -> tuple[float, float, float, float] | None:
    return _union_bbox(*[_el_bbox(idm[i]) for i in ids if i in idm])


# ---------------------------------------------------------------------------
# Rail fill — shared across all pages (§8.7)
# ---------------------------------------------------------------------------

def _center_rail_label(lbl, bg) -> None:
    """Centre a vertically-rotated rail section label along its tab's long axis (#44).

    The label transform is ``matrix(0 -1 1 0 e f)``: a local point (lx, ly) maps to
    device (ly + e, f - lx), so the reading axis (device-y) = f - lx. The labels are
    start-anchored at a fixed x, so a category name whose length differs from the
    baked placeholder renders off-centre (clustered at the tab bottom). Re-anchor with
    ``text-anchor=middle`` and put the tspan x at the tab centre — lx = f - (tab_y +
    tab_h/2) — so the renderer centres the text using real font metrics (Noto Sans is
    proportional). Cross-axis (tab width) position is left untouched.
    """
    ts = lbl.find(SU.S + "tspan")
    bb = SU.bbox(bg) if bg is not None else None
    if ts is None or bb is None:
        return
    m = re.match(r"matrix\(([^)]+)\)", lbl.get("transform", ""))
    parts = m.group(1).replace(",", " ").split() if m else []
    try:
        f = float(parts[5])
    except (IndexError, ValueError):
        f = bb[1] + bb[3]          # fallback: transform origin at tab bottom
    ts.set("x", f"{f - (bb[1] + bb[3] / 2):.3f}")
    lbl.set("text-anchor", "middle")


def _fill_rail(
    idm: dict,
    cfg: Config,
    active_month: tuple[int, int] | None,
    anchors: set[str],
    window: list[tuple[int, int]],
) -> list[Link]:
    links: list[Link] = []

    # Section labels: fill provided categories; blank unused tabs — clear the
    # label and hide the chip so the slot reads as empty rail (#30).
    for i in range(1, 5):
        lbl = idm.get(f"rail-section-{i}")
        bg  = idm.get(f"rail-section-{i}-bg")
        if i <= len(cfg.categories):
            if lbl is not None:
                SU.set_text(lbl, cfg.categories[i - 1])
                _center_rail_label(lbl, bg)   # #44: centre along the tab's long axis
        else:
            if lbl is not None:
                SU.set_text(lbl, "")
            if bg is not None:
                SU.set_fill(bg, "none")

    # Active month tab highlight (§8.7)
    if active_month:
        _, am = active_month
        for mm in range(1, 13):
            bg  = idm.get(f"rail-month-{mm:02d}-bg")
            lbl = idm.get(f"rail-month-{mm:02d}")
            if mm == am:
                if bg  is not None: SU.set_fill(bg, ACCENT)
                if lbl is not None:
                    SU.set_fill(lbl, WHITE)
                    SU.set_font_weight(lbl, "bold")

    # Index chip → year (all pages)
    chip = idm.get("rail-index-chip")
    if chip is not None:
        bb = _el_bbox(chip)
        if bb and "year" in anchors:
            links.append((*bb, "year"))

    # Month tabs → month-YYYY-MM. Keep the baked JAN–DEC labels; link each tab to
    # whichever year that month falls in within the planner window (#27). Months
    # is capped at 12, so each month number maps to exactly one year.
    for yy, mm in window:
        bg = idm.get(f"rail-month-{mm:02d}-bg")
        if bg is not None:
            bb = _el_bbox(bg)
            if bb:
                tgt = a_month(yy, mm)
                if tgt in anchors:
                    links.append((*bb, tgt))

    # Section tabs → first cat page of current month (if pages_per_category > 0)
    if active_month and cfg.pages_per_category > 0:
        ay, am = active_month
        for i in range(1, len(cfg.categories) + 1):
            bg = idm.get(f"rail-section-{i}-bg")
            if bg is not None:
                bb = _el_bbox(bg)
                if bb:
                    tgt = a_cat(ay, am, i, 1)
                    if tgt in anchors:
                        links.append((*bb, tgt))

    return links


# ---------------------------------------------------------------------------
# Month grid helper: yields (row1, col1, date, is_current_month)
# ---------------------------------------------------------------------------

def _month_grid(y: int, m: int):
    start = date(y, m, 1) - timedelta(days=first_weekday(y, m))
    d = start
    for r in range(6):
        for c in range(7):
            yield (r + 1, c + 1, d, d.month == m)
            d += timedelta(days=1)


# ---------------------------------------------------------------------------
# Year page (§8.1)
# ---------------------------------------------------------------------------

def _mini_set(node, value: str) -> None:
    # ponytail: IBM Plex Mono is monospaced; template x is right-aligned per placeholder digit count
    tspan = node.find(SU.S + "tspan")
    if tspan is not None and value:
        old = tspan.text or ""
        old_n = len(old.strip()) or 1  # strip to handle whitespace/newline placeholders
        new_n = len(value)
        if old_n != new_n:
            try:
                cw = float(node.get("font-size", "13.5")) * 0.6
                tspan.set("x", f"{float(tspan.get('x', '0')) + (old_n - new_n) * cw:.3f}")
            except (ValueError, TypeError):
                pass
    SU.set_text(node, value)


def _meta_set(node, value: str) -> None:
    # ponytail: center-align text at the placeholder's visual center point
    tspan = node.find(SU.S + "tspan")
    if tspan is not None:
        old_n = len((tspan.text or "").strip()) or 1
        new_n = len(value) or 1
        if old_n != new_n:
            try:
                cw = float(node.get("font-size", "14")) * 0.6
                x = float(tspan.get("x", "0"))
                tspan.set("x", f"{x + (old_n - new_n) * cw / 2:.3f}")
            except (ValueError, TypeError):
                pass
    SU.set_text(node, value)


def _fill_year(page: Page, cfg: Config, idm: dict, anchors: set[str]) -> list[Link]:
    links: list[Link] = []
    window = page.window or []
    start_y = window[0][0] if window else 0

    first_abbr = EN_MON_A[window[0][1] - 1]  if window else ""
    last_abbr  = EN_MON_A[window[-1][1] - 1] if window else ""
    if "hdr-meta-top"    in idm: _meta_set(idm["hdr-meta-top"],    first_abbr)
    if "hdr-meta-bottom" in idm: _meta_set(idm["hdr-meta-bottom"], last_abbr)
    if "footer-left"     in idm: SU.set_text(idm["footer-left"], f"YEAR {start_y}")

    # hdr-big: single year or two-line "YYYY\nYYYY" when window spans calendar years
    if "hdr-big" in idm and window:
        years = sorted({y for y, _ in window})
        ts = idm["hdr-big"].find(SU.S + "tspan")
        if ts is not None:
            if len(years) == 1:
                ts.text = str(years[0])
            else:
                y0 = float(ts.get("y", "117"))
                ts.text = str(years[0])
                ts.set("y", str(y0 - 18))
                ts1 = etree.SubElement(idm["hdr-big"], SU.S + "tspan")
                ts1.set("x", ts.get("x", "135.828"))
                ts1.set("y", str(y0 + 18))
                ts1.text = str(years[1])

    for slot_idx, (my, mm) in enumerate(window):
        nn = slot_idx + 1
        lbl = idm.get(f"mini-{nn:02d}-label")
        if lbl is not None:
            SU.set_text(lbl, EN_MON_A[mm - 1])
            bb = _el_bbox(lbl)
            if bb:
                tgt = a_month(my, mm)
                if tgt in anchors:
                    links.append((*bb, tgt))
        lbl_jp = idm.get(f"mini-{nn:02d}-label-jp")
        if lbl_jp is not None:
            SU.set_text(lbl_jp, f"{mm}月")

        rows = mini_rows(my, mm)
        for r_idx, row in enumerate(rows):
            for c_idx, cell in enumerate(row):
                cid = f"mini-{nn:02d}-d-r{r_idx+1}c{c_idx+1}"
                node = idm.get(cid)
                if node is None:
                    continue
                if cell["valid"]:
                    _mini_set(node, str(cell["d"]))
                    SU.set_fill(node, SUNDAY if c_idx == 6 else INK)
                    dd = date(my, mm, cell["d"])
                    tgt = a_day(dd)
                    if tgt in anchors:
                        bb = _el_bbox(node)
                        if bb:
                            links.append((*bb, tgt))
                else:
                    SU.set_text(node, "")

        # Clear unused rows beyond actual row count
        for r_idx in range(len(rows), 6):
            for c_idx in range(7):
                node = idm.get(f"mini-{nn:02d}-d-r{r_idx+1}c{c_idx+1}")
                if node is not None:
                    SU.set_text(node, "")

    # Clear mini slots beyond the window (partial final year)
    for nn in range(len(window) + 1, 13):
        for key in (f"mini-{nn:02d}-label", f"mini-{nn:02d}-label-jp"):
            node = idm.get(key)
            if node is not None:
                SU.set_text(node, "")
        for r_idx in range(6):
            for c_idx in range(7):
                node = idm.get(f"mini-{nn:02d}-d-r{r_idx+1}c{c_idx+1}")
                if node is not None:
                    SU.set_text(node, "")

    return links


# ---------------------------------------------------------------------------
# Month page (§8.2)
# ---------------------------------------------------------------------------

def _fill_month(page: Page, cfg: Config, idm: dict, anchors: set[str]) -> list[Link]:
    links: list[Link] = []
    y, m = page.month

    _meta_set(idm["hdr-big"], str(m))  # center in box (1- vs 2-digit months)
    _meta_set(idm["hdr-month-name"], EN_MON[m - 1])
    if "hdr-month-jp"    in idm:
        SU.set_text(idm["hdr-month-jp"], f"{m}月")
    if "hdr-meta-top"    in idm: SU.set_text(idm["hdr-meta-top"],    "YEAR")
    if "hdr-meta-bottom" in idm: SU.set_text(idm["hdr-meta-bottom"], str(y))
    if "footer-left"     in idm: SU.set_text(idm["footer-left"], f"{EN_MON[m-1]} {y}")

    # Grid cells — always 6 rows; adjacent-month days get FAINT fill
    for row, col, d, is_cur in _month_grid(y, m):
        node = idm.get(f"mcell-r{row}c{col}-num")
        if node is None:
            continue
        SU.set_text(node, str(d.day))
        if is_cur:
            SU.set_fill(node, SUNDAY if col == 7 else INK)  # col is 1-based, Sunday=7
            tgt = a_day(d)
            if tgt in anchors:
                bb = _el_bbox(node)
                if bb:
                    links.append((*bb, tgt))
        else:
            SU.set_fill(node, FAINT)

    # Week number column — FAINT for rows whose Monday is outside the current month
    row_mondays: dict[int, tuple[date, bool]] = {}
    for row, col, d, is_cur in _month_grid(y, m):
        if col == 1 and row not in row_mondays:
            row_mondays[row] = (d, is_cur)
    for row, (monday, is_cur) in row_mondays.items():
        node = idm.get(f"mrow-{row}-weeknum")
        if node is None:
            continue
        _, iw = iso_week(monday)
        SU.set_text(node, f"W{iw}")
        if not is_cur:
            SU.set_fill(node, FAINT)
        tgt = week_existing(anchors, monday, cfg.weeklink)
        if tgt:
            bb = _el_bbox(node)
            if bb:
                links.append((*bb, tgt))

    # Footer-right → year overview
    fr = idm.get("footer-right")
    if fr is not None:
        bb = _el_bbox(fr)
        if bb and "year" in anchors:
            links.append((*bb, "year"))

    return links


# ---------------------------------------------------------------------------
# Shared week header (§8.3/§8.4)
# ---------------------------------------------------------------------------

def _fill_week_header(page: Page, cfg: Config, idm: dict) -> None:
    monday = page.monday
    y, m = page.month
    sunday = monday + timedelta(days=6)
    _, iw = iso_week(monday)

    _meta_set(idm["hdr-big"], str(m))  # center in box (1- vs 2-digit months)
    _meta_set(idm["hdr-month-name"], EN_MON[m - 1])
    if "hdr-month-jp"    in idm:
        SU.set_text(idm["hdr-month-jp"], f"{m}月")
    if "hdr-meta-top"    in idm: _meta_set(idm["hdr-meta-top"],    f"{monday.day}–{sunday.day}")
    if "hdr-meta-bottom" in idm: SU.set_text(idm["hdr-meta-bottom"], str(monday.year))
    if "footer-left"     in idm:
        SU.set_text(idm["footer-left"], f"WEEK {iw} · {EN_MON_A[m-1]} {monday.year}")


# ---------------------------------------------------------------------------
# Week-block (§8.3)
# ---------------------------------------------------------------------------

def _fill_week_block(page: Page, cfg: Config, idm: dict, anchors: set[str]) -> list[Link]:
    links: list[Link] = []
    monday = page.monday
    _fill_week_header(page, cfg, idm)

    # Toggle: BLOCK active
    tb_bg = idm.get("hdr-toggle-block-bg")
    tb    = idm.get("hdr-toggle-block")
    if tb_bg is not None: SU.set_fill(tb_bg, ACCENT)
    if tb    is not None: SU.set_fill(tb,    WHITE)

    # Schedule toggle → sibling schedule page
    ts_bg = idm.get("hdr-toggle-schedule-bg")
    if ts_bg is not None:
        bb = _el_bbox(ts_bg)
        if bb:
            tgt = a_week(monday, "s")
            if tgt in anchors:
                links.append((*bb, tgt))

    # Day cells
    for n in range(1, 8):
        dd = monday + timedelta(days=n - 1)
        num = idm.get(f"wb-day-{n}-num")
        wd  = idm.get(f"wb-day-{n}-wd")
        if num is not None: SU.set_text(num, str(dd.day))
        if wd  is not None: SU.set_text(wd,  EN_WD[n - 1])
        bb = _idm_bbox(idm, f"wb-day-{n}-num", f"wb-day-{n}-wd")
        if bb:
            tgt = a_day(dd)
            if tgt in anchors:
                links.append((*bb, tgt))

    # Footer-right "↳ month overview" → month page
    fr = idm.get("footer-right")
    if fr is not None:
        bb = _el_bbox(fr)
        if bb:
            y, m = page.month
            tgt = a_month(y, m)
            if tgt in anchors:
                links.append((*bb, tgt))

    return links


# ---------------------------------------------------------------------------
# Week-schedule (§8.4)
# ---------------------------------------------------------------------------

def _fill_week_schedule(page: Page, cfg: Config, idm: dict, anchors: set[str]) -> list[Link]:
    links: list[Link] = []
    monday = page.monday
    _fill_week_header(page, cfg, idm)

    # Toggle: SCHEDULE active
    ts_bg = idm.get("hdr-toggle-schedule-bg")
    ts    = idm.get("hdr-toggle-schedule")
    if ts_bg is not None: SU.set_fill(ts_bg, ACCENT)
    if ts    is not None: SU.set_fill(ts,    WHITE)

    # Block toggle → sibling block page
    tb_bg = idm.get("hdr-toggle-block-bg")
    if tb_bg is not None:
        bb = _el_bbox(tb_bg)
        if bb:
            tgt = a_week(monday, "b")
            if tgt in anchors:
                links.append((*bb, tgt))

    # Hour labels: fill every physical row from `hour_start`, stepping `hour_increment` hours
    # per row (labels are block-start times, HH:MM, wrapping past midnight). Row count is read
    # from the master, so it tracks the design's fixed 18 rows without a magic constant (#63).
    hour_ids = sorted((k for k in idm if k.startswith("ws-hour-pos-")),
                      key=lambda k: int(k.rsplit("-", 1)[1]))
    start = round(cfg.hour_start * 60)             # first row in minutes (part-hours OK, e.g. 7.25 → 07:15)
    step = round(cfg.hour_increment * 60)          # minutes/row, integer to avoid float drift
    for i, hid in enumerate(hour_ids):
        total = start + i * step
        SU.set_text(idm[hid], f"{(total // 60) % 24:02d}:{total % 60:02d}")

    # Day cells
    for n in range(1, 8):
        dd = monday + timedelta(days=n - 1)
        num = idm.get(f"ws-day-{n}-num")
        wd  = idm.get(f"ws-day-{n}-wd")
        if num is not None: SU.set_text(num, str(dd.day))
        if wd  is not None: SU.set_text(wd,  EN_WD[n - 1])
        bb = _idm_bbox(idm, f"ws-day-{n}-num", f"ws-day-{n}-wd")
        if bb:
            tgt = a_day(dd)
            if tgt in anchors:
                links.append((*bb, tgt))

    # Footer-right "↳ week block" → sibling block page
    fr = idm.get("footer-right")
    if fr is not None:
        bb = _el_bbox(fr)
        if bb:
            tgt = a_week(monday, "b")
            if tgt in anchors:
                links.append((*bb, tgt))

    return links


# ---------------------------------------------------------------------------
# Day page (§8.5)
# ---------------------------------------------------------------------------

def _fill_day(page: Page, cfg: Config, idm: dict, anchors: set[str]) -> list[Link]:
    links: list[Link] = []
    d = page.day
    y, m = d.year, d.month
    wd_idx = d.weekday()
    _, iw = iso_week(d)

    # Header
    _meta_set(idm["hdr-big"], str(d.day))  # day-of-month (#10), centered in box (#25)
    _meta_set(idm["hdr-month-name"], EN_MON[m - 1])
    if "hdr-month-jp" in idm:
        SU.set_text(idm["hdr-month-jp"], f"{m}月")
    if "hdr-right-weekday" in idm:
        SU.set_text(idm["hdr-right-weekday"], f"{EN_WD[wd_idx]} · {JP_WD[wd_idx]}")
    if "hdr-meta-top"    in idm: SU.set_text(idm["hdr-meta-top"],    "WEEK")
    if "hdr-meta-bottom" in idm: _meta_set(idm["hdr-meta-bottom"],   str(iw))
    if "hdr-big-label"   in idm: _meta_set(idm["hdr-big-label"],     "DAY")

    # Datebox area → year page
    for frame_id in ("hdr-meta", "hdr-datebox-frame"):
        node = idm.get(frame_id)
        if node is not None:
            bb = _el_bbox(node)
            if bb and "year" in anchors:
                links.append((*bb, "year"))
            break  # prefer hdr-meta; fallback to frame

    # Footer (keeps the stylistic 月/日 glyphs; no lang option) — #53
    if "footer-left" in idm:
        SU.set_text(idm["footer-left"], f"{m}月 {d.day}日, {y}")

    # Footer-right "↳ week" → week page
    monday = d - timedelta(days=d.weekday())
    fr = idm.get("footer-right")
    if fr is not None:
        bb = _el_bbox(fr)
        if bb:
            tgt = week_existing(anchors, monday, cfg.weeklink)
            if tgt:
                links.append((*bb, tgt))

    # Mini-cal (current month)
    if "day-mini-month" in idm: SU.set_text(idm["day-mini-month"], EN_MON_A[m - 1])
    if "day-mini-year"  in idm: SU.set_text(idm["day-mini-year"],  str(y))

    rows = mini_rows(y, m)
    for r_idx, row in enumerate(rows):
        for c_idx, cell in enumerate(row):
            node = idm.get(f"day-mini-r{r_idx+1}c{c_idx+1}")
            if node is None:
                continue
            if cell["valid"]:
                day_num = cell["d"]
                _mini_set(node, str(day_num))  # #24: right-align 2-digit dates
                if day_num == d.day:
                    SU.set_fill(node, ACCENT)
                elif c_idx == 6:
                    SU.set_fill(node, SUNDAY)
                else:
                    SU.set_fill(node, INK)
                tgt = a_day(date(y, m, day_num))
                if tgt in anchors:
                    bb = _el_bbox(node)
                    if bb:
                        links.append((*bb, tgt))
            else:
                SU.set_text(node, "")

    # Clear unused rows
    for r_idx in range(len(rows), 6):
        for c_idx in range(7):
            node = idm.get(f"day-mini-r{r_idx+1}c{c_idx+1}")
            if node is not None:
                SU.set_text(node, "")

    return links


# ---------------------------------------------------------------------------
# Category page (§8.6)
# ---------------------------------------------------------------------------

def _fill_category(page: Page, cfg: Config, idm: dict, anchors: set[str]) -> list[Link]:
    links: list[Link] = []
    slot  = page.slot   # 1..4
    idx   = page.index  # 1..N
    y, m  = page.month
    name  = cfg.categories[slot - 1]
    n_total = cfg.pages_per_category

    # hdr-big: first letter of category (design intent)
    SU.set_text(idm["hdr-big"], name[0].upper() if name else "")
    if "hdr-big-label"  in idm: SU.set_text(idm["hdr-big-label"],  "")
    if "hdr-month-name" in idm: SU.set_text(idm["hdr-month-name"], name)
    if "hdr-month-jp"   in idm: SU.set_text(idm["hdr-month-jp"],   "")
    if "hdr-meta-top"    in idm: SU.set_text(idm["hdr-meta-top"],    EN_MON_A[m - 1])
    if "hdr-meta-bottom" in idm: SU.set_text(idm["hdr-meta-bottom"], f"{idx}/{n_total}")
    if "footer-left"     in idm: SU.set_text(idm["footer-left"], name)  # issue #12

    # Footer-right → year overview (issue #13)
    fr = idm.get("footer-right")
    if fr is not None:
        SU.set_text(fr, "↳ index")
        bb = _el_bbox(fr)
        if bb and "year" in anchors:
            links.append((*bb, "year"))

    return links


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fill_page(
    page: Page,
    cfg: Config,
    anchors: set[str],
    templates_dir: Path,
) -> tuple[str, list[Link]]:
    """Clone master SVG, fill all var-ink nodes, collect link rects.

    Returns (svg_string, links) where links = [(x, y, w, h, target_anchor), ...].
    Cover pages return ("", []).
    """
    if page.kind == "cover":
        return ("", [])

    master_path = templates_dir / f"{page.master}.svg"
    tree = SU.parse(str(master_path))
    root = copy.deepcopy(tree.getroot())
    idm  = SU.id_map(root)

    links: list[Link] = []

    if page.kind == "year":
        links.extend(_fill_year(page, cfg, idm, anchors))
    elif page.kind == "month":
        links.extend(_fill_month(page, cfg, idm, anchors))
    elif page.kind == "week-block":
        links.extend(_fill_week_block(page, cfg, idm, anchors))
    elif page.kind == "week-schedule":
        links.extend(_fill_week_schedule(page, cfg, idm, anchors))
    elif page.kind == "day":
        links.extend(_fill_day(page, cfg, idm, anchors))
    elif page.kind == "category":
        links.extend(_fill_category(page, cfg, idm, anchors))

    # Rail is identical on every page: link all in-range months to their year (#27)
    rail_window = month_range(cfg.start_y, cfg.start_m, cfg.months)
    links.extend(_fill_rail(idm, cfg, page.active_month, anchors, rail_window))
    return SU.tostring(root), links
