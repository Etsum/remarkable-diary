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
| `planner_gen/dates.py` | Date helpers + page model + anchor scheme (§6/§7) |
| `planner_gen/config.py` | Config load/validate (§5) |
| `planner_gen/fonts.py` | @font-face CSS + CJK fallback chain |
| `planner_gen/svgutil.py` | lxml mutate helpers + `bbox()` |
| `planner_gen/background.py` | Dot-grid injection (§10) |
| `planner_gen/fill.py` | Per-page fill (§8) + link geometry (§9) |
| `planner_gen/render.py` | Playwright PDF + blank PNGs (§11/§12) |
| `planner_gen/build.py` | CLI + pre-flight validator (§13.1) |

### Quick start

```bash
uv sync
uv run playwright install chromium
uv run playwright install-deps chromium   # one-time system libs

uv run python -m planner_gen.build --validate-only          # pre-flight check
uv run python -m planner_gen.build --start 2026-02 --months 1 --output out/test.pdf
uv run python -m planner_gen.build --start 2026-01 --months 12 --output out/planner-2026.pdf
uv run python -m planner_gen.build --blanks-only --output out/x.pdf
```

---

## Confirmed design decisions

| Decision | Value |
|----------|-------|
| Templates | `templates/` (not `uploads/`) |
| Renderer | Playwright/Chromium (swappable module) |
| `hdr-big` on week pages | Month number (label says "MONTH") |
| `hdr-big` on day page | **Currently month number** — issue #10 will change to day-of-month |
| `hdr-big` on category page | First letter of category name |
| Link geometry | `svgutil.bbox()` for rects/paths; font-size approximation for text nodes |
| Background-prepped SVGs | Written to temp dir during build; fill.py reads dot-grid-ready masters |
| Rail month links | Keyed on `active_month[0]` (year) — correct for 1-year ranges |

---

## Open issues (GitHub `Etsum/remarkable-diary`)

### Code-owned — ready to fix

| # | Title | Effort | File |
|---|-------|--------|------|
| [#10](https://github.com/Etsum/remarkable-diary/issues/10) | Day page: hdr-big should be day-of-month, not month | 1 line | `fill.py` `_fill_day()` |
| [#12](https://github.com/Etsum/remarkable-diary/issues/12) | Category footer-left shows "LISTS" not section name | 1 line | `fill.py` `_fill_category()` |
| [#13](https://github.com/Etsum/remarkable-diary/issues/13) | footer-right on category pages not linked | ~5 lines | `fill.py` `_fill_category()` |
| [#8](https://github.com/Etsum/remarkable-diary/issues/8) | Year overview always 12 months from start date | Medium | `dates.py` + `fill.py` |
| [#1](https://github.com/Etsum/remarkable-diary/issues/1) | Year overview: rail shows active month (should be neutral) | Small | `fill.py` `_fill_rail()` — skip active-month restyle on year page |
| [#3](https://github.com/Etsum/remarkable-diary/issues/3) | Mini-calendars: '.' placeholder leaks into empty cells | Small | `fill.py` — clear unused row cells explicitly |
| [#5](https://github.com/Etsum/remarkable-diary/issues/5) | Month page: 6th week-number row shows 'W-' placeholder | Small | `fill.py` `_fill_month()` — clear unused mrow nodes |
| [#7](https://github.com/Etsum/remarkable-diary/issues/7) | All renders use serif fallback instead of correct fonts | Medium | `render.py` / `fonts.py` — font loading path |
| [#2](https://github.com/Etsum/remarkable-diary/issues/2) | Blank PNGs: strip hdr-nav arrows | Small | `render.py` `_BLANK_REMOVE_IDS` already includes `hdr-nav` — verify |
| [#4](https://github.com/Etsum/remarkable-diary/issues/4) | Blank PNGs: strip footer-right link text | Small | `render.py` `_BLANK_REMOVE_IDS` already includes `footer-right` — verify |

### Design-owned (waiting on Figma re-export)

| # | Title |
|---|-------|
| [#9](https://github.com/Etsum/remarkable-diary/issues/9) | Year page: mini-cal day numbers misaligned — set text-anchor:middle in Figma |
| [#11](https://github.com/Etsum/remarkable-diary/issues/11) | Category hdr-meta-top overflows right — fix tspan x position in Figma |

### Recently closed

| # | Title | Commit |
|---|-------|--------|
| [#14](https://github.com/Etsum/remarkable-diary/issues/14) | Page order: days interleaved with weeks | `0855634` |
| [#6](https://github.com/Etsum/remarkable-diary/issues/6) | Dot-grid backgrounds | `5e8306f` |

---

## Architecture notes for next agent

**Page order** (as of `0855634`):
```
[cover]  Year overview
For each month M:
  Month overview
  [orphan day pages: days in M whose week-Monday is in prior month]
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
3. `prepare_background(tree)` per master → write to temp dir
4. `fill_page()` per page → `(svg_str, links)`
5. `render_pdf()` — one HTML doc, Playwright prints PDF
6. `render_blanks()` — one PNG per master type

**Quick wins for next session:** fix #10, #12, #13 in one commit (all in `_fill_category` / `_fill_day` in `fill.py`) — the issue descriptions contain the exact code.
