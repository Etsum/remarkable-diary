"""CLI entry point + pre-flight validator + full build orchestration.

Usage
-----
  uv run python -m planner_gen.build --config config.json
  uv run python -m planner_gen.build --start 2026-01 --months 12
  uv run python -m planner_gen.build --start 2026-01 --end 2026-12 --output out/planner-2026.pdf
  uv run python -m planner_gen.build --validate-only   # pre-flight check only
  uv run python -m planner_gen.build --blanks-only     # render blank PNGs only

The pre-flight validator (§13.1) runs automatically before every build.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .config import DEFAULT_CATEGORIES

REPO_ROOT      = Path(__file__).resolve().parent.parent
TEMPLATES_DIR  = REPO_ROOT / "assets" / "templates" / "rm2"

# ---------------------------------------------------------------------------
# Pre-flight validator (§13.1)
# ---------------------------------------------------------------------------

# Per-master expected element counts and required ids
_REQUIRED: dict[str, dict] = {
    "01-year": {
        "text_ids": ["hdr-big", "hdr-meta-top", "hdr-meta-bottom", "footer-left"],
        "groups":   ["background", "var-ink"],
        # regex pattern → minimum count
        "counts":   {r"mini-\d{2}-d-r": 504},
    },
    "02-month": {
        "text_ids": ["hdr-big", "hdr-month-name", "hdr-meta-top", "hdr-meta-bottom",
                     "footer-left"],
        "groups":   ["background", "var-ink"],
        "counts":   {"mcell-r": 42, "mrow-": 6},
    },
    "03-week-block": {
        "text_ids": ["hdr-big", "hdr-month-name", "hdr-meta-top", "hdr-meta-bottom",
                     "footer-left"],
        "groups":   ["background", "var-ink"],
        "counts":   {"wb-day-": 7},
    },
    "04-week-schedule": {
        "text_ids": ["hdr-big", "hdr-month-name", "hdr-meta-top", "hdr-meta-bottom",
                     "footer-left"],
        "groups":   ["background", "var-ink"],
        "counts":   {"ws-day-": 7, "ws-hour-": 18},
    },
    "05-day": {
        "text_ids": ["hdr-big", "hdr-month-name", "hdr-right-weekday",
                     "hdr-meta-top", "hdr-meta-bottom", "footer-left",
                     "day-mini-month", "day-mini-year"],
        "groups":   ["background", "var-ink"],
        "counts":   {"day-mini-r": 42},
    },
    "06-category": {
        "text_ids": ["hdr-big", "hdr-month-name", "hdr-meta-top", "hdr-meta-bottom"],
        "groups":   ["background"],   # no var-ink on category master
        "counts":   {},
    },
}

# Rail ids expected on every master
_RAIL_IDS = (
    ["rail-index-chip"]
    + [f"rail-month-{mm:02d}-bg" for mm in range(1, 13)]
    + [f"rail-section-{i}-bg" for i in range(1, 5)]
)


def validate_masters(templates_dir: Path = TEMPLATES_DIR) -> list[str]:
    """Run pre-flight checks on all six master SVGs. Returns list of error strings."""
    from . import svgutil as SU

    errors: list[str] = []

    for stem, spec in _REQUIRED.items():
        svg_path = templates_dir / f"{stem}.svg"
        if not svg_path.exists():
            errors.append(f"MISSING master: {svg_path}")
            continue

        try:
            tree = SU.parse(str(svg_path))
        except Exception as e:
            errors.append(f"{stem}: parse error — {e}")
            continue

        idm = SU.id_map(tree)

        # Check for duplicate ids
        root = tree.getroot()
        all_ids = [el.get("id") for el in root.iter() if el.get("id")]
        seen: set[str] = set()
        for eid in all_ids:
            if eid in seen:
                errors.append(f"{stem}: DUPLICATE id '{eid}'")
            seen.add(eid)

        # Required groups (background, var-ink)
        for gid in spec.get("groups", []):
            if gid not in idm:
                errors.append(f"{stem}: missing group #{gid}")

        # Required text ids
        for tid in spec.get("text_ids", []):
            if tid not in idm:
                errors.append(f"{stem}: missing text node #{tid}")
            elif SU.local(idm[tid]) != "text":
                errors.append(f"{stem}: #{tid} is not a <text> node")

        # Rail ids (all masters)
        for rid in _RAIL_IDS:
            if rid not in idm:
                errors.append(f"{stem}: missing rail node #{rid}")

        # Count checks (regex pattern matches)
        import re as _re
        for pattern, expected in spec.get("counts", {}).items():
            count = sum(1 for k in idm if _re.search(pattern, k))
            if count < expected:
                errors.append(
                    f"{stem}: expected >={expected} ids matching '{pattern}', "
                    f"found {count}"
                )

    return errors


# ---------------------------------------------------------------------------
# Build pipeline
# ---------------------------------------------------------------------------

def build(
    cfg,
    templates_dir: Path = TEMPLATES_DIR,
    repo_root: Path = REPO_ROOT,
    validate: bool = True,
) -> None:
    """Full build: fill pages → render PDF (+ optional blanks)."""
    from .dates import build_pages
    from .background import prepare_background
    from . import svgutil as SU
    from .fill import fill_page
    from .render import render_pdf, render_blanks

    output_path = Path(cfg.output)
    t0 = time.time()

    # --- Pre-flight ---
    if validate:
        print("Validating masters…", end=" ", flush=True)
        errors = validate_masters(templates_dir)
        if errors:
            print("FAILED")
            for e in errors:
                print(f"  ✗ {e}")
            sys.exit(1)
        print("OK")

    # --- Page model ---
    print("Computing page list…", end=" ", flush=True)
    pages, anchors = build_pages(cfg)
    print(f"{len(pages)} pages, {len(anchors)} anchors")

    # --- Cache background-prepped SVG trees (one per master) ---
    print("Preparing dot-grid backgrounds…", end=" ", flush=True)
    bg_cache: dict[str, str] = {}
    masters = ["01-year", "02-month", "03-week-block",
               "04-week-schedule", "05-day", "06-category"]
    for stem in masters:
        tree = SU.parse(str(templates_dir / f"{stem}.svg"))
        prepare_background(tree, stem, cfg.dot_scale)
        # Store the prepped SVG string; fill_page will re-parse from templates_dir
        # (dot-grid is added to templates directly during fill via deepcopy)
        bg_cache[stem] = SU.tostring(tree)
    print("done")

    # --- Fill pages ---
    print(f"Filling {len(pages)} pages…", end=" ", flush=True)
    import tempfile
    # fill_page reads SVG from templates_dir; we write background-prepped SVGs
    # to a temp dir so fill gets the dot-grid-ready masters.
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_templates = Path(tmpdir)
        for stem, svg_str in bg_cache.items():
            (tmp_templates / f"{stem}.svg").write_text(svg_str, encoding="utf-8")

        filled: list[tuple[str, list]] = []
        for page in pages:
            svg_str, links = fill_page(page, cfg, anchors, tmp_templates)
            filled.append((svg_str, links))

    print("done")

    # --- Render PDF ---
    print(f"Rendering PDF → {output_path}…", end=" ", flush=True)
    render_pdf(pages, filled, cfg, repo_root, output_path)
    elapsed = time.time() - t0
    print(f"done ({elapsed:.1f}s)")
    print(f"✓ Written: {output_path}")

    # --- Blank PNGs ---
    if cfg.blanks:
        print("Rendering blank PNGs…", end=" ", flush=True)
        out_dir = output_path.parent
        written = render_blanks(cfg, templates_dir, repo_root, out_dir)
        print(f"done ({len(written)} files)")
        for p in written:
            print(f"  ✓ {p}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m planner_gen.build",
        description="Generate a reMarkable planner PDF + blank PNGs from Figma SVG masters.",
    )
    p.add_argument("--config", metavar="PATH",
                   help="JSON config file (overrides other flags if present)")
    p.add_argument("--start", metavar="YYYY-MM",
                   help="First month of range (required if --config not given)")
    p.add_argument("--end",   metavar="YYYY-MM",
                   help="Last month of range (inclusive)")
    p.add_argument("--months", type=int, default=12,
                   help="Number of months (alternative to --end, default 12)")
    p.add_argument("--output", metavar="PATH", default="out/planner.pdf",
                   help="Output PDF path (default: out/planner.pdf)")
    p.add_argument("--lang", choices=["jp-en", "en"], default="jp-en",
                   help="Language mode (default: jp-en)")
    p.add_argument("--weeklink", choices=["schedule", "block"], default="schedule",
                   help="Where week-number links point (default: schedule)")
    p.add_argument("--no-blanks", action="store_true",
                   help="Skip blank PNG output")
    p.add_argument("--no-block", action="store_true",
                   help="Skip week-block pages")
    p.add_argument("--no-schedule", action="store_true",
                   help="Skip week-schedule pages")
    p.add_argument("--no-days", action="store_true",
                   help="Skip day pages")
    p.add_argument("--pages-per-category", type=int, default=5, metavar="N",
                   help="Category pages per slot per month (default 5)")
    p.add_argument("--cover", metavar="PATH|blank",
                   help="Cover page: 'blank' or path to a PDF/PNG")
    p.add_argument("--hour-start", type=int, default=5, metavar="H",
                   help="First hour label on week-schedule pages (default 5)")
    p.add_argument("--dot-scale", type=float, default=0.8, metavar="F",
                   help="Dot-grid tile size scale factor (default: 0.8, 1.0 = original)")
    p.add_argument("--validate-only", action="store_true",
                   help="Run pre-flight validator and exit (no PDF generated)")
    p.add_argument("--blanks-only", action="store_true",
                   help="Render blank PNGs only (no PDF)")
    p.add_argument("--templates-dir", metavar="PATH", default=str(TEMPLATES_DIR),
                   help="Directory containing master SVGs (default: templates/)")
    return p


def main(argv: list[str] | None = None) -> None:
    parser = _make_parser()
    args = parser.parse_args(argv)

    templates_dir = Path(args.templates_dir)

    # --- Validate-only mode ---
    if args.validate_only:
        errors = validate_masters(templates_dir)
        if errors:
            for e in errors:
                print(f"✗ {e}")
            sys.exit(1)
        print("✓ All masters pass pre-flight checks.")
        return

    # --- Load config ---
    from .config import Config, load_config

    if args.config:
        cfg = load_config(args.config)
    elif args.blanks_only:
        # Blanks-only needs no date range — use a dummy single month
        cfg = Config(
            start_y=2026, start_m=1, months=1,
            lang=args.lang,
            categories=DEFAULT_CATEGORIES,
            pages_per_category=args.pages_per_category,
            output=args.output,
            blanks=True,
            hour_start=args.hour_start,
            dot_scale=args.dot_scale,
        )
    else:
        if not args.start:
            parser.error("--start YYYY-MM is required when --config is not given")
        sy, sm = args.start.split("-")
        if args.end:
            ey, em = args.end.split("-")
            months = (int(ey) - int(sy)) * 12 + (int(em) - int(sm)) + 1
        else:
            months = args.months
        cfg = Config(
            start_y=int(sy), start_m=int(sm), months=months,
            lang=args.lang, weeklink=args.weeklink,
            include={
                "block":    not args.no_block,
                "schedule": not args.no_schedule,
                "days":     not args.no_days,
            },
            pages_per_category=args.pages_per_category,
            cover_page=args.cover or False,
            output=args.output,
            blanks=not args.no_blanks,
            hour_start=args.hour_start,
            dot_scale=args.dot_scale,
        )

    # --- Blanks-only mode ---
    if args.blanks_only:
        from .render import render_blanks
        out_dir = Path(cfg.output).parent
        print("Rendering blank PNGs…", end=" ", flush=True)
        written = render_blanks(cfg, templates_dir, REPO_ROOT, out_dir)
        print(f"done ({len(written)} files)")
        for p in written:
            print(f"  ✓ {p}")
        return

    build(cfg, templates_dir=templates_dir, repo_root=REPO_ROOT)


if __name__ == "__main__":
    main()
