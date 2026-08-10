"""Derive which backgrounds a normalised asset is safe to sit on.

The manifest publishes this per variant so a consumer can place a mark without
re-opening the file. The value answers "what may I put behind this?":

  "any"    the asset composites over anything — it has no baked-in fill
  "light"  the asset carries a light fill; safe on light backgrounds only
  "dark"   the asset carries a dark fill; safe on dark backgrounds only

Derived, never declared: 03_manifest.py writes it and 04_validate.py re-derives
and compares, so the published claim cannot drift from the bytes on disk.

Both readers must agree exactly, so this lives in one module and is
deterministic — no sampling, no tolerances.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

ANY = "any"
LIGHT = "light"
DARK = "dark"
VALID_BACKGROUNDS = {ANY, LIGHT, DARK}

SVG_NS = "{http://www.w3.org/2000/svg}"
# Elements whose contents describe geometry for reference rather than painting it.
_NON_RENDERING = {
    f"{SVG_NS}defs",
    f"{SVG_NS}clipPath",
    f"{SVG_NS}mask",
    f"{SVG_NS}symbol",
    f"{SVG_NS}pattern",
    f"{SVG_NS}marker",
}
# Midpoint of the 0-255 luminance scale: the fill is either nearer white or
# nearer black, and that is the whole judgement being made.
_LUMA_MIDPOINT = 128.0
# Named fills worth recognising; anything more exotic falls back to ANY (see
# _svg_background).
_NAMED_FILLS = {"white": (255, 255, 255), "black": (0, 0, 0)}
# Path data splits into single-letter commands and numbers (incl. exponents).
_PATH_TOKEN_RE = re.compile(r"[A-Za-z]|-?\d*\.?\d+(?:[eE][-+]?\d+)?")


def _luma(rgb: tuple[float, float, float]) -> float:
    """Rec. 709 relative luminance, 0-255."""
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _classify_fill(rgb: tuple[float, float, float]) -> str:
    return LIGHT if _luma(rgb) >= _LUMA_MIDPOINT else DARK


def _raster_background(path: Path) -> str:
    """Classify a raster by its outermost ring of pixels.

    02_normalise.py trims to the alpha bounding box, so a transparent asset is
    cropped tight to its mark and its ring is where any baked fill would show.
    A ring containing even one transparent pixel means no fill covers the
    canvas; a fully opaque ring is a fill, classified by its mean colour.

    The ring rather than the whole image, because a mark that happens to have
    an opaque interior is not thereby background-bound.
    """
    with Image.open(path) as im:
        img = im.convert("RGBA")
    w, h = img.size
    px = img.load()
    ring = [px[x, y] for x in range(w) for y in (0, h - 1)]
    ring += [px[x, y] for y in range(h) for x in (0, w - 1)]

    if any(pixel[3] != 255 for pixel in ring):
        return ANY
    mean = tuple(sum(p[i] for p in ring) / len(ring) for i in range(3))
    return _classify_fill(mean)


def _parse_fill(fill: str) -> tuple[int, int, int] | None:
    fill = fill.strip().lower()
    if fill in _NAMED_FILLS:
        return _NAMED_FILLS[fill]
    if not fill.startswith("#"):
        return None
    digits = fill[1:]
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    if len(digits) != 6:
        return None
    try:
        return (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))
    except ValueError:
        return None


def _spans(value: str | None, extent: float) -> bool:
    """True if an SVG length covers the full viewBox extent."""
    if value is None:
        return False
    value = value.strip()
    if value.endswith("%"):
        try:
            return float(value[:-1]) >= 100.0
        except ValueError:
            return False
    try:
        return float(value) >= extent
    except ValueError:
        return False


def _painted_descendants(node: ET.Element):
    """Walk only nodes that actually paint.

    `<defs>`, `<clipPath>` and friends define geometry for reference, not ink.
    Skipping them matters in practice: Figma exports routinely end with
    `<clipPath><path fill="#fff" d="M0 0h{w}v{h}H0z"/></clipPath>`, a full-canvas
    white rect that would otherwise read as a baked white background on an asset
    that has none.
    """
    for child in node:
        if child.tag in _NON_RENDERING:
            continue
        yield child
        yield from _painted_descendants(child)


def _path_bbox(d: str) -> tuple[float, float, float, float] | None:
    """Bounding box of an axis-aligned path, or None if it is anything else.

    Only M/L/H/V/Z (and their relative forms) are understood. Curves and arcs
    return None rather than a wrong answer — a mark with curves is not a
    background rectangle.
    """
    tokens = _PATH_TOKEN_RE.findall(d)
    x = y = 0.0
    points: list[tuple[float, float]] = []
    i = 0
    while i < len(tokens):
        cmd = tokens[i]
        if not cmd.isalpha():
            return None
        i += 1
        args: list[float] = []
        while i < len(tokens) and not tokens[i].isalpha():
            try:
                args.append(float(tokens[i]))
            except ValueError:
                return None
            i += 1

        upper = cmd.upper()
        relative = cmd.islower()
        if upper == "Z":
            continue
        if upper in {"M", "L"}:
            if len(args) % 2:
                return None
            for j in range(0, len(args), 2):
                x = x + args[j] if relative else args[j]
                y = y + args[j + 1] if relative else args[j + 1]
                points.append((x, y))
        elif upper == "H":
            for arg in args:
                x = x + arg if relative else arg
                points.append((x, y))
        elif upper == "V":
            for arg in args:
                y = y + arg if relative else arg
                points.append((x, y))
        else:
            return None

    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _svg_background(path: Path) -> str:
    """Look for a shape painted across the whole canvas — how an SVG bakes a fill.

    Checks both forms the shape takes in this pipeline: the `<rect>` an author
    writes, and the equivalent `<path>` that SVGO rewrites it into during
    02_normalise (a full-canvas rect becomes `M0 0h{w}v{h}H0z`), so the answer
    is the same before and after normalisation.

    Deliberately narrow. A background filled via CSS, a gradient, or a curved
    shape is not detected and the asset reports ANY. That is the right trade:
    such an asset fails the house standard on sight and should be rejected at
    curation time rather than guessed at here.
    """
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8"))
    except (ET.ParseError, OSError):
        return ANY

    viewbox = (root.get("viewBox") or "").replace(",", " ").split()
    if len(viewbox) != 4:
        return ANY
    try:
        min_x, min_y, width, height = (float(v) for v in viewbox)
    except ValueError:
        return ANY

    for node in _painted_descendants(root):
        rgb = _parse_fill(node.get("fill") or "")
        if rgb is None:
            continue
        if node.tag == f"{SVG_NS}rect":
            if _spans(node.get("width"), width) and _spans(node.get("height"), height):
                return _classify_fill(rgb)
        elif node.tag == f"{SVG_NS}path":
            bbox = _path_bbox(node.get("d") or "")
            if bbox and bbox == (min_x, min_y, min_x + width, min_y + height):
                return _classify_fill(rgb)
    return ANY


def derive_background(path: Path) -> str:
    """Which backgrounds the asset at `path` is safe on: "any", "light", "dark"."""
    if path.suffix.lower() == ".svg":
        return _svg_background(path)
    return _raster_background(path)
