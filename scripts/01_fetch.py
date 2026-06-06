"""Resolve and download the official asset for every entity in registry.yaml.

Per scoping note §5, in priority order per entry: official brand portal / press
kit, direct from the owner, or Wikimedia Commons for the minority under a free
licence (reusing national-letters' resolver). Skips anything on the denylist.
Records provenance (sourceUrl, sourceKind, retrievedAt, sha256) for the manifest
step. Resumable: a re-run skips files whose local copy already matches.

Outputs:
  logos/<id>.<ext>         — downloaded raw asset(s)
  (provenance handed to scripts/03_manifest.py)

STATUS: stub. Not yet implemented — see sailscoring/docs/notes/canonical-logo-library.md.
"""

from __future__ import annotations

import sys

from _registry import check_registry, load_registry


def main() -> int:
    registry = load_registry()
    problems = check_registry(registry)
    if problems:
        print("registry.yaml has problems; fix before fetching:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print(f"registry OK: {len(registry['logos'])} entit(y/ies) to fetch.")
    print("fetch not yet implemented — this is a skeleton stub.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
