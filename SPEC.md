# reMarkable Planner — design + linking spec

> **⚠️ Historical design notes.** Colour/style references here (navy 2px rule, maroon INDEX
> chip, etc.) describe the **original** iteration. The live design is the **e-ink greyscale
> palette** — see `PIPELINE_SPEC.md` §3.5 and `assets/e-ink-palette.tokens.json`. The
> **link contract** below is still accurate and useful; the colour cues are not. (`NAMING.md`
> referenced below no longer exists.)

Companion to `HANDOVER.md` / `NAMING.md` / `GENERATE_PDF.md`. Records the decisions made
about the **year-page calendar cells** and the **page-to-page link contract**, and where
each lives across the three artifacts.

> **The generator build contract is `PIPELINE_SPEC.md` (project root).** This file records
> design + linking *decisions*; the spec says what to *build*. Note since this was written:
> rail sections are now `rail-section-{1..4}`, category pages are **per-month** (configurable
> names + count, default 5), the dot-grid texture is **added at generation**, blanks are
> **PNG**, and Figma must export with **"Outline text" OFF**.

## The three artifacts (keep in sync)

| File | Role |
|---|---|
| `Planner.html` | **Working generator** — builds every page for a date range with real `<a href="#anchor">` links. Source of truth for behaviour + the PDF. |
| `Planner System.dc.html` | **Design reference** — single parametric page, click/Tweaks to switch view/date. Source of truth for layout, type, colour. |
| `uploads/*.svg` | **Named-layer master SVGs** (text not outlined, ids on) exported from Figma — the generator's input. Per-cell text layers + named frames carry the contract. |

---

## Decision: year mini-calendars use per-cell labelled cells (Option 1)

**Chosen: every mini-calendar cell is its own named/positioned layer** (`mini-NN-d-rRcC`),
created for **all 6 possible week-rows** of every month — not the geometry/anchor route.

### Why
1. **Even vertical rhythm across the whole page.** Every mini reserves the same **6 rows**
   of height regardless of whether a given month spans 4, 5 or 6 weeks. Months that start
   on a Sat/Sun and run 31 days (6 weeks) no longer push their neighbours out of
   alignment — all 12 minis are the same height and the 3×4 grid stays square.
2. **Per-date hyperlinks.** Each cell is an individually addressable target, so a single
   date on the year page can link straight to its **day page** (see below). The
   anchor/geometry route would have to synthesise these at generate-time; per-cell layers
   make the link a property of a real, nudgeable layer.
3. **Hand-tunable in Figma.** A single date can be restyled/nudged without touching code.

### Cost (accepted)
- One-off setup of the missing row/column labels so all minis are a full 6 rows. In Figma
  an empty text layer is illegal, so blank cells hold a `.` placeholder; **the generator
  overwrites every cell** — real day number for valid days, empty string for blanks — so
  the `.` is an authoring-only token and never appears in the PDF/PNG output.

> Fixed-height (6-row) minis are a *layout* decision (even spacing); per-cell labels are a
> *fill* decision (per-date links + hand-tuning). Option 1 takes both.

---

## Link contract (page → page)

Anchors are computed from the date (see `PIPELINE_SPEC.md` §6): `year`, `month-YYYY-MM`,
`week-<isoYear>-WW-s` (schedule) / `-b` (block), `day-YYYY-MM-DD`, and per-month category
pages `cat-YYYY-MM-s{slot}-{NN}`.

| From | Tap target | Goes to | Notes |
|---|---|---|---|
| **Year** | a single **date** in any mini | that **day page** | per-cell link; primary year-page action |
| **Year** | the mini's **month name** | that **month page** | secondary |
| **Month** | the **Wn** week-number (left gutter) | that **week page** | **schedule by default, configurable** |
| **Week block** | the rotated **date column** only (not the grid) | that **day page** | hit area = the date column; dot grid fills the rest |
| **Week schedule** | the **date header cell** | that **day page** | unchanged |
| **Day** | nav arrows / footer / rail | prev-next / week / index | unchanged |

### Configurable week-number target
`Planner.html` URL param **`weeklink`** = `sched` (default) | `block`. Controls where the
month **Wn** gutter and the day-page "↳ week" footer point. In `Planner System.dc.html`
the same choice is the **`weekLinkTarget`** prop (`week-schedule` default / `week-block`).
If only one of the two week page types is generated, the link falls back to whichever
exists so it never dangles.

### Week-block date column
Each day band is split into two columns: a **narrow date column** on the left holding the
date + weekday **rotated 90° (vertical)**, styled like the week-schedule column header
(mono date numeral, small weekday, navy 2 px rule on its inner edge); and the **dot-grid
writing column** filling the rest of the band width. **Only the date column is the link**
— the writing grid is never a hit target.

---

## Index rail (updated — larger touch targets + higher contrast)

Per the Figma edit, the rail was enlarged for on-device tapping and e-ink contrast:
- **Wider** rail column (54 → 66 px).
- **INDEX chip** is larger and **near-black `#2c2c2c`** (was small + maroon) — much higher
  greyscale contrast; label 15 px.
- The 12 months sit on **one continuous cool-grey panel `#edf0f5`** (was individual warm
  pills with gaps) so the whole strip reads as one tall tap column; the active month is a
  filled navy cell.
- Section tabs are now `rail-section-{1..4}` (labels) + `rail-section-{1..4}-bg` (real
  rects). The generator sets each label's **text at build time** (default Lists / Projects
  / Meetings / Scratchpad) and links slot _i_ to the **current month's** first category
  page; each category gets _N_ pages per month (default 5).

### SVG layer additions for the contract
The Figma round-trip did **not** preserve the planned `*-link` hit-rects, and that's fine:
the generator derives each link's geometry from the named **content** nodes and frames
instead (see `PIPELINE_SPEC.md` §9). Specifics:
- Year: link geometry from each valid `mini-NN-d-rRcC` cell → `day-YYYY-MM-DD`; from
  `mini-NN-label` → `month-YYYY-MM`.
- Month: from the `mrow-R-weeknum` cell → `week-…` (per `weeklink`); each day cell → day.
- Week block: from the `wb-day-N-num`/`-wd` union (the date column). Optionally add
  `wb-day-N-link` fill-none rects for pixel-precise hit areas.
- Rail: `rail-month-NN-bg` and `rail-section-{1..4}-bg` are real `<rect>`s used directly as
  link geometry; the active month is shown by **restyling** `rail-month-NN-bg` + label (no
  separate active layer).
- **Dot-grid** writing texture is added at generation (not a Figma layer).
