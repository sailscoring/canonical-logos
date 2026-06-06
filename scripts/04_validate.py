"""Validate the dataset (scoping note §9 step 5).

Today (skeleton): validates the shape of sources/registry.yaml — required
fields, valid class / sourceKind, unique ids, and that nothing on the denylist
is still listed for fetching.

Added once scripts/03_manifest.py produces output: every manifest entry resolves
to a file in logos/; formats are in the allowed set; any free-licence asset
carries its required attribution; exclusions are logged in unresolved.json.
"""

from __future__ import annotations

import sys

from _registry import MANIFEST_PATH, check_registry, load_registry


def main() -> int:
    problems = check_registry(load_registry())

    if MANIFEST_PATH.is_file():
        # TODO: validate manifest.json once 03_manifest.py produces it.
        print(f"note: {MANIFEST_PATH.name} exists; manifest validation not yet implemented.")

    if problems:
        print("validation failed:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print("registry.yaml valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
