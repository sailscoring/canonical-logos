"""Normalise downloaded assets to the house standard (scoping note §6).

Format and size only — NEVER recolour, crop into, or restyle a mark.
  - SVG: run SVGO (svgo.config.mjs) in place. Best-effort — if SVGO is not
    installed (`npx --no-install svgo`) the original valid SVG is kept and a
    warning is printed. CI installs SVGO; locally run `npm install -g svgo`.
  - Raster (png/jpg/gif/webp/bmp): trim to the non-transparent bounding box,
    cap the longest edge, force a transparent RGBA PNG, strip metadata, and
    write a small derivative (<id>.small.png) for the ~100 px header slot.

Operates on whatever is in logos/; idempotent. Rasters are rewritten as PNG, so
a converted original (e.g. <id>.jpg) is removed in favour of <id>.png.
"""

from __future__ import annotations

import subprocess
import sys
from functools import cache
from pathlib import Path

from _registry import LOGOS_DIR, REPO_ROOT
from PIL import Image

MAX_EDGE = 512  # longest edge of the primary raster
SMALL_EDGE = 200  # longest edge of the header derivative (~100px slot, retina)
RASTER_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


@cache
def _svgo_available() -> bool:
    try:
        r = subprocess.run(
            ["npx", "--no-install", "svgo", "--version"],
            cwd=REPO_ROOT,
            capture_output=True,
            timeout=60,
        )
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _normalise_svg(path: Path) -> None:
    if not _svgo_available():
        print(f"  warn: SVGO not installed; left {path.name} un-minified")
        return
    subprocess.run(
        ["npx", "--no-install", "svgo", "--config", "svgo.config.mjs", "-i", str(path),
         "-o", str(path)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    print(f"  svgo: {path.name}")


def _normalise_raster(path: Path) -> None:
    with Image.open(path) as im:
        img = im.convert("RGBA")
    bbox = img.getchannel("A").getbbox()  # None only if fully transparent
    if bbox:
        img = img.crop(bbox)
    img.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)

    primary = path.with_suffix(".png")
    img.save(primary, format="PNG", optimize=True)  # re-encode strips metadata
    if path.suffix.lower() != ".png":
        path.unlink()

    small = primary.with_suffix(".small.png")
    derivative = img.copy()
    derivative.thumbnail((SMALL_EDGE, SMALL_EDGE), Image.LANCZOS)
    derivative.save(small, format="PNG", optimize=True)
    print(f"  raster: {primary.name} (+ {small.name})")


def main() -> int:
    if not LOGOS_DIR.is_dir():
        print("no logos/ directory — run 01_fetch.py first.")
        return 0

    count = 0
    for path in sorted(LOGOS_DIR.iterdir()):
        if path.name == ".gitkeep" or ".small." in path.name:
            continue
        suffix = path.suffix.lower()
        if suffix == ".svg":
            _normalise_svg(path)
        elif suffix in RASTER_EXTS:
            _normalise_raster(path)
        else:
            print(f"  skip: {path.name} (not a recognised asset)", file=sys.stderr)
            continue
        count += 1

    print(f"normalised {count} asset(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
