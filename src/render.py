"""Playwright/Chromium renderer (PIPELINE_SPEC §11.1).

Public API
----------
render_pdf(filled, pages, cfg, templates_dir, repo_root, output_path)
    Assemble one HTML document from filled SVGs + link overlays, print to PDF.

render_blanks(cfg, templates_dir, repo_root, output_dir)
    Emit one blank write-on PNG per master type (§12).

`filled` is a list of (svg_str, links) parallel to `pages`; links are
(x, y, w, h, target_anchor) tuples in SVG user units.
"""
from __future__ import annotations

import html
import tempfile
from pathlib import Path

from .config import Config
from .dates import Page
from .fill import Link
from .fonts import font_face_css

# Page dimensions (§3)
W, H = 1404, 1872

# CSS shared by both paths
_PAGE_CSS = f"""\
@page{{size:{W}px {H}px;margin:0}}
body{{margin:0;padding:0;background:#fff}}
.page{{width:{W}px;height:{H}px;position:relative;page-break-after:always;
       overflow:hidden;display:block}}
.page svg{{display:block;width:{W}px;height:{H}px}}
a.lnk{{position:absolute;display:block;z-index:10;
        text-decoration:none;color:transparent}}
"""


# ---------------------------------------------------------------------------
# HTML assembly helpers
# ---------------------------------------------------------------------------

def _link_tag(x: float, y: float, w: float, h: float, target: str) -> str:
    style = (
        f"left:{x:.2f}px;top:{y:.2f}px;"
        f"width:{w:.2f}px;height:{h:.2f}px"
    )
    return f'<a class="lnk" href="#{html.escape(target)}" style="{style}"></a>'


def _page_div(anchor: str | None, svg_str: str, links: list[Link]) -> str:
    id_attr = f' id="{html.escape(anchor)}"' if anchor else ""
    link_tags = "\n".join(_link_tag(*lnk) for lnk in links)
    return (
        f'<div class="page"{id_attr}>\n'
        f'{link_tags}\n'
        f'{svg_str}\n'
        f'</div>'
    )


def _cover_div(source: str | bool) -> str:
    if source == "blank" or source is True:
        return f'<div class="page" id="cover"></div>'
    # A supplied PNG/PDF path — embed as a full-page image
    path = Path(str(source))
    uri = path.resolve().as_uri()
    style = (
        f"position:absolute;top:0;left:0;"
        f"width:{W}px;height:{H}px;object-fit:fill"
    )
    return (
        f'<div class="page" id="cover">'
        f'<img src="{html.escape(uri)}" style="{style}"/>'
        f'</div>'
    )


def build_html(
    pages: list[Page],
    filled: list[tuple[str, list[Link]]],
    cfg: Config,
    repo_root: Path,
) -> str:
    """Assemble the full single-document HTML string."""
    css = font_face_css(repo_root) + "\n" + _PAGE_CSS
    divs: list[str] = []
    for page, (svg_str, links) in zip(pages, filled):
        if page.kind == "cover":
            divs.append(_cover_div(page.cover_source or cfg.cover_page))
        else:
            divs.append(_page_div(page.anchor, svg_str, links))
    body = "\n".join(divs)
    return (
        "<!DOCTYPE html><html><head>"
        f'<meta charset="utf-8">'
        f"<style>{css}</style>"
        "</head><body>"
        f"{body}"
        "</body></html>"
    )


# ---------------------------------------------------------------------------
# Playwright PDF rendering (§11.1)
# ---------------------------------------------------------------------------

_CHUNK = 200  # pages per render pass; keeps HTML under V8's ~512MB string limit


def _render_html_to_pdf(browser, html_str: str, output: Path) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", encoding="utf-8", delete=False
    ) as f:
        f.write(html_str)
        tmp_path = Path(f.name)
    try:
        pg = browser.new_page()
        pg.goto(tmp_path.as_uri(), wait_until="networkidle")
        pg.evaluate("document.fonts.ready")
        pg.pdf(path=str(output), prefer_css_page_size=True, print_background=True)
        pg.close()
    finally:
        tmp_path.unlink(missing_ok=True)


def _merge_pdfs(parts: list[Path], output: Path) -> None:
    import subprocess
    for exe, args in [
        ("qpdf", ["qpdf", "--empty", "--pages", *[str(p) for p in parts], "--", str(output)]),
        ("gs",   ["gs", "-dBATCH", "-dNOPAUSE", "-q", "-sDEVICE=pdfwrite",
                  f"-sOutputFile={output}", *[str(p) for p in parts]]),
    ]:
        try:
            subprocess.run(args, check=True, capture_output=True)
            return
        except FileNotFoundError:
            continue
    raise RuntimeError("PDF chunk merge requires qpdf or ghostscript (gs); install either.")


def render_pdf(
    pages: list[Page],
    filled: list[tuple[str, list[Link]]],
    cfg: Config,
    repo_root: Path,
    output_path: Path,
) -> None:
    """Print the assembled HTML to a PDF via Playwright/Chromium."""
    from playwright.sync_api import sync_playwright

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        if len(pages) <= _CHUNK:
            html_str = build_html(pages, filled, cfg, repo_root)
            _render_html_to_pdf(browser, html_str, output_path)
            browser.close()
        else:
            with tempfile.TemporaryDirectory() as td:
                parts: list[Path] = []
                for i in range(0, len(pages), _CHUNK):
                    chunk_html = build_html(pages[i:i+_CHUNK], filled[i:i+_CHUNK], cfg, repo_root)
                    part = Path(td) / f"part-{i:04d}.pdf"
                    _render_html_to_pdf(browser, chunk_html, part)
                    parts.append(part)
                browser.close()
                _merge_pdfs(parts, output_path)


# ---------------------------------------------------------------------------
# Blank write-on PNGs (§12)
# ---------------------------------------------------------------------------

_BLANK_REMOVE_IDS = (
    "var-ink",          # all variable content (§12 step 2)
    "rail-sections",    # category tabs (§12 step 3)
    "rail-sections-bg",
    "hdr-nav",          # nav arrows (§12 step 4)
    "footer-right",     # link text (§12 step 5)
)
_BLANK_CLEAR_TEXT = (
    "hdr-meta-top",     # keep frame, clear text (§12 step 6)
    "hdr-meta-bottom",
)


def _prepare_blank(svg_str: str) -> str:
    """Apply blank-mode transformations to a background-prepped SVG string."""
    from lxml import etree
    from . import svgutil as SU

    root = etree.fromstring(svg_str.encode())
    idm = SU.id_map(root)

    for node_id in _BLANK_REMOVE_IDS:
        node = idm.get(node_id)
        if node is not None:
            SU.remove(node)

    for node_id in _BLANK_CLEAR_TEXT:
        node = idm.get(node_id)
        if node is not None:
            SU.set_text(node, "")

    return etree.tostring(root, encoding="unicode")


def render_blanks(
    cfg: Config,
    templates_dir: Path,
    repo_root: Path,
    output_dir: Path,
) -> list[Path]:
    """Render one blank PNG per master type. Returns list of written paths."""
    from playwright.sync_api import sync_playwright
    from .background import prepare_background
    from . import svgutil as SU

    output_dir.mkdir(parents=True, exist_ok=True)
    masters = [
        "01-year", "02-month", "03-week-block",
        "04-week-schedule", "05-day", "06-category",
    ]
    font_css = font_face_css(repo_root)
    css = font_css + "\n" + _PAGE_CSS

    written: list[Path] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for stem in masters:
            tree = SU.parse(str(templates_dir / f"{stem}.svg"))
            prepare_background(tree, stem)
            svg_str = _prepare_blank(SU.tostring(tree))

            html_str = (
                "<!DOCTYPE html><html><head>"
                f'<meta charset="utf-8"><style>{css}</style>'
                f'</head><body><div class="page">{svg_str}</div></body></html>'
            )
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".html", encoding="utf-8", delete=False
            ) as f:
                f.write(html_str)
                tmp_path = Path(f.name)

            try:
                pg = browser.new_page(viewport={"width": W, "height": H})
                pg.goto(tmp_path.as_uri(), wait_until="networkidle")
                pg.evaluate("document.fonts.ready")
                out_path = output_dir / f"{stem}-blank.png"
                pg.screenshot(
                    path=str(out_path),
                    clip={"x": 0, "y": 0, "width": W, "height": H},
                    full_page=False,
                )
                pg.close()
                written.append(out_path)
            finally:
                tmp_path.unlink(missing_ok=True)

        browser.close()
    return written
