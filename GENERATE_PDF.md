# Generating the PDF — Python / Playwright handoff (legacy HTML route)

> **Canonical pipeline is now `PIPELINE_SPEC.md`** (Figma named-layer SVG → Python). This
> doc describes the older **HTML route (Route B)** built on `Planner.html`. Keep it as a
> zero-setup fallback and as the **behavioural reference** for the date logic — and note
> the Playwright recipe below is exactly the rendering backend the SVG route reuses
> (§11.1 of the spec), just fed mutated SVGs instead of `Planner.html`.

`Planner.html` is the **behavioural source of truth**: open it in Chrome and it builds every
page for a date range, with real internal `<a href="#anchor">` links already wired. Two ways
to get a PDF from it:

## A. One-off, by hand (no code)
1. Open `Planner.html` in Chrome (double-click, or `file:///…/Planner.html`).
2. **Cmd/Ctrl+P → Save as PDF.**
3. In the dialog set: **Margins = None**, **Scale = 100%**, **Paper size = (matches the
   1404×1872 CSS @page automatically)**, and **Background graphics = ON**.
   ⚠ Background graphics MUST be on — the dot grids and weekend shading are CSS
   backgrounds and won't print otherwise.
4. Internal links (rail tabs, mini-calendar days, week numbers, nav arrows, footers)
   carry into the PDF as clickable GoTo jumps.

## B. Deterministic, scripted (Playwright — the route you wanted)
```python
# pip install playwright && playwright install chromium
import pathlib
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).parent.resolve()
SRC  = (HERE / "Planner.html").as_uri()

# pick the range with URL params (see "Config" below)
URL = SRC + "?year=2026"            # full calendar year 2026
OUT = HERE / "planner-2026.pdf"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(URL, wait_until="networkidle")
    page.evaluate("document.fonts.ready")          # ensure Noto fonts loaded
    page.pdf(
        path=str(OUT),
        prefer_css_page_size=True,                 # use the @page 1404x1872
        print_background=True,                     # <-- dot grids + shading
        margin={"top":"0","right":"0","bottom":"0","left":"0"},
    )
    browser.close()
print("wrote", OUT)
```
`print_background=True` is the scripted equivalent of "Background graphics = ON".
Chromium preserves the in-page `#anchor` links as internal PDF links — open the result
and click a month tab to confirm.

## Config (URL params on `Planner.html`)
| param | default | meaning |
|---|---|---|
| `year` | `2026` | calendar year (Jan–Dec) |
| `start` | — | `YYYY-MM` start, overrides `year` (e.g. financial year `?start=2025-07&months=12`) |
| `months` | `12` | number of months to generate |
| `lang` | `jp-en` | `jp-en` (kanji + EN) or `en` |
| `hours` | `5-22` | week-schedule / day start–end hour |
| `block` | `1` | include week-block pages (`0` to omit) |
| `sched` | `1` | include week-schedule pages |
| `days` | `1` | include the 365 day pages |

Examples:
- Full 2026 calendar year: `?year=2026`
- AU financial year 25/26: `?start=2025-07&months=12`
- Light build (no day pages): `?year=2026&days=0`
- Early-riser hours: `?year=2026&hours=4-21`

## Anchor scheme (what the links point at)
- `year` · `month-YYYY-MM` · `week-<isoYear>-WW-b` (block) / `-s` (schedule) · `day-YYYY-MM-DD`

Every page id is computed from the date, so the link graph is consistent for any range —
add/remove page types via the params and links self-heal (a link to an omitted page
silently renders as plain text instead of a dead link).

## Notes
- Page count for a full year ≈ **484** (1 year + 12 months + ~53 weeks ×2 + 365 days).
  Large builds take a few seconds to render and a chunky PDF — expected.
- To embed the device's exact font files instead of Google Fonts, swap the `<link>` in
  `Planner.html`'s `<head>` for `@font-face` rules pointing at local `.ttf`s (Noto Sans,
  Noto Sans Mono, Noto Sans JP) — Playwright will embed whatever the page loads.
- Design edits live in one place: the body-builder functions + token vars at the top of
  the `<script>` in `Planner.html`. Change a colour/size once, every page follows.
