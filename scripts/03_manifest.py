"""Build data/manifest.json from registry.yaml + the normalised logos/ assets.

One record per shipped logo: id, class, displayName, file, format, variants
(colourway + intended background), sourceUrl, sourceKind, optional usageNote and
free-licence attribution, retrievedAt, and post-normalisation sha256 (scoping
note §5). Entities that could not be sourced, or that are on the denylist, are
written to data/unresolved.json with a reason.

STATUS: stub. Not yet implemented — see sailscoring/docs/notes/canonical-logo-library.md.
"""

from __future__ import annotations


def main() -> int:
    print("manifest build not yet implemented — this is a skeleton stub.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
