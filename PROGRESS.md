# Progress / build notes — reMarkable planner generator

Implements `PIPELINE_SPEC.md` (the build contract): six Figma master SVGs →
deterministic hyperlinked PDF + blank write-on PNGs, for any date range.

## Decisions made this session

- **Renderer: Playwright/Chromium** (spec D7), chosen for fidelity. Verified by
  rendering all six masters — IBM Plex Mono numerals, Noto Sans, and mixed
  Latin+kanji nodes (e.g. day `MON · 月`, footers like `2月 16, 2026`) all shape
  correctly via per-glyph fallback. Kept as a **swappable module** so a future
  pure-Python (cairosvg + pypdf) backend can drop in without touching date
  logic / fill / links. (Owner accepts this may be revisited later.)
- **Python tooling: uv** (`pyproject.toml`, `uv run`). Deps: `playwright`, `lxml`.
  Chromium installed via `uv run playwright install chromium`.
- **Masters live in `templates/`** (not `uploads/` as the spec text says) and the
  id contract re-export is **clean**: no duplicate ids, `#background`/`#var-ink`
  split on all six, `rail-section-1..4` slot-numbered on **every** page (spec F9
  resolved), `mini-NN-label`/`-label-jp` ×12 present, counts all match
  (`mini-*-d` ×504, `mcell` ×42, `mrow` ×6, `day-mini` ×42, `ws-hour` ×18, etc).
- **Fonts** are bundled in `fonts/` (IBM Plex Mono Regular/Bold; Noto Sans
  static Regular/Bold; Noto Sans JP static Regular/Bold) and served via
  `@font-face` from `file://` URIs.

## Design-intent notes (faithful to masters — differ from older spec §8, confirm)

The header is a **shared component** across all dated pages, so:
- **Day page** `hdr-big` = the **month number** (label "MONTH"), *not* the
  day-of-month. The day is identified by the big weekday (`MON · 月`), the footer
  (`2月 16, 2026`) and the mini-cal highlight. (Spec §8.5 expected day-of-month.)
- **Week pages** `hdr-big` = month number; the ISO week number is in the footer
  (`WEEK 8 · …`) + the SCHEDULE/BLOCK toggle. (Spec §8.3/8.4 expected week #.)
- **Category page** `hdr-big` = first letter of the category name ("L" for
  Lists); title = name; datebox = month/year.

These are one-line changes in `fill.py` if the owner wants the spec behaviour
instead — the architecture makes repointing trivial.

## Known bugs

Tracked as GitHub issues on the main repo (`Etsum/remarkable-diary`), issues
**#1–#7** — all code-owned (Figma masters need no changes). They map onto the
pending fill / blanks / dot-grid / renderer work below.

## Status — MVP COMPLETE ✓

All modules implemented and tested end-to-end:

- `planner_gen/dates.py` — §6 date helpers + §7 page model + anchor scheme.
- `planner_gen/config.py` — §5 config load/validate.
- `planner_gen/fonts.py` — `@font-face` CSS + CJK fallback chain.
- `planner_gen/svgutil.py` — lxml mutate helpers + `bbox()` for rect/path/group.
- `planner_gen/background.py` — §10 dot-grid injection (shared by PDF + blanks).
- `planner_gen/fill.py` — §8 per-page fill contract + §9 link geometry. Fills all
  var-ink nodes (dates, week numbers, mini-cal, hour labels, categories, active rail
  tab). Returns (svg_str, links) where links = [(x,y,w,h,target_anchor), ...].
  Link geometry uses `svgutil.bbox()` for rects/paths and font-size approximation
  for text nodes — accurate enough for click targets.
- `planner_gen/render.py` — §11.1 single-HTML assembly + Playwright PDF print.
  Also §12 blank write-on PNGs (one per master type). Blanks: var-ink removed,
  category tabs + nav arrows + footer-right stripped, hdr-meta text cleared,
  dot-grid present.
- `planner_gen/build.py` — CLI + §13.1 pre-flight validator + full orchestration.
  Validates masters (duplicate ids, required nodes, counts) before any build.

### Verified output

- Feb-2026 (1 month, 2 cat pages): 46 pages → 21 MB PDF in ~16s
- All 6 blank write-on PNGs at 1404×1872 with dot-grid, no dates, no category tabs
- Pre-flight validator passes all six masters

## Running the generator

```bash
# Pre-flight validation only
uv run python -m planner_gen.build --validate-only

# Generate a 1-month PDF (fast test)
uv run python -m planner_gen.build --start 2026-02 --months 1 --output out/feb2026.pdf

# Full year PDF + blank PNGs
uv run python -m planner_gen.build --start 2026-01 --months 12 --output out/planner-2026.pdf

# Blank PNGs only
uv run python -m planner_gen.build --blanks-only --output out/foo.pdf

# Via JSON config
uv run python -m planner_gen.build --config config.json
```
