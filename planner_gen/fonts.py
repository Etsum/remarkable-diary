"""Font registration: build the @font-face CSS that maps the SVG's font-family
names to the bundled .ttf faces, and the per-glyph fallback chain.

The masters declare three families by name: ``IBM Plex Mono``, ``Noto Sans`` and
``Noto Sans JP``.  We serve each from the repo's bundled TTFs so the browser
renders exactly the device faces.  A global fallback to Noto Sans JP is appended
to every family so mixed Latin+kanji nodes (e.g. day ``hdr-right-weekday`` =
"MON · 月", footers like "2月 16, 2026") shape correctly: the primary face draws
Latin, Noto Sans JP picks up the kanji.
"""
from __future__ import annotations

import pathlib

# (css family name, weight, repo-relative ttf path)
_FACES = [
    ("IBM Plex Mono", "normal", "fonts/IBM_Plex_Mono/IBMPlexMono-Regular.ttf"),
    ("IBM Plex Mono", "bold", "fonts/IBM_Plex_Mono/IBMPlexMono-Bold.ttf"),
    ("Noto Sans", "normal", "fonts/Noto_Sans/static/NotoSans-Regular.ttf"),
    ("Noto Sans", "bold", "fonts/Noto_Sans/static/NotoSans-Bold.ttf"),
    ("Noto Sans JP", "normal", "fonts/Noto_Sans_JP/static/NotoSansJP-Regular.ttf"),
    ("Noto Sans JP", "bold", "fonts/Noto_Sans_JP/static/NotoSansJP-Bold.ttf"),
]

# Families that already cover CJK — no JP fallback needed/wanted.
JP_FAMILY = "Noto Sans JP"
FALLBACK = "Noto Sans JP"


def font_face_css(repo_root: pathlib.Path) -> str:
    """@font-face rules pointing at file:// URIs for the bundled TTFs."""
    rules = []
    for family, weight, rel in _FACES:
        uri = (repo_root / rel).resolve().as_uri()
        rules.append(
            "@font-face{"
            f"font-family:'{family}';font-weight:{weight};font-style:normal;"
            f"src:url('{uri}') format('truetype');"
            "}"
        )
    return "\n".join(rules)


def with_fallback(family: str | None) -> str:
    """Append the CJK fallback to a font-family value unless it is already JP."""
    if not family:
        return f"'{FALLBACK}'"
    fam = family.strip().strip("'\"")
    if fam == JP_FAMILY:
        return f"'{fam}'"
    return f"'{fam}', '{FALLBACK}'"
