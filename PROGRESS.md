# Progress — reMarkable planner generator

Implements `PIPELINE_SPEC.md`: six Figma master SVGs → deterministic hyperlinked PDF
+ blank write-on PNGs for any date range. See `SPEC.md` / `HANDOVER.md` for design
intent; `PIPELINE_SPEC.md` for the build contract.

---

## Status: MVP complete ✓ — bug-fix phase

All eight generator modules are implemented and the end-to-end pipeline works.
Active work is closing the open GitHub issues (see below).

### Module map

| File | Purpose |
|------|---------|
| `src/dates.py` | Date helpers + page model + anchor scheme (§6/§7) |
| `src/config.py` | Config load/validate (§5) |
| `src/fonts.py` | @font-face CSS + CJK fallback chain |
| `src/svgutil.py` | lxml mutate helpers + `bbox()` |
| `src/background.py` | Dot-grid injection (§10) |
| `src/fill.py` | Per-page fill (§8) + link geometry (§9) |
| `src/render.py` | Playwright PDF + blank PNGs (§11/§12) |
| `src/build.py` | CLI + pre-flight validator (§13.1) |

### Quick start

```bash
uv sync
uv run playwright install chromium
uv run playwright install-deps chromium   # one-time system libs

uv run python -m src.build --validate-only          # pre-flight check
uv run python -m src.build --start 2026-07 --months 1 --output tmp/test.pdf
uv run python -m src.build --start 2026-01 --months 12 --output tmp/planner-2026.pdf
uv run python -m src.build --blanks-only --output tmp/x.pdf

# Single-page render helper (no Playwright — reads from templates dir directly)
uv run python scripts/render_page.py --anchor month-2026-07 --output tmp/page.png
```

---

## Confirmed design decisions

| Decision | Value |
|----------|-------|
| Templates | `assets/templates/rm2/` |
| Renderer | Playwright/Chromium (swappable module) |
| `hdr-big` on week pages | Month number (label says "MONTH") |
| `hdr-big` on day page | Day-of-month number |
| `hdr-big` on category page | First letter of category name |
| Link geometry | `svgutil.bbox()` for rects/paths; font-size approximation for text nodes |
| Background-prepped SVGs | Written to temp dir during build; fill.py reads dot-grid-ready masters |
| Rail month links | `page.window` for year pages (handles cross-year planners); `active_month[0]` for all other pages |
| Dot grid scale | `dot_scale=0.8` default (20% finer than Figma original); configurable via `--dot-scale` or `dotScale` JSON |

---

## Open issues (GitHub `Etsum/remarkable-diary`)

### Code-owned

| # | Title | File |
|---|-------|------|
| [#3](https://github.com/Etsum/remarkable-diary/issues/3) | Mini-calendars: '.' placeholder leaks into empty cells | `fill.py` — clear unused row cells explicitly |

### Design-owned (waiting on Figma re-export)

| # | Title |
|---|-------|
| [#24](https://github.com/Etsum/remarkable-diary/issues/24) | Day page: mini-cal dates misaligned |
| [#25](https://github.com/Etsum/remarkable-diary/issues/25) | Day page: 'DAY' label not centred under 2-digit date numbers |

---

## Recently closed

| # | Title |
|---|-------|
| [#26](https://github.com/Etsum/remarkable-diary/issues/26) | Page order: weeks appear before days in partial first week |
| [#22](https://github.com/Etsum/remarkable-diary/issues/22) | Category blank: footer-left shows 'LISTS' |
| [#20](https://github.com/Etsum/remarkable-diary/issues/20) | Category: hdr-meta should not show month/year |
| [#19](https://github.com/Etsum/remarkable-diary/issues/19) | Category: hdr-big-label and hdr-month-jp should be blank |
| [#18](https://github.com/Etsum/remarkable-diary/issues/18) | Month prev-nav on first month doesn't link to year overview |
| [#17](https://github.com/Etsum/remarkable-diary/issues/17) | Year rail tabs not all hyperlinked when start ≠ January |
| [#15](https://github.com/Etsum/remarkable-diary/issues/15) | Day page hdr-meta-bottom (week #) misaligned |
| [#13](https://github.com/Etsum/remarkable-diary/issues/13) | footer-right on category pages not linked |
| [#12](https://github.com/Etsum/remarkable-diary/issues/12) | Category footer-left shows "LISTS" not section name |
| [#11](https://github.com/Etsum/remarkable-diary/issues/11) | Category hdr-meta-top overflows right |
| [#10](https://github.com/Etsum/remarkable-diary/issues/10) | Day page: hdr-big should be day-of-month |
| [#9](https://github.com/Etsum/remarkable-diary/issues/9) | Year page: mini-cal day numbers misaligned |
| [#8](https://github.com/Etsum/remarkable-diary/issues/8) | Year overview always 12 months from start date |
| [#5](https://github.com/Etsum/remarkable-diary/issues/5) | Month page: 6th week-number row shows placeholder |
| [#4](https://github.com/Etsum/remarkable-diary/issues/4) | Blank PNGs: strip footer-right link text |
| [#2](https://github.com/Etsum/remarkable-diary/issues/2) | Blank PNGs: strip hdr-nav arrows |

---

## Architecture notes for next agent

**Page order** (as of commit `0bf9b9d`):
```
[cover]  Year overview
For each month M:
  Month overview
  [partial first week: week-block → week-schedule → day pages for days before 1st owned Monday]
    (week pages only emitted if the partial Monday's month is not already in the planner)
  For each week W with Monday in M:
    Week block → Week schedule → Day pages for days in W that belong to M
  Category pages (slot 1–4, N pages each)
```

**fill.py entry point:** `fill_page(page, cfg, anchors, templates_dir) → (svg_str, links)`
- Links = `[(x, y, w, h, target_anchor), ...]` in SVG user units (1 unit = 1 px)
- Called from `build.py` with background-prepped SVGs in a temp dir

**build.py pipeline:**
1. `validate_masters()` — pre-flight, fails loudly
2. `build_pages(cfg)` → page list + anchor set
3. `prepare_background(tree, stem, cfg.dot_scale)` per master → write to temp dir
4. `fill_page()` per page → `(svg_str, links)`
5. `render_pdf()` — one HTML doc, Playwright prints PDF
6. `render_blanks()` — one PNG per master type

**Key fill.py helpers:**
- `_meta_set(node, value)` — center-aligns text within placeholder width; used for month names, date ranges, week numbers, hdr-big-label
- `_mini_set(node, value)` — right-aligns text for mini-cal cells; handles `'.\n'` style placeholders
- `SU.set_text(node, value)` — raw tspan text replacement (no alignment adjustment)
- `_fill_rail(idm, cfg, active_month, rail_year, anchors, window=None)` — pass `window=page.window` for year pages to handle cross-year planners

**var-ink gotcha:** `var-ink` group is present on ALL six masters (including `06-category`). Removed entirely in blank PNG mode. Everything that changes per-page lives inside it.
