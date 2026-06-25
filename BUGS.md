# Bug tracker

Observed from the rendered master PNGs in `out/`. **Owner** is whoever best
fixes it: **code** (generator change) or **figma** (edit `rm2.fig` + re-export).

> All seven are **code-owned** — the Figma masters are authored correctly. Most
> are generator behaviours not yet implemented (the fill/dot-grid/blanks steps
> are still pending); #7 is a render-path bug now root-caused. No `rm2.fig`
> changes are required.

| # | Bug | Owner | Status | Fix |
|---|-----|-------|--------|-----|
| 1 | Year overview: FEB rail tab shaded as "active" — there is no active month on the year page, all 12 month tabs should look identical | **code** (me) | open | `fill.py`: normalise the rail every page — reset all `rail-month-NN-bg` + labels to the inactive style, then apply the active style only to `active_month`. Year page → `active_month=None` → all inactive. (The master ships FEB as a sample-active state; the generator must own active styling. Figma alt: ship a neutral rail — but code normalisation is more robust.) |
| 2 | `hdr-nav` (prev/next arrows) shows on PNG exports — PNGs have no hyperlinks so nav chrome is meaningless | **code** (me) | open (spec §12.4) | `blanks.py`: remove the `hdr-nav` group (the `‹`/`›` arrows + their hit rects) when emitting blank PNGs. |
| 3 | Year overview: `.` placeholder shows in mini-cal cells that have no date (e.g. days before the 1st) | **code** (me) | open (spec line 43) | `fill.py`: overwrite **every** `mini-NN-d-rRcC` cell — real day number for valid days, **empty string** for blanks. The `.` is a Figma authoring token (empty text layers are illegal) and must never reach output. Same for `day-mini-rRcC`. |
| 4 | `footer-right` (the "↳ …" link text) shows on PNG exports — no hyperlinks in PNGs | **code** (me) | open (spec §12.5) | `blanks.py`: remove `footer-right` when emitting blank PNGs. |
| 5 | Month page: the 6th week-number row shows the placeholder `W-` instead of a real week number — the grid is always 6 rows so all 6 should be numbered | **code** (me) | open | `fill.py`: the month grid is a fixed 6-row grid starting at `mon_monday(1st)`. Compute and set all 6 `mrow-N-weeknum` = `W{iso_week}` for each row's Monday (e.g. Feb 2026 → W5…W10). No row left blank. |
| 6 | Dot-grid writing texture is missing entirely on every template (writable zones are blank white) | **code** (me) | open (spec §10, D9) | `background.py`: `prepare_background()` injects the `<pattern>` defs + a patterned `<rect>` into `#background` for each writable zone (day schedule/notes, category grid, week-schedule cells, week-block bands/boxes, month day cells), computed from the named frames. Shared by PDF + blanks. By design this is added at generation, not authored in Figma. |
| 7 | All PNGs render Latin text in a **serif fallback** — IBM Plex Mono / Noto Sans are not applied | **code** (me) | **root-caused** | The preview rendered via Playwright `set_content`, whose `about:blank` origin **blocks `file://` font loads**, so `@font-face` silently failed → serif fallback. Fix (lands in `render.py`): write the combined HTML to disk and `page.goto(file://…)` so same-origin `file://` font URIs load, then `await document.fonts.ready`. Verified: via `goto(file://)` `IBM Plex Mono` (regular+bold) and `Noto Sans` load and render correctly (`out/02-month-goto.png`). Alternative: embed the TTFs as base64 `data:` URIs (bulletproof, larger HTML). |

## Notes
- #1, #3, #5 are part of the **fill contract** (`fill.py`, task #5) — not yet written.
- #2, #4 are part of the **blank PNG** step (`blanks.py`, task #7) — not yet written.
- #6 is the **dot-grid** step (`background.py`, task #4) — not yet written.
- #7 must be baked into the **renderer** (`render.py`, task #6): never use
  `set_content` for the real render; always `goto(file://)`.
