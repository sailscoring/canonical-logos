"""Normalise downloaded assets to the house standard (scoping note §6).

Format and size only — NEVER recolour, crop into, or restyle a mark.
  - Vectors: run SVGO with svgo.config.mjs (preserve IDs, keep viewBox).
  - Rasters: trim transparent bbox, cap the longest edge, transparent
    background, strip metadata (Pillow), and emit a small derivative for the
    ~100 px results-header slot.
Records the post-normalisation sha256 for the manifest step.

STATUS: stub. Not yet implemented — see sailscoring/docs/notes/canonical-logo-library.md.
"""

from __future__ import annotations


def main() -> int:
    print("normalise not yet implemented — this is a skeleton stub.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
