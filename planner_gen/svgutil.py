"""lxml helpers for mutating the master SVGs.

Pure-Python (no browser). Provides:
- parse / serialize / id lookup
- bbox(): geometry of rect / line / path / group, matching browser getBBox for
  the axis-aligned rounded-rect frames the masters use (corner control points of
  a rounded rect coincide with the rect corner, so including them is exact).
- set_text / set_fill / remove: the "mutate, don't redraw" primitives.
"""
from __future__ import annotations

import re
from lxml import etree

SVG_NS = "http://www.w3.org/2000/svg"
S = "{%s}" % SVG_NS


def parse(path) -> etree._ElementTree:
    return etree.parse(str(path))


def tostring(tree) -> str:
    root = tree.getroot() if isinstance(tree, etree._ElementTree) else tree
    return etree.tostring(root, encoding="unicode")


def id_map(tree) -> dict[str, etree._Element]:
    root = tree.getroot() if isinstance(tree, etree._ElementTree) else tree
    return {el.get("id"): el for el in root.iter() if el.get("id")}


def local(el) -> str:
    return etree.QName(el).localname


# --- bbox -------------------------------------------------------------------
_NUM = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")
_CMD = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]")


def _path_points(d: str):
    """Yield (x, y) points (incl. control points) of a path, absolute coords.
    Handles M/L/H/V/C/S/Q/T/A and relative variants well enough for the masters'
    rect/rounded-rect/line frames."""
    tokens = _CMD.findall(d)
    chunks = _CMD.split(d)[1:]  # text after each command letter
    cx = cy = 0.0
    sx = sy = 0.0  # subpath start
    for cmd, chunk in zip(tokens, chunks):
        nums = [float(n) for n in _NUM.findall(chunk)]
        rel = cmd.islower()
        c = cmd.upper()
        i = 0
        if c in ("M", "L", "T"):
            first = True
            while i + 1 < len(nums) + 1 and i + 2 <= len(nums):
                x, y = nums[i], nums[i + 1]
                if rel:
                    x += cx; y += cy
                cx, cy = x, y
                if c == "M" and first:
                    sx, sy = cx, cy  # subpath start; further M-pairs are implicit L
                first = False
                yield cx, cy
                i += 2
        elif c == "H":
            for n in nums:
                cx = cx + n if rel else n
                yield cx, cy
        elif c == "V":
            for n in nums:
                cy = cy + n if rel else n
                yield cx, cy
        elif c in ("C", "S", "Q"):
            step = {"C": 6, "S": 4, "Q": 4}[c]
            while i + step <= len(nums):
                pts = nums[i:i + step]
                for j in range(0, step, 2):
                    x, y = pts[j], pts[j + 1]
                    if rel:
                        x += cx; y += cy
                    yield x, y
                cx, cy = (pts[-2] + (cx if rel else 0)), (pts[-1] + (cy if rel else 0))
                i += step
        elif c == "A":
            while i + 7 <= len(nums):
                x, y = nums[i + 5], nums[i + 6]
                if rel:
                    x += cx; y += cy
                cx, cy = x, y
                yield cx, cy
                i += 7
        elif c == "Z":
            cx, cy = sx, sy


def bbox(el) -> tuple[float, float, float, float] | None:
    """(x, y, w, h) in user units; unions descendants for groups."""
    xs: list[float] = []
    ys: list[float] = []

    def add(el):
        tag = local(el)
        if tag == "rect":
            x = float(el.get("x", 0)); y = float(el.get("y", 0))
            w = float(el.get("width", 0)); h = float(el.get("height", 0))
            xs.extend([x, x + w]); ys.extend([y, y + h])
        elif tag == "line":
            xs.extend([float(el.get("x1", 0)), float(el.get("x2", 0))])
            ys.extend([float(el.get("y1", 0)), float(el.get("y2", 0))])
        elif tag == "circle":
            cx = float(el.get("cx", 0)); cy = float(el.get("cy", 0)); r = float(el.get("r", 0))
            xs.extend([cx - r, cx + r]); ys.extend([cy - r, cy + r])
        elif tag == "path":
            for px, py in _path_points(el.get("d", "")):
                xs.append(px); ys.append(py)
        for c in el:
            add(c)

    add(el)
    if not xs or not ys:
        return None
    return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


# --- mutation primitives ----------------------------------------------------
def set_text(el, value: str) -> None:
    """Rewrite a <text> node's content, preserving its <tspan> position/style.
    Sets the first tspan's text (the masters use one tspan per text node)."""
    tspans = el.findall(S + "tspan")
    if tspans:
        tspans[0].text = value
        for extra in tspans[1:]:
            extra.text = ""
    else:
        el.text = value


def set_fill(el, color: str) -> None:
    el.set("fill", color)


def set_font_weight(el, weight: str) -> None:
    el.set("font-weight", weight)


def remove(el) -> None:
    p = el.getparent()
    if p is not None:
        p.remove(el)
