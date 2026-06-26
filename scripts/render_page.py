"""Render a single planner page (or the 6 blanks) to tmp/ for quick visual checks.

Avoids the ~25-min full build when verifying a one-page fix. Used by the
plan -> act -> verify loop on individual issues.

Examples
--------
uv run python scripts/render_page.py --start 2026-07 --months 12 --kind year
uv run python scripts/render_page.py --start 2026-07 --months 12 --kind month --ym 2027-01
uv run python scripts/render_page.py --start 2026-07 --months 12 --kind day --date 2027-01-15
uv run python scripts/render_page.py --blanks            # 6 blank PNGs
"""
from __future__ import annotations

import argparse
import tempfile
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _render_svg(svg: str, css: str, out: Path, W: int, H: int) -> None:
    from playwright.sync_api import sync_playwright

    html = (f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{css}</style>'
            f'</head><body><div class="page">{svg}</div></body></html>')
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html); tmp = Path(f.name)
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            pg = b.new_page(viewport={"width": W, "height": H})
            pg.goto(tmp.as_uri(), wait_until="networkidle")
            pg.evaluate("document.fonts.ready")
            pg.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": W, "height": H})
            b.close()
    finally:
        tmp.unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-07", help="YYYY-MM")
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--kind", choices=["year", "month", "week-block", "week-schedule", "day", "category"])
    ap.add_argument("--ym", help="YYYY-MM (month/week/category pages)")
    ap.add_argument("--date", help="YYYY-MM-DD (day pages)")
    ap.add_argument("--blanks", action="store_true", help="render the 6 blank PNGs instead")
    args = ap.parse_args()

    import sys
    sys.path.insert(0, str(REPO))
    from src.config import Config
    from src.dates import build_pages
    from src.fill import fill_page
    from src.fonts import font_face_css
    from src.render import _PAGE_CSS, W, H, render_blanks

    templates = REPO / "assets" / "templates" / "rm2"
    out_dir = REPO / "tmp"
    out_dir.mkdir(exist_ok=True)
    sy, sm = (int(x) for x in args.start.split("-"))
    cfg = Config(start_y=sy, start_m=sm, months=args.months)

    if args.blanks:
        written = render_blanks(cfg, templates, REPO, out_dir)
        print("\n".join(str(p) for p in written))
        return

    pages, anchors = build_pages(cfg)

    def matches(p) -> bool:
        if p.kind != args.kind:
            return False
        if args.ym and p.month != tuple(int(x) for x in args.ym.split("-")):
            return False
        if args.date and p.day != date(*(int(x) for x in args.date.split("-"))):
            return False
        return True

    pg = next((p for p in pages if matches(p)), None)
    if pg is None:
        raise SystemExit(f"no page matched kind={args.kind} ym={args.ym} date={args.date}")

    svg, _ = fill_page(pg, cfg, anchors, templates)
    name = f"check-{args.kind}{('-' + (args.ym or args.date)) if (args.ym or args.date) else ''}.png"
    out = out_dir / name
    _render_svg(svg, font_face_css(REPO) + "\n" + _PAGE_CSS, out, W, H)
    print(out)


if __name__ == "__main__":
    main()
