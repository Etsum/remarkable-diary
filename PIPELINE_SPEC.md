# reMarkable Planner — SVG → PDF/Blank Generation Pipeline

**Audience:** Claude Code (or any engineer) implementing the deterministic generator.
**Author of source design:** the owner, in Figma. **Language:** Python 3.10+.

This document is the **build contract**. It supersedes the "Route A" stub in `HANDOVER.md`
and the linking notes in `SPEC.md` / `figma-export/NAMING.md` (read those for design
*intent*; read **this** for what to *build*). `Planner.html` is the **behavioural source of
truth** for all date logic and page content — when in doubt, open it and match its output.

> **Status of owner decisions:** all confirmed — see §2. Defaults below reflect them.

---

## 0. What we are building

Two deterministic outputs from the **six master SVGs** the owner authors in Figma:

1. **Hyperlinked PDF** — a multi-page planner for any date range, all dates / week numbers /
   mini-calendars filled in, every navigation link wired as a real internal PDF "go-to"
   jump. Configurable: start/end month, week-link target, four category section names, and
   how many category pages per category per month. Optional leading cover page.
2. **Blank write-on PNGs** — **one PNG per page type**, no dates, no category tabs and
   non-functional chrome stripped, with the **dot-grid writing texture present**, for
   handwriting directly on the device.

Both come from the *same* masters. The script's job is **date logic + filling named layers
+ dot-grid + links + assembly**. Nothing the SVG can provide is hand-placed by the script.

---

## 1. Architecture (read this first)

```
 Figma  ──export──▶  6 master SVGs (text NOT outlined, id attrs ON)
                          │
                          ▼
   ┌──────────────────────────────────────────────────────────────┐
   │  build.py                                                      │
   │   1. parse config (range, options, categories)                │
   │   2. compute the page list  (port of Planner.html date logic) │
   │   3. prepare-background(svg):  add dot-grid pattern to the     │
   │        writable zones (shared by PDF + blanks)                 │
   │   4. for each page:  clone master → REWRITE named <text> by id │
   │        → restyle active-month tab → record link rects          │
   │   5. render + assemble (+ optional cover) ─▶ planner-<range>.pdf│
   │   6. blanks: prepare-background → strip var-ink, category tabs,│
   │        footer-right, hdr-meta text → render 1 PNG/type         │
   └──────────────────────────────────────────────────────────────┘
```

**The key architectural fact (why the re-export matters):** Figma's current export has
**"Outline text" ON**, so every label and number is a vector `<path>` — there is *no text
to rewrite*. The pipeline depends on the owner **re-exporting with "Outline text" OFF** so
each value is a real `<text id="…">` node. Then the script can (a) read each field's exact
position/size/font/colour straight from the file and (b) overwrite its content. This makes
the **SVG self-describing**: nudge anything in Figma, re-export, and the script follows — no
coordinates or styles hard-coded in Python. (See §3.1 for exact export settings.)

**Design principle: mutate, don't redraw.** Prefer changing the *content* (and, where
noted, the *fill*) of an existing named node over drawing a fresh one — a mutated node keeps
the position, font, size, baseline, and colour the owner set in Figma. The only things the
script adds/restyles are the dot-grid texture (§10), the active-month tab (§8.7), and an
optional "today" dot.

---

## 2. Decisions & defaults (all confirmed by owner)

| # | Decision | Confirmed value |
|---|---|---|
| D1 | Re-export from Figma with **Outline text OFF**, **id attribute ON** | Yes — required |
| D2 | Page ordering | **Per-month blocks**: Year → for each month: Month → Week-block → Week-schedule → Day (each day) → category pages |
| D3 | Category names | **Set at build time** (script rewrites the 4 `rail-section-{1..4}` labels + category page titles). Default names `["Lists","Projects","Meetings","Scratchpad"]` |
| D4 | Category page count | **Same N per category, per month**, appended at the end of each month block. **Default N = 5** |
| D5 | Blank output | **One PNG per page type** (write-on template) |
| D6 | Blank rail / chrome | Keep month tabs (static, no active highlight); **remove** category tabs, `footer-right`; **clear** the text inside `hdr-meta` (keep the box so it's writable) |
| D7 | Render backend | **Playwright/Chromium** primary (links + fonts free); cairosvg+pypdf documented as the pure-Python alternative (§11.2) |
| D8 | Date range > 12 months | One Year page per 12-month window |
| D9 | **Dot-grid writing texture** | **Added at generation** (SVG `<pattern>` on computed writable zones); shared by PDF + blanks. Not authored in Figma. (§10) |
| D10 | **Cover page** | Not auto-designed. Config option inserts a customisable leading page; anchors are id-based so a cover never breaks links. (§7.3) |
| D11 | Week-schedule hours | Accept the baked 18-row grid as-is (no custom hour count) |

---

## 3. Inputs — the six master SVGs

The master SVGs live in `uploads/` (re-exported from Figma, text not outlined). All are
**1404 × 1872 px, portrait**, `viewBox="0 0 1404 1872"`, 1 unit = 1 px.

| # | File | Page type | var-ink? |
|---|---|---|---|
| 01 | `01-year.svg` | Year overview (12 mini-cals, 3×4) | yes |
| 02 | `02-month.svg` | Month grid (ISO-week rows × Mon–Sun) | yes |
| 03 | `03-week-block.svg` | Week, days-as-rows + right-hand boxes | yes |
| 04 | `04-week-schedule.svg` | Week, days-as-cols × hour rows | yes |
| 05 | `05-day.svg` | Day page + schedule + notes + mini-cal | yes |
| 06 | `06-category.svg` | Full-page dot grid (Lists/Projects/…) | none (all static) |

### 3.1 Required Figma export settings (per master)

- **Outline text: OFF** ← *critical* (gives real `<text>` nodes).
- **Include "id" attribute: ON** ← *critical* (gives the layer-name contract).
- **Include bounding box: OFF** (not needed; the viewBox defines the frame).
- **Ignore overlapping layers: OFF** (we need every node).

### 3.2 The two-group contract (already present)

- `#background` — static printed chrome (frames, rules, weekend shading, weekday names,
  hour labels, section/box titles, footers' static text). After dot-grid prep (§10) **this
  IS the blank template**.
- `#var-ink` — every date-dependent node. Absent on `06-category` (nothing varies).

### 3.3 Layer/id audit — final re-export verified ✅

I re-checked the final masters (`uploads/*-<hash>.svg`). **All critical checks pass:** real
`<text>` nodes (not outlined), **no duplicate ids**, `#background`/`#var-ink` split on all
six, counts correct, and a Feb-2026 content spot-check is right (`hdr-big=2`,
`hdr-month-name=February`, `mrow-1-weeknum=W5`, `mcell-r1c1-num=26`,
`hdr-right-weekday="MON · 月"`). One small cosmetic id-consistency fix remains (F9).

**✅ Present & correct:** `#background`/`#var-ink` split; `mcell-r{R}c{C}-num` ×42;
`mrow-{1..6}-weeknum` ×6; `day-mini-r{R}c{C}` ×42; `mini-{NN}-d-r{R}c{C}` ×504;
`ws-day-{1..7}-num/-wd`, `ws-hour-*` ×18; `wb-day-{1..7}-num/-wd`; rail
(`rail-index-chip`, `rail-month-{01..12}-bg/-label`, `rail-section-{1..4}-bg`); header
(`hdr-big`, `hdr-month-name`, `hdr-meta-top/-bottom`, toggle, checks); frame paths
(`day-schedule-frame`, `day-notes-frame`, `hdr-datebox-frame`, `cat-grid-frame`).

| ID | Status |
|---|---|
| F1 — year mini cells | **✅ Verified.** 504/504, no duplicate ids. (Earlier 499 undercount was duplicate layer names; resolved.) |
| F2 — `05-day` header in var-ink | **✅ Done.** `hdr-big`/`hdr-month-name`/`hdr-meta-*` now sit in `#var-ink`. |
| F3 — `01-year` range caption | **✅ Done.** `hdr-meta-top`/`-bottom` now in `#var-ink`. |
| F4 — active-month node | **✅ Intentionally removed** (keeps layer count down). Script restyles the existing `rail-month-{MM}-bg` + label for the active month (§8.7). |
| F6 — rail section bg rects | **✅ Done.** `rail-section-{1..4}-bg` (real rects) on every page — these are the link geometry. |
| **F9 — rail section *label* ids (NEW, minor)** | The section **label** text nodes are slot-numbered (`rail-section-{1..4}`) on `06-category` but still name-based (`rail-section-lists/-projects/-meetings/-scratchpad`) on month/week-block/week-schedule/day. **Recommend standardising** the four dated pages to `rail-section-{1..4}` (order: lists→1, projects→2, meetings→3, scratchpad→4). Cheap one-time rename. *(Or the generator targets `rail-section-{i}` and falls back to the name-based id — but standardising is cleaner.)* |
| F5 — link hit-rects | **Optional.** Script derives link geometry from content nodes + the `rail-*-bg` rects (§9). Optionally add `wb-day-{1..7}-link` rects for pixel-precise week-block links. |
| F7 — dot grid | **By design, added at generation** (§10) — no Figma action. |
| F8 — UTF-8 | Masters are UTF-8; script parses UTF-8. |

> Run the **pre-flight validator** (§12.1) on each re-export before a full build.

### 3.4 Fallback if "keep outlined" (not chosen)

If text ever stays outlined, the script can't rewrite values; it must draw all variable
text with reportlab from a hard-coded per-field style/coordinate table (ported from
`Planner.html`) over the SVG `#background`. Works, but every Figma nudge silently desyncs.
Not the chosen path.

### 3.5 Style & typography — the SVG export is the source of truth

Design is authored **only in Figma**. Colour and type are defined there as variables and
text styles and **exported** into the repo — the six master SVGs plus the token JSONs
(`assets/e-ink-palette.tokens.json`, `assets/Type_ Fonts/`, `assets/Type_ Properties/`).
There should **never** be a need to hand-edit the exported JSON or bake a style decision
into code; when a style changes, re-export from Figma.

Consequences for the generator:

- **The per-node SVG attributes are authoritative, not the token JSON.** Figma bakes each
  text element's full style (`font-family`, `font-size`, `font-weight`, `letter-spacing`,
  `fill`) onto its exported `<text>` node. The token JSON is design *reference*: it may
  declare font/colour variables that no text style actually uses, so it cannot tell you
  what is rendered. Treat `assets/*.tokens.json` as definitions; treat the master SVGs as
  the truth for how each element looks.
- **Code follows the design automatically — do not maintain a "which style" table.**
  `set_text()` rewrites only a node's text content and preserves every style attribute
  (`svgutil.py`). So filling a template node keeps its Figma style for free. Binding style
  by node id, by placeholder text, or by parsing the `.fig` are all the wrong direction:
  the export already carries it. (If a semantic style *name* is ever needed for validation,
  generate an `id → text-style` manifest from the Figma API — never hand-author one.)
- **The only explicit styling in code is data-dependent restyling** of an existing node —
  active rail tab, Sunday emphasis, adjacent-month fade, dot-grid texture. Those few
  overrides (`fill.py`, `background.py`) map onto the exported e-ink palette (§4). When the
  palette changes in Figma, update the export and these constants together; the SVG export
  stays the reference.

Fonts are served to the renderer from the bundled TTFs in `assets/fonts/` via
`fonts.py` `@font-face`, keyed by the exact family names the SVGs declare — so whatever
family Figma exports must have a matching bundled face, or it silently falls back
(issue #52).

---

## 4. What the OWNER must provide (action items)

> **⚠️ Superseded by the e-ink redesign (2026-07).** The specific faces and hex tokens in
> the tables below are historical owner-provided context from the original build. Type is
> now **Inter** (UI / labels / numbers), **Newsreader** (display headers) and **EB Garamond**
> (mini-cal month names); colour is the greyscale e-ink palette in
> `assets/e-ink-palette.tokens.json`. The authoritative style is always the Figma export per
> **§3.5** — the values below are kept only for provenance.

1. **Re-exported SVGs** per §3.1 with §3.3 (F2, F3) applied. Keep layer names unique.
2. **Font files (`.ttf`/`.otf`)** in `assets/fonts/` — the exact faces from Figma:

   | Family (as in Figma) | Weights | Used for |
   |---|---|---|
   | **IBM Plex Mono** | Regular, Bold | every number/date (660+ nodes) |
   | **Noto Sans** *(Display)* | Regular, Bold | headings, weekday names, labels, section/box titles |
   | **Noto Sans JP** | Regular | kanji (月, 火…) — always on via the CJK fallback chain (`fonts.py`); the `lang` option was removed (#31) |

   *(Historical, per the §4 banner: the original build used **IBM Plex Mono** for numbers
   and called EB Garamond unused. The e-ink redesign replaced this — see the current
   families in `fonts.py` and the banner above; EB Garamond is now used for mini-cal month
   names.)* All bundled faces are OFL — redistributable with the output.
3. **Tokens** — baked into the SVG; the script only needs them for nodes it restyles/draws:

   | Token | Hex | Use |
   |---|---|---|
   | ink | `#23262d` | default text |
   | navy | `#41587c` | active states, week #s, links |
   | maroon | `#9e5563` | Sundays, weekday chip |
   | faint | `#cbc9c4` | adjacent-month (greyed) day numbers |
   | weekend / weekendOff | `#dde0e5` / `#ecedf0` | weekend shading (cur / adjacent month) |
   | rail panel / index | `#edf0f5` / `#2c2c2c` | months strip / INDEX chip |
   | sand / sand-ink | `#dccfb0` / `#54492a` | box header fills / their text |
   | **dot / rule** | **`#c7c4be`** / `#e2dfda` | **dot-grid texture (§10)** / hairlines |

---

## 5. Configuration

JSON/TOML config + CLI flags. Suggested schema:

```jsonc
{
  "start": "2026-01",        // YYYY-MM inclusive (calendar/financial year, etc.)
  "end":   "2026-12",        // YYYY-MM inclusive   (or use "months")
  "months": 12,              // alt to "end": count from start
  "lang": "jp-en",           // "jp-en" (kanji + EN) | "en"
  "weeklink": "schedule",    // "schedule" | "block"  → where month Wn + day "↳ week" point
  "include": { "block": true, "schedule": true, "days": true },
  "categories": ["Lists", "Projects", "Meetings", "Scratchpad"],  // 4 slots, rail order top→bottom
  "pagesPerCategory": 5,     // SAME count for every category, per month (D4). 0 ⇒ none + tab unlinked
  "coverPage": false,        // false | "blank" | "path/to/cover.pdf|png"  (D10)
  "output": "planner-2026.pdf",
  "blanks": true             // also emit the 6 *-blank.png
}
```

- **`start`/`end`/`months`** → the range. Calendar year `2026-01..2026-12`; AU FY
  `2025-07..2026-06`; month-to-a-notebook `months:1`.
- **`weeklink`** = where the month `Wn` gutter + the day-page "↳ week" footer point. If the
  target week type isn't generated, fall back to the other; else render plain (port
  `Planner.html`'s `weekExisting`).
- **`categories`** = exactly 4 names, slot order = rail top→bottom. Default
  `["Lists","Projects","Meetings","Scratchpad"]`. Keep ≤ ~10 chars (rotated rail tabs).
- **`pagesPerCategory`** = one integer applied to all four (D4), default **5**. (If you
  ever want per-category counts, accept an int *or* a 4-array — but uniform is the spec.)
- **`coverPage`**: `false` = none; `"blank"` = one truly blank leading page to customise;
  a file path = use that PDF/PNG as page 1. Never changes anchors.

---

## 6. Date logic to port (from `Planner.html`)

Match `Planner.html`'s output exactly. Python is shorter — `date.weekday()` is Mon=0…Sun=6
and `date.isocalendar()` returns ISO year+week directly. Drop-in helpers:

```python
from datetime import date, timedelta

WD_LET = ["M","T","W","T","F","S","S"]
EN_WD  = ["MON","TUE","WED","THU","FRI","SAT","SUN"]
JP_WD  = ["月","火","水","木","金","土","日"]
EN_MON = ["January","February","March","April","May","June",
          "July","August","September","October","November","December"]
EN_MON_A = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

def dim(y, m):                       # days in month
    nm = date(y + (m == 12), (m % 12) + 1, 1)
    return (nm - date(y, m, 1)).days

def first_weekday(y, m):             # weekday of the 1st, Mon=0..Sun=6
    return date(y, m, 1).weekday()

def mon_monday(d):                   # Monday of d's week
    return d - timedelta(days=d.weekday())

def iso_week(d):                     # (iso_year, iso_week)
    y, w, _ = d.isocalendar()
    return y, w

def mini_rows(y, m):                 # 6-or-fewer week rows of a month
    first, days = first_weekday(y, m), dim(y, m)
    n = (first + days + 6) // 7      # 4, 5, or 6
    rows, dd = [], 1 - first
    for _ in range(n):
        wk = []
        for c in range(7):
            valid = 1 <= dd <= days
            wk.append({"d": dd if valid else "", "col": c, "valid": valid})
            dd += 1
        rows.append(wk)
    return rows
```

**Anchor (page-id) scheme** — computed so links never need page numbers:

| Page | Anchor id |
|---|---|
| Year (window k) | `year` (then `year-2`… for >12-month ranges) |
| Month | `month-YYYY-MM` |
| Week block / schedule | `week-<isoYear>-WW-b` / `-s` |
| Day | `day-YYYY-MM-DD` |
| Category | `cat-YYYY-MM-s<slot>-<NN>` (slot 1–4, NN = 01…pagesPerCategory) |

Build the `Set` of all anchors that will exist **first**, so any link to a non-generated
page degrades to plain text (port `Planner.html`'s `anchors` set + `weekExisting()`).

---

## 7. Page model & ordering

### 7.1 Order — per-month blocks (D2)

```
[ cover page ]                      # only if coverPage set (§7.3)
Year overview                       # one per 12-month window
For each month M in range (chronological):
    Month overview (M)
    For each week whose Monday falls in M (chronological):
        Week block      (if include.block)
        Week schedule   (if include.schedule)
    For each day in M:
        Day page        (if include.days)
    For slot i in 1..4:
        pagesPerCategory × Category page (slot i, month M)
```

Block-internal order is **Month → Week-block → Week-schedule → Day(s) → Categories**, as
confirmed.

### 7.2 Edge cases
- **Week→month:** a week belongs to the month of its **Monday** (deterministic; a week
  straddling month-end lands in the earlier month).
- **>12-month range (D8):** one Year page per 12-month window; its 12 minis show that
  window's months. A final partial window shows its months (rest blank).
- **`pagesPerCategory: 0`:** no category pages; rail tabs still drawn, just unlinked.

### 7.3 Cover page (D10)
If `coverPage` is set, prepend one page as page 1:
- `"blank"` → an empty 1404×1872 page (optionally a plain dot-grid) the owner customises
  later.
- a file path → embed that PDF page / PNG as page 1.
Because all internal links target **anchors (ids)**, not ordinals, a cover never breaks
them. Do **not** auto-design cover artwork.

---

## 8. Fill contract — what the script writes into each page

Clone the master, then set the **content** (and, where listed, the **fill**) of these
`#var-ink` nodes. Unlisted `#var-ink` nodes with no value here → set text `""`. Static
`#background` is untouched (except dot-grid prep, §10). Inherit position/size/font from the
node; override fill only where stated.

> **Colour override roles (e-ink redesign).** The data-dependent fills below now map onto
> the greyscale e-ink palette (`assets/e-ink-palette.tokens.json`), not the old navy/maroon.
> The `fill.py` constants: **Text/Primary `#000000`** (emphasis — active tab, Sunday/weekend,
> today), **Text/Secondary `#4d4d4d`** (regular day numbers), **Grid/Primary `#b8b8b8`**
> (faded adjacent-month numbers & dot grid), **Base `#ffffff`** (inverse text on dark chips).
> Everything else inherits the node's exported Figma style untouched (§3.5).

### 8.1 Year (`01-year.svg`)
| Node id(s) | Set to |
|---|---|
| `hdr-big` | start year (`2026`) |
| `hdr-month-name` | `Overview` |
| `hdr-meta-top` / `hdr-meta-bottom` | first / last month abbr of range (needs F3) |
| `mini-{NN}-label` / `-label-jp` | abbr + `M月` for `monthsList[NN-1]` |
| `mini-{NN}-d-r{R}c{C}` | day number from `mini_rows()` or `""`; **fill** Text/Primary if Sunday (col 6), else Text/Secondary |
| `footer-left` `YEAR 2026` · `footer-right` static |

### 8.2 Month (`02-month.svg`)
| Node id(s) | Set to |
|---|---|
| `hdr-big` month # · `hdr-month-name` `February` · `hdr-month-jp` `2月` |
| `hdr-meta-top` `YEAR` (static) · `hdr-meta-bottom` year |
| `mrow-{R}-weeknum` | `W`+ISO week of that row's Monday; `""` for unused rows |
| `mcell-r{R}c{C}-num` | day-of-month. **fill:** current month → Text/Secondary (Sun→Text/Primary); **adjacent month → Grid/Primary `#b8b8b8`** |

### 8.3 Week block (`03-week-block.svg`)
| Node id(s) | Set to |
|---|---|
| `hdr-big` ISO week # · `hdr-month-name`/`-jp` month of Monday · `hdr-meta-top` range `16–22` · `hdr-meta-bottom` year |
| `wb-day-{N}-num` | day-of-month (Mon=1…Sun=7) |
| `wb-day-{N}-wd` | `EN_WD[N-1]` (+JP) — constant; set or leave |
| toggle | **BLOCK** active: `hdr-toggle-block-bg` fill→Text/Primary `#000`, `hdr-toggle-block` text→white |

### 8.4 Week schedule (`04-week-schedule.svg`)
| Node id(s) | Set to |
|---|---|
| header | as 8.3 |
| `ws-day-{N}-num` / `-wd` | day-of-month / weekday |
| `ws-hour-pos-{01..18}` | hour labels — 18 positional-id rows, relabelled from `cfg.hour_start` (the old literal `ws-hour-5..22` ids were renamed in the e-ink redesign; see `_WS_HOUR_IDS`) |
| toggle | **SCHEDULE** active |

### 8.5 Day (`05-day.svg`)
| Node id(s) | Set to |
|---|---|
| `hdr-big` day-of-month (needs F2) · `hdr-month-name` month · `hdr-right-weekday` `MON · 月` |
| `hdr-meta-top` `WEEK` (static) · `hdr-meta-bottom` ISO week # |
| `day-mini-month` / `day-mini-year` | month name / year |
| `day-mini-r{R}c{C}` | mini-cal day numbers (fill rules as 8.1) |
| `day-mini-today` *(absent)* | not present in the e-ink master — the redesign dropped it; today is emphasised via Text/Primary fill on the cell (see `_fill_day`). Code still guards it via `idm.get`. |
| `footer-left` `2月 16, 2026` (JP month glyph) · `footer-right` static `↳ week` |

### 8.6 Category (`06-category.svg`) — per slot/month instance
| Node id(s) | Set to |
|---|---|
| `hdr-big` (title) | `categories[i]` name |
| meta line | `MMM YYYY · n/N` (month + index within the slot) — into the `hdr-meta-*` cells, else draw at the datebox |

### 8.7 Rail (every page)
| Node id(s) | Action |
|---|---|
| `rail-index-chip` | link only (§9) |
| `rail-month-{MM}-bg` + `rail-month-{MM}` | **active month:** bg fill→Text/Primary `#000`, label→white+bold. Others inherit. (Replaces F4.) |
| `rail-section-{i}` labels | set text → `categories[i]` on **every** page (D3). ≤10 chars. The masters are now **standardised**: labels are `rail-section-{1..4}` on all six templates (the old name-based `rail-section-lists/-projects/…` ids are gone). Labels are vertically rotated; `_center_rail_label(lbl, bg)` re-centres each along its tab's long axis so any-length name stays centred (#44). Unused tabs are blanked (#30). |

---

## 9. Link contract

Each link = `(rect in page coords) → (target anchor)`. While filling, collect `[(page_idx,
x, y, w, h, target)]`; resolve `target → page_idx`; emit at render/assembly (§11). Geometry
= the named **source node's bounding box** (no separate link layer needed, F5).

| Page | Source node (bbox) | Target |
|---|---|---|
| Year | `mini-{NN}-d-r{R}c{C}` (valid) | `day-YYYY-MM-DD` |
| Year | `mini-{NN}-label` | `month-YYYY-MM` |
| Month | `mrow-{R}-weeknum` cell | week page per `weeklink` (fallback) |
| Month | each day cell (`mcell-…-num` → cell box) | `day-YYYY-MM-DD` |
| Week block | `wb-day-{N}-num`+`-wd` union (or `wb-day-{N}-link`, F5) | `day-…` |
| Week sched | `ws-day-{N}-num`+`-wd` (header cell) | `day-…` |
| Day | `hdr-meta-*` cell | `year` |
| Day | `day-mini-r{R}c{C}` (optional) | `day-…` |
| All | `rail-index-chip` | `year` |
| All | `rail-month-{MM}-bg` (real rect) | `month-YYYY-MM` |
| All | `rail-section-{i}-bg` (real rect) | this month's `cat-YYYY-MM-s{i}-01` (none if N=0) |
| Header | `hdr-toggle-schedule-bg` / `-block-bg` | the sibling week page |
| Footer | `footer-right` bbox | `↳ year` / `↳ month` / `↳ week` (as `Planner.html`) |

Bounding boxes: Playwright route → `element.getBBox()` in-page; pure-Python route →
`svgelements`/`svgpathtools` (rects give x/y/w/h directly; frame paths are clean rects).

---

## 10. Dot-grid backgrounds (writable texture) — added at generation (D9)

In the original HTML every writable area had a fine dot grid; CSS backgrounds don't survive
SVG export, so it must be re-added. **Do it in code, once, as part of a shared
`prepare_background(svg)` step** used by both the PDF and the blanks.

**Dot-grid approach (proven).** Add one `<defs>` block of dot patterns and fill each
writable zone with a `<rect fill="url(#dotNN)">`. The exact pattern set + per-zone spacing
below is already worked out (it matches the original HTML densities). Copy the `<defs>`
as-is:
```xml
<defs>
  <pattern id="dot30" width="30" height="30" patternUnits="userSpaceOnUse" patternTransform="translate(16 16)"><circle cx="1.1" cy="1.1" r="1.1" fill="#c7c4be"/></pattern>
  <pattern id="dot26" width="26" height="26" patternUnits="userSpaceOnUse" patternTransform="translate(8 8)"><circle cx="1.1" cy="1.1" r="1.1" fill="#c7c4be"/></pattern>
  <pattern id="dot24" width="24" height="24" patternUnits="userSpaceOnUse" patternTransform="translate(10 10)"><circle cx="1.1" cy="1.1" r="1.1" fill="#c7c4be"/></pattern>
  <pattern id="dot23" width="23" height="23" patternUnits="userSpaceOnUse" patternTransform="translate(8 8)"><circle cx="1.1" cy="1.1" r="1.1" fill="#c7c4be"/></pattern>
  <pattern id="dot22" width="22" height="22" patternUnits="userSpaceOnUse" patternTransform="translate(11 11)"><circle cx="1.1" cy="1.1" r="1.1" fill="#c7c4be"/></pattern>
</defs>
```
For each zone insert a `<rect fill="url(#dotNN)">` into `#background` just above `page-bg`
(under the rules/labels/text). The current `uploads/` masters have the **frames** but not
the inner grid rects, so compute each grid rect from its frame (inset ~1px) or the listed
nodes.

**Zones → pattern** (densities from the original HTML):

| Zone | Geometry from | Pattern |
|---|---|---|
| Day schedule | `day-schedule-frame` (grid rect ≈ x133 y179 w1216 h1258) | `dot30` |
| Day notes | `day-notes-frame`, lower region below the "NOTES" title (≈ y1500) | `dot26` |
| Category grid | `cat-grid-frame` | `dot30` |
| Week-schedule cells | grid body below the day-header row (per `ws-day-{N}-hours`) | `dot22` |
| Week-block writing bands | `wb-left` (date columns/headers sit on top) | `dot23` |
| Week-block right boxes | each `wb-box-{name}` body, below its `-header-bg` | `dot23` |
| Month day cells | grid body: x from the week-number column's right edge to the right margin, y from the weekday-header bottom to the last row (from `month-vertical-rules` / `month-weekend-cols` bbox) | `dot24` |

Notes:
- Mini-calendars and the day-page mini get **no** dots (they're calendar grids).
- Dots render under cell borders, day numbers, and shading — insert the patterned rects
  *before* those nodes in document order (or give them a low `z` by DOM position).
- Because zones are computed from existing named frames, the dots **follow any layout nudge**
  you make in Figma — no new layers required.
- One global tweak point: change dot colour/size/opacity in the pattern; spacing in the
  table above.

**Figma alternative (not chosen):** a raster dot-tile image fill per region also survives
export compactly, but it's fiddly to align and duplicates the texture across files. Code is
cleaner here.

---

## 11. Rendering & assembly

Date logic, fill, links, and dot-grid are **backend-agnostic**. Pick one renderer.

### 11.1 PRIMARY — Playwright / Chromium (D7)

Chrome turns in-document `#anchor` links into PDF go-to jumps **for free**, embeds
`@font-face` fonts perfectly, and renders the SVG exactly as drawn. The owner already runs
Playwright (`GENERATE_PDF.md`).

1. Build **one** HTML document (all links resolve in a single print job):
   ```html
   <style>
     @font-face{font-family:'Inter';font-weight:400;src:url(assets/fonts/Inter/static/Inter-Regular.ttf)}
     /* …Inter 500/600/700, Newsreader, EB Garamond, Noto Sans, Noto Sans JP — see fonts.py */
     @page{size:1404px 1872px;margin:0}
     .page{width:1404px;height:1872px;position:relative;page-break-after:always;overflow:hidden}
     a.lnk{position:absolute;display:block}      /* invisible hit overlays */
   </style>
   <!-- optional cover page first -->
   <div class="page" id="year">…inline <svg>… + <a class="lnk" href="#day-2026-02-16" style="left/top/width/height">…</div>
   <div class="page" id="month-2026-02">…</div> …
   ```
   - Inline each **mutated + background-prepped** SVG. `<svg width=1404 height=1872>`.
   - Emit an absolutely-positioned `<a class="lnk" href="#target">` per link (§9), sized to
     the source bbox. Give each `.page` `id="<anchor>"`.
2. `page.goto(file_url); page.evaluate("document.fonts.ready"); page.pdf(path=out,
   prefer_css_page_size=True, print_background=True, margin=0)`.
3. ~500-page docs are large but fine in one job. **Do not split** — splitting breaks
   cross-page links.

### 11.2 ALTERNATIVE — cairosvg + pypdf (pure Python)

1. `pip install cairosvg pypdf`; make `.ttf`s discoverable by fontconfig (install to OS or
   set `XDG_DATA_HOME`).
2. Each mutated SVG → `cairosvg.svg2pdf(bytestring=svg, output_width=1404,
   output_height=1872)` → a 1404×1872-**pt** page (1px→1pt). cairosvg embeds glyph
   outlines, so the final PDF needs no fonts downstream.
3. Concatenate with `pypdf`; per page `add_named_destination(name=anchor, page_number=i)`;
   add links with `add_link(... rect=[x1,y1,x2,y2], ...)`.
4. **Coordinate transform** (PDF origin bottom-left): SVG `(x,y,w,h)` →
   `[x, 1872-(y+h), x+w, 1872-y]`.

### 11.3 Cover page insertion
Playwright: prepend a leading `.page` (empty, or with the cover image). cairosvg+pypdf:
prepend the blank/supplied page before page 1. Anchors unaffected.

---

## 12. Blank write-on PNGs (output #2, D5/D6)

**One PNG per page type:** `01-year-blank.png … 06-category-blank.png`. Produced by the
script (not a raw Figma export) so the dot grid and removals are consistent.

For each master:
1. `prepare_background(svg)` — add the dot grid (§10).
2. **Remove** `#var-ink` entirely (skip on `06`).
3. **Remove** the rail category tabs: delete `rail-sections` (the 4 `rail-section-{i}` +
   their bg rects). **Keep** `rail-months` + `rail-index-chip` (static; no active style).
4. **Remove** `footer-right` (the "↳ …" link text).
5. **Clear** the text inside `hdr-meta` (`hdr-meta-top`/`-bottom`) but **keep** the datebox
   frame/dividers so it's a writable field. *(If F2 isn't applied, also clear the day
   page's root-level `hdr-big`/`hdr-month-name` here.)*
6. Render to **PNG at 1404×1872** via `cairosvg.svg2png(... output_width=1404,
   output_height=1872)`. (Fonts must be discoverable — same as §11.2. For a reMarkable
   Paper Pro variant, also render at 1620×2160 if wanted.)

Result: no dates, no links, no category tabs, dot-grid present, writable header meta —
exactly the handwriting template.

---

## 13. QA / validation

### 13.1 Pre-flight (on the re-exported SVGs, before generating)
Assert per file: `#background` (and `#var-ink` where expected) exist; every id in the §8
tables resolves to `<text>`/`<rect>`; counts match (`mcell`×42, `mrow`×6, `day-mini`×42,
`mini-*-d`×504, `ws-hour`×18, `wb-day-*`×7, `ws-day-*`×7); **no duplicate ids** (F1). Fail
loudly listing any missing/duplicated id.

### 13.2 Post-build
- Click an INDEX chip, month tab, mini-cal date, week number, rail category tab
  → each jumps to the right page.
- A February mini links to `day-2026-02-…`; a category tab inside the March block lands on
  a **March** category page.
- Dot grid present in every writable area on both PDF pages and blank PNGs; absent from
  mini-cals.
- Grayscale-flatten one page; weekend shading + chips still read (e-ink).
- Blank PNGs: no numbers, no category tabs, no footer-right link, hdr-meta
  empty but framed, month rail present.
- Page count for a full year ≈ 1 year + 12 months + ~106 week pages (53×2) + 365 days +
  (4 × 5 × 12 = 240) category pages (+ cover, if any).

---

## 14. Gotchas
- **Outlined text breaks everything** — verify §3.1 each re-export; parse UTF-8 (F8).
- **Duplicate layer names** → Figma suffixes ids → strict lookups miss them. Keep unique;
  the validator (§13.1) catches it.
- **Week-schedule hour rows fixed at 18** (D11): relabel only.
- **Weeks straddling months** land in the Monday's month (§7.2).
- **Adjacent-month day numbers** must be recoloured faint (§8.2); the active-month tab
  (§8.7), the dot grid (§10), and the optional "today" dot are the only script-drawn/restyled
  elements.
- **Category names are rotated rail text** — long names overflow; validate length.
- **Don't split the PDF** (Playwright route) or links break.
- **`weekExisting` fallback** — if only one week type is built, week links fall back.

---

## 15. Suggested repo layout & milestones

```
planner-gen/
  build.py            # CLI: config → PDF + blanks
  dates.py            # §6 helpers (ported, unit-tested)
  background.py       # §10 prepare_background (dot grid)
  pages.py            # §7 model + §8 fill contract
  links.py            # §9 link table
  render_chrome.py    # §11.1   render_cairo.py  # §11.2 (pick one)
  blanks.py           # §12
  config.example.json
  assets/ masters/ 01-year.svg … 06-category.svg     fonts/ *.ttf
  out/
```

**Milestones**
1. Pre-flight validator (§13.1).
2. `dates.py` + golden tests vs `Planner.html` outputs.
3. `prepare_background` dot grid on one master → eyeball vs `Planner System.dc.html`.
4. Single-month fill → render → compare.
5. Links on that page → click-test.
6. Full per-month assembly + categories + range/options + cover.
7. Blanks (PNG).
8. End-to-end QA (§13.2).

---

### Appendix — current vs target category behaviour
`Planner.html` today appends 4 category pages once at the very end, rail tabs → single
`cat-*`. Target (D3/D4): categories **per-month**, **N each** (default 5), anchors
`cat-YYYY-MM-s{slot}-{NN}`, rail tabs → the **current month's** first page of that slot.
Everything else in `Planner.html` (date math, mini-cal, month grid, week/day pages,
fallback links) ports as-is.
