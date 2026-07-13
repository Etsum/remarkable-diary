# remarkable-diary

A deterministic generator for a **reMarkable** planner: from six hand-authored
Figma master SVGs it produces a **hyperlinked PDF** for any date range and a set
of **blank write-on PNG templates** — same masters, no LLM in the loop.

- **Hyperlinked PDF** — every date, week number and mini-calendar filled in;
  every navigation link (rail, mini-cal dates, week numbers, nav arrows,
  footers) wired as a real internal PDF go-to jump. Configurable range,
  week-link target, four category sections, pages-per-category, optional cover.
- **Blank PNGs** — one per page type, no dates/links, dot-grid present, for
  handwriting directly on the device.

## Requirements

- Python ≥ 3.14
- [uv](https://docs.astral.sh/uv/) — install with `pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`

## Quick start

```bash
git clone git@github.com:Etsum/remarkable-diary.git
cd remarkable-diary

uv sync                                        # create venv, install deps
uv run playwright install chromium             # download Chromium (one-time, ~150 MB)
uv run playwright install-deps chromium        # system libs (one-time, Linux only — needs sudo)

# Pre-flight check (validates all six SVG masters)
uv run python -m planner_gen.build --validate-only

# Generate a 1-month PDF for quick smoke-testing
mkdir -p tmp
uv run python -m planner_gen.build --start 2026-07 --months 1 --output tmp/test.pdf

# Full year
uv run python -m planner_gen.build --start 2026-07 --months 12 --output tmp/planner.pdf

# Blank write-on PNGs only
uv run python -m planner_gen.build --blanks-only --output tmp/blanks.pdf
```

Generated output goes to `tmp/` (not committed).

## Build in the cloud (manual GitHub Actions run)

The SVG→PDF render (headless Chromium) can be run on GitHub's runners instead of
on-device, so per-build parameters stay out of committed config files. The
workflow is **manual-only** — it has a single `workflow_dispatch` trigger and
never runs on push, PR, or a schedule.

To run it: **Actions ▸ "Build planner (manual)" ▸ Run workflow**, fill in the
inputs (they map 1:1 onto the CLI flags — `start`, `end`/`months`, `cover`,
`no-*` toggles, etc., or paste a full JSON config into `config_json` to override
them), and start it. The PDF and any blank PNGs are uploaded as a
`planner-build-<run_id>` artifact (14-day retention). CLI equivalent:

```bash
gh workflow run build-planner.yml -f start=2026-07 -f months=12
```

## CLI reference

```
--config PATH          JSON config file (overrides other flags if present)
--start YYYY-MM        First month (required unless --config given)
--months N             Number of months to generate (default: 12)
--end YYYY-MM          Alternative to --months (inclusive)
--output PATH          Output PDF path (default: out/planner.pdf)
--weeklink schedule|block  Where week-number links point (default: schedule)
--hour-start H         First hour on week-schedule pages, 24h (default: 5)
--pages-per-category N Category pages per slot per month (default: 5)
--dot-scale F          Dot-grid tile size scale factor (default: 0.8; 1.0 = original density)
--cover PATH|blank     Cover page: 'blank' or path to a PDF/PNG
--no-blanks            Skip blank PNG output
--no-block             Skip week-block pages
--no-schedule          Skip week-schedule pages
--no-days              Skip day pages
--blanks-only          Render one blank PNG per page type; no PDF
--validate-only        Pre-flight check only; exit 0 if all masters pass
--templates-dir PATH   Override SVG master directory (default: assets/templates/rm2/)
```

JSON config keys mirror the flags: `start`, `end`, `months`, `output`, `weeklink`,
`hourStart`, `pagesPerCategory`, `dotScale`, `coverPage`, `blanks`, `include` (object with
`year`/`block`/`schedule`/`days` booleans), `categories` (array of 1–4 strings).

## How it works

```
Figma ── export ──▶ assets/templates/*.svg   (text NOT outlined, id attrs ON)
                              │
                              ▼
   parse config → compute page list (date logic)
   → add dot-grid to writable zones → per page: clone master,
     rewrite named <text> by id, restyle active rail, record links
   → render one HTML, print to PDF (internal links) ; + blank PNGs
```

The masters are **self-describing**: each fillable value is a real `<text id="…">`
node. Nudge anything in Figma, re-export the SVG, and the generator picks it up
with no code changes.

## Repository layout

```
assets/
  templates/       six master SVGs (01-year … 06-category) — generator input
  fonts/           bundled faces: Inter, Newsreader, EB Garamond, Noto Sans, Noto Sans JP
src/               Python package (importable as planner_gen)
  dates.py         date helpers + page model + anchor scheme   (§6/§7)
  config.py        config load/validate                        (§5)
  fonts.py         @font-face CSS + CJK fallback chain
  svgutil.py       lxml mutate helpers + path/group bbox()
  background.py    dot-grid writing texture                    (§10)
  fill.py          per-page fill + link geometry               (§8/§9)
  render.py        Playwright PDF + blank PNG renderer         (§11/§12)
  build.py         CLI entry point + pre-flight validator      (§13)
PIPELINE_SPEC.md   the build contract
SPEC.md            design intent
PROGRESS.md        decisions, open issues, architecture notes
```

## Updating the masters

The six SVGs in `assets/templates/` are exported from Figma (`rm2.fig`).
Export requirements:

- **Do not outline text** — the generator rewrites `<text>` nodes by `id`
- **Include `id` attributes** — every named layer must carry its Figma id
- Export as SVG (not optimised / minified)

After exporting, run `--validate-only` to confirm all required ids are present.

## Page count

A 12-month range resolves to ~722 pages with default settings:
1 year overview + 12 month + 52 week-block + 52 week-schedule + 365 day + 240 category (4 sections × 5 pages × 12 months).

## Rendering backend

**Playwright/Chromium** — chosen for font fidelity (Inter / Newsreader / EB Garamond,
mixed Latin+kanji) and native internal-link support. Kept behind a single swappable module
(`render.py`) so a future pure-Python backend can drop in.

> Fonts must be loaded via a real `file://` navigation (`page.goto`), not
> `set_content` — Chromium blocks `file://` font loads from an `about:blank`
> origin, falling back silently to serif.

## Issues

Bugs and work items are tracked as [GitHub issues](https://github.com/Etsum/remarkable-diary/issues).
Issues are tagged `owner: code` (fix in `src/`) or `owner: design` (fix in Figma then re-export).
