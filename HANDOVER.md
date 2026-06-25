# reMarkable 2 Planner System — Handover

A working brief for a fresh chat session. Goal: a set of planner templates for the
reMarkable 2 (and reMarkable Paper Pro), produced two ways:

1. **Blank PNG backgrounds** — one per page type, to set as a notebook template and
   write on directly.
2. **Fully hyperlinked PDF** — self-contained, page numbers + internal links computed
   from a date range (e.g. calendar year, financial year, "month-to-a-notebook").

> **Pipeline is now decided & specified — see `PIPELINE_SPEC.md` (project root).** Route A
> (Figma named-layer SVG → Python) is chosen. The masters live in `uploads/` (the owner's
> re-exported, text-not-outlined SVGs); `figma-export/NAMING.md` is the Figma-authoring
> contract. The sections below are the original brief, kept for context.

Inspired by the Bullet Journal method and Hobonichi Techo, but **practicality over
purism** — functional fit for the owner, not a faithful BuJo clone.

---

## Current artifact

**`Planner System.dc.html`** — a parametric reference implementation of all five page
types in one file. Open it directly; use the top toolbar (or the Tweaks panel) to switch
view and step the date. This is the *design source of truth* — match its layout, spacing,
type, and colour. It is NOT necessarily the final generation tool (see Pipeline below).

It renders from six parameters: `view, year, month, day, lang, hourStart/hourEnd`. All
dates, week numbers, weekend shading, and mini-calendars are computed — nothing is
hand-placed. Date logic lives in `renderVals()`: ISO week numbers, Monday-start grids,
leading/trailing greyed days, 12 mini-calendars.

---

## Canvas & device

- **Page size: 1404 × 1872 px, portrait** (reMarkable 2, 226 mm tall, ~226 DPI).
  Also valid for Paper Pro at the same aspect if needed.
- Greyscale e-ink on-device; PDFs render in colour in desktop/mobile apps.
- **Toolbar is ~104 px** and can sit left or right. Nav links are kept clear of it.

## The five page types

1. **Year overview** — 12 mini-calendars, 3×4 grid, Monday-start, Sundays accented.
   Customisable start/end month (calendar year, financial year, etc.). Title block +
   Q1–Q4 box. Each mini links to its Month page.
2. **Month overview** — rows = ISO week numbers (`W5`…), columns = Mon–Sun. Grid
   background inside each cell, weekends shaded, adjacent-month days greyed. Big day
   number top-left of each cell.
3. **Week block** — Mon–Sun as rows, left ~2/3 width (grid background for notes); right
   ~1/3 = customisable boxes: **Active Projects / Tasks / Discuss · Follow-up**.
   SCHEDULE/BLOCK toggle in header.
4. **Week schedule** — days as columns, hours as rows. Customisable start/finish
   (default 5am–10pm; "early/late" framing). Half-hour dotted sub-lines, weekends shaded.
5. **Day page** — big date + month + week + quarter chips, nav arrows, 4 checkboxes;
   full-width hourly schedule (dot grid, customisable hours); NOTES box bottom-left +
   mini month calendar bottom-right.

## Right-hand nav rail (all pages)

Vertical strip, **right side** (currently fixed; making side a parameter is an open item).
Top→bottom: maroon **year chip** → months **1–12** (current month filled navy) → section
tabs **LISTS / MEETINGS / PROJECTS / SCRATCHPAD**. In the PDF these become internal links.

---

## Design system

**Fonts — reMarkable system faces only** (embed the actual device fonts in the PDF):
- **Noto Sans** — all headings, labels, weekday names, section tabs, box headers. (User
  decided sans for headings, not serif.)
- **IBM Plex Mono** — every number / date: calendar days, week numbers, hour labels,
  the big day digit, year chip. Tabular feel, grid-aligned. (Retuned from Noto Sans Mono
  in Figma — this is the mono face to embed.)
- **Noto Sans JP** — kanji (`月`, `月火水木金土日`); `lang` switches `jp-en` ↔ `en`.
  (EB Garamond is no longer used.)

**Colour — must read in greyscale (e-ink):**
- Ink text `#23262d`; primary navy `#41587c` (filled headers/chips, active state);
  maroon `#9e5563` (year chip, Sunday accent); sand `#dccfb0` (box headers).
- Accent colours are only ever used as **filled chips with white text**, so they survive
  greyscale (white reads on any dark). The reliable greyscale cue for weekends is the
  **shading**, not the Sunday colour.
- **Weekend shading `#dde0e5`** (~12% grey) — deliberately darker than near-white so it's
  visible on e-ink. Off-month weekend `#ecedf0`. Verified against a greyscale pass.
- Grid/dot backgrounds: dots `#c7c4be`, square grid `#e9e6e0` — visible but quiet.

**Other conventions:** Monday week start; ISO week numbers; dot grid wherever you write,
square grid for calendar/time cells.

---

## Pipeline — the important decision

**The owner wants to move OFF an LLM for design changes.** The template changes rarely
once set, but must stay tweakable by hand. Preferred direction:

- **Author the static templates in a WYSIWYG tool (Figma) with named layers/groups**, then
  generate deterministically with a script the owner runs themselves — no LLM in the loop.
- **PNGs are blank** (just the printed background). **PDF generation injects** all the
  dates, page numbers, and hyperlinks from a date range.

**Can Figma do parametric design?** Not natively — Figma is static vectors. There are
data/plugin workarounds, but **it doesn't need to be parametric**: the PNG is blank, and
the PDF generator handles all the variable content. So the clean split is:
**Figma = visual editor for the static skeleton → script = deterministic generator.**

**Two viable generator routes — keep open, pick by maintenance taste:**

| Route | How | Pros | Cons |
|---|---|---|---|
| **A. Named-layer SVG → Python** | Export each page from Figma as SVG with `id`-named layers; Python (e.g. `svglib`/`reportlab` or `lxml` + `cairosvg`) clones the skeleton per page, fills date text nodes, writes `<a>` link rects, concatenates to PDF. | Fully WYSIWYG editing in Figma; no LLM; explicit control. | Owner maintains the date logic + naming contract in Python. |
| **B. HTML print-to-PDF** | The parametric HTML (like the current DC) renders each page with real `<a href="#anchor">` links; Chrome headless print preserves internal links as PDF GoTo jumps. | One source; links "just work"; no SVG round-trip. | Editing means touching HTML/CSS, which is closer to code. |

The current DC is essentially **Route B already**. **Route A is now the chosen, specified
path** — the named-layer SVGs exist (`uploads/`) and the full build
contract is in **`PIPELINE_SPEC.md`** (date logic port, fill + link tables, dot-grid,
render backends, blank PNG output). The decisive constraint: **export from Figma with
"Outline text" OFF** so values stay as real `<text>` nodes the script can rewrite.

**Hyperlink/anchor scheme (both routes):** every page gets a computed id — `year`,
`month-02`, `week-08`, `day-2026-02-16`. Rail months/sections and footer cross-links point
to those ids. Page numbers and the id map are derived from the chosen date range.

---

## Open items / next steps

1. **Weekly Review page** (BuJo migration step) — decide between a dedicated page
   (reflect + migrate list) vs. a "carry-over from last week" strip in the Week-block
   right column.
2. **Rail side** — make left/right a parameter (currently right-only).
3. **Build the generator** from `PIPELINE_SPEC.md`.

_Resolved:_ SVG export + layer-naming contract (done — `NAMING.md`); financial-year /
custom range (specified — `start`/`end`/`months` config); fonts to embed (IBM Plex Mono,
Noto Sans, Noto Sans JP); category sections (per-month, configurable names + count).

## Files

- `PIPELINE_SPEC.md` — **the build contract** for the generator (read this first).
- `Planner System.dc.html` — parametric reference (all 5 page types).
- `Planner.html` — working HTML generator (behavioural source of truth for date logic).
- `figma-export/NAMING.md` — Figma authoring + layer/id contract.
- `HANDOVER.md` / `SPEC.md` — this doc / design + linking decisions.
- `uploads/*.svg` — the owner's Figma masters; `uploads/*.png` — original design refs.
