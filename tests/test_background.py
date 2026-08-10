"""Unit tests for deriving which backgrounds an asset is safe on.

The end-to-end pipeline test covers the happy path; these pin the judgements
that are easy to get subtly wrong — non-painting SVG geometry, the two forms a
baked fill takes either side of SVGO, and the ring rule for rasters.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from _background import derive_background  # noqa: E402

SVG_OPEN = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 243 125">'


def _svg(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "sample.svg"
    path.write_text(f"{SVG_OPEN}{body}</svg>", encoding="utf-8")
    return path


def test_svg_without_a_fill_is_safe_anywhere(tmp_path: Path):
    assert derive_background(_svg(tmp_path, '<path fill="#4289c9" d="M10 10h50v50H10z"/>')) == "any"


def test_svg_background_as_a_rect_is_detected(tmp_path: Path):
    body = '<rect width="243" height="125" fill="#fff"/><path fill="#000" d="M10 10h5v5h-5z"/>'
    assert derive_background(_svg(tmp_path, body)) == "light"


def test_svg_background_survives_svgo_rewriting_it_to_a_path(tmp_path: Path):
    # SVGO turns a full-canvas <rect> into this path during 02_normalise, so the
    # answer must not depend on which side of normalisation we look at.
    assert derive_background(_svg(tmp_path, '<path fill="#123a5e" d="M0 0h243v125H0z"/>')) == "dark"


def test_percentage_sized_background_rect_is_detected(tmp_path: Path):
    body = '<rect width="100%" height="100%" fill="black"/>'
    assert derive_background(_svg(tmp_path, body)) == "dark"


def test_clip_path_geometry_is_not_a_background(tmp_path: Path):
    # Regression: Figma exports end with a full-canvas white path inside a
    # <clipPath>. It defines a clip region and paints nothing, but read naively
    # it looks exactly like a baked white background.
    body = (
        '<g clip-path="url(#c)"><path fill="#4289c9" d="M10 10h50v50H10z"/></g>'
        '<defs><clipPath id="c"><path fill="#fff" d="M0 0h243v125H0z"/></clipPath></defs>'
    )
    assert derive_background(_svg(tmp_path, body)) == "any"


def test_curved_shape_spanning_the_canvas_is_not_treated_as_a_rectangle(tmp_path: Path):
    body = '<path fill="#fff" d="M0 0C80 40 160 80 243 125z"/>'
    assert derive_background(_svg(tmp_path, body)) == "any"


def _raster(tmp_path: Path, image: Image.Image) -> Path:
    path = tmp_path / "sample.png"
    image.save(path)
    return path


def test_raster_with_transparent_corners_is_safe_anywhere(tmp_path: Path):
    img = Image.new("RGBA", (120, 60), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((0, 0, 119, 59), fill=(251, 58, 59, 255))
    assert derive_background(_raster(tmp_path, img)) == "any"


def test_raster_with_a_baked_white_fill_is_light_only(tmp_path: Path):
    img = Image.new("RGBA", (120, 60), (255, 255, 255, 255))
    ImageDraw.Draw(img).ellipse((20, 10, 99, 49), fill=(18, 58, 94, 255))
    assert derive_background(_raster(tmp_path, img)) == "light"


def test_raster_with_a_baked_dark_fill_is_dark_only(tmp_path: Path):
    img = Image.new("RGBA", (120, 60), (18, 58, 94, 255))
    ImageDraw.Draw(img).ellipse((20, 10, 99, 49), fill=(255, 255, 255, 255))
    assert derive_background(_raster(tmp_path, img)) == "dark"


def test_an_opaque_interior_alone_does_not_bind_the_background(tmp_path: Path):
    # The ring, not the whole image: a solid mark with one transparent edge pixel
    # still composites over anything.
    img = Image.new("RGBA", (120, 60), (251, 58, 59, 255))
    img.putpixel((0, 0), (0, 0, 0, 0))
    assert derive_background(_raster(tmp_path, img)) == "any"
