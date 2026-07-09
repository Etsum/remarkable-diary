"""Font registration: build the @font-face CSS that maps the SVG's font-family
names to the bundled .ttf faces, and the per-glyph fallback chain.

The e-ink masters declare their type via the palette's font tokens: ``Inter``
(UI / labels / grid numbers), ``Newsreader`` (bold display headers) and
``EB Garamond`` (mini-calendar month names). ``Noto Sans`` remains for a few
nodes, and ``Noto Sans JP`` covers the kanji decoration. We serve each from the
repo's bundled TTFs so the browser renders exactly the device faces instead of
falling back to a system serif (issue #52). Kanji inside a Latin node resolve
via the browser's own CJK fallback (``with_fallback`` spells out the chain).
"""
from __future__ import annotations

import pathlib

# (css family name, weight, repo-relative ttf path). Weight is a CSS
# font-weight value — a keyword ("normal"/"bold") or a number (400..700) so
# nodes asking for weight 500/600 match an exact face instead of synth-bolding.
_FACES = [
    ("Inter", 400, "assets/fonts/Inter/static/Inter-Regular.ttf"),
    ("Inter", 500, "assets/fonts/Inter/static/Inter-Medium.ttf"),
    ("Inter", 600, "assets/fonts/Inter/static/Inter-SemiBold.ttf"),
    ("Inter", 700, "assets/fonts/Inter/static/Inter-Bold.ttf"),
    ("Newsreader", 400, "assets/fonts/Newsreader/static/Newsreader-Regular.ttf"),
    ("Newsreader", 500, "assets/fonts/Newsreader/static/Newsreader-Medium.ttf"),
    ("Newsreader", 700, "assets/fonts/Newsreader/static/Newsreader-Bold.ttf"),
    ("EB Garamond", 400, "assets/fonts/EB_Garamond/static/EBGaramond-Regular.ttf"),
    ("EB Garamond", 600, "assets/fonts/EB_Garamond/static/EBGaramond-SemiBold.ttf"),
    ("Noto Sans", "normal", "assets/fonts/Noto_Sans/static/NotoSans-Regular.ttf"),
    ("Noto Sans", "bold", "assets/fonts/Noto_Sans/static/NotoSans-Bold.ttf"),
    ("Noto Sans JP", "normal", "assets/fonts/Noto_Sans_JP/static/NotoSansJP-Regular.ttf"),
    ("Noto Sans JP", "bold", "assets/fonts/Noto_Sans_JP/static/NotoSansJP-Bold.ttf"),
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
