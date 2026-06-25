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

The build contract is **[`PIPELINE_SPEC.md`](PIPELINE_SPEC.md)**; design and
linking decisions are in [`SPEC.md`](SPEC.md) / [`HANDOVER.md`](HANDOVER.md).
Current status and design notes live in [`PROGRESS.md`](PROGRESS.md).

## How it works

```
Figma ── export ──▶ templates/*.svg   (text NOT outlined, id attrs ON)
                          │
                          ▼
   parse config → compute page list (ported date logic)
   → add dot-grid to writable zones → per page: clone master,
     rewrite named <text> by id, restyle active rail, record links
   → render one HTML, print to PDF (internal links) ; + blank PNGs
```

The masters are **self-describing**: each value is a real `<text id="…">` node
and each link source is a named node/frame, so nudging anything in Figma and
re-exporting keeps the generator in sync — no coordinates hard-coded in Python.

## Layout

```
templates/           the six master SVGs (01-year … 06-category) — generator input
fonts/               bundled faces: IBM Plex Mono, Noto Sans, Noto Sans JP
planner_gen/
  dates.py           date helpers + page model + anchor scheme   (§6/§7)
  config.py          config load/validate                        (§5)
  fonts.py           @font-face CSS + CJK fallback chain
  svgutil.py         lxml mutate helpers + path/group bbox()
  background.py      dot-grid writing texture                    (§10)
  # pending: geometry.py (links §9), fill.py (§8), render.py (§11), blanks.py (§12)
PIPELINE_SPEC.md     the build contract
PROGRESS.md          decisions, design-intent notes, status
```

Generated output (PDF/PNG) is written to `out/` and is **not** committed — it is
produced client-side. The SVG masters in `templates/` are tracked source.

## Requirements

- Python ≥ 3.14, managed with [uv](https://docs.astral.sh/uv/).
- Chromium for the renderer: `uv run playwright install chromium`.

```bash
uv sync                              # create env from pyproject.toml / uv.lock
uv run playwright install chromium   # one-time
```

## Status

Implemented and verified: date logic + page model, config, font loading,
SVG mutate helpers + bbox, and the dot-grid backgrounds. The fill contract,
link geometry, renderer and blank-PNG output are in progress — see
[`PROGRESS.md`](PROGRESS.md) and the issue tracker.

A full calendar year resolves to ~722 pages (1 year + 12 month + 52+52 week +
365 day + 240 category, default settings).

## Rendering backend

**Playwright/Chromium**, chosen for fidelity — exact fonts including mixed
Latin+kanji nodes (e.g. `MON · 月`), and internal links / bounding boxes for
free. It is kept behind a single swappable module so a future pure-Python
(cairosvg + pypdf) backend can drop in without touching the date / fill / link
logic.

> Fonts must be loaded via a real `file://` navigation (`page.goto`), not
> `set_content` — Chromium blocks `file://` font loads from an `about:blank`
> origin, which silently falls back to serif.

## Repository & issues

The canonical repo is GitHub `Etsum/remarkable-diary` (mirrored to a private
Gitea). Bugs and work items are tracked as GitHub issues.
