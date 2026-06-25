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

## Status

Done & tested:
- `planner_gen/dates.py` — §6 date helpers + §7 page model + anchor scheme.
  Self-test passes: full 2026 = 1 year + 12 month + 52+52 week + 365 day + 240
  category pages; Feb-2026 mini = 5 rows (only Sun=1 in row 1); ISO week 8 etc.
- `planner_gen/config.py` — §5 config load/validate (range, lang, weeklink,
  include, categories, pagesPerCategory, coverPage, blanks).
- `planner_gen/fonts.py` — `@font-face` CSS + CJK fallback chain.

Remaining (next session):
- `svgutil.py` — lxml mutate helpers (set tspan text, set fill, remove, defs).
- `geometry.py` — §9 link rects derived analytically from named nodes/frames/grids.
- `background.py` — §10 dot-grid injection (shared by PDF + blanks).
- `fill.py` — §8 per-page fill contract + active-month restyle + section labels.
- `render.py` — §11.1 assemble one HTML, `<a>` overlays, `page.pdf()`; PNG screenshots.
- `blanks.py` + `build.py` (CLI) + §13.1 pre-flight validator.

## Running what exists

```bash
uv run python - <<'PY'   # date-model sanity
from planner_gen.config import Config
from planner_gen import dates as D
pages, anchors = D.build_pages(Config(start_y=2026, start_m=1, months=12, pages_per_category=5))
print(len(pages), "pages,", len(anchors), "anchors")
PY
```

Preview the six masters (writes PNGs to `out/`): render each `templates/*.svg`
inside an HTML shell with `planner_gen.fonts.font_face_css` and screenshot the
`<svg>` at 1404×1872.
