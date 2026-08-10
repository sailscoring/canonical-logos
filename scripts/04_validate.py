"""Validate the dataset (see CLAUDE.md).

Always validates the shape of sources/registry.yaml — required fields, valid
class / sourceKind, unique ids, and that nothing on the denylist is still listed
for fetching.

If data/manifest.json exists, also validates it: every entry maps to a registry
id that is not denylisted, its file (and any derivative) exists, the format is
allowed and matches the file, the recorded sha256 matches the file on disk, each
variant's `background` re-derives to the value published, and any asset with a
non-free licence carries an attribution string.
"""

from __future__ import annotations

import hashlib
import json
import sys

from _background import VALID_BACKGROUNDS, derive_background
from _registry import (
    MANIFEST_PATH,
    REPO_ROOT,
    check_registry,
    load_registry,
)

ALLOWED_FORMATS = {"svg", "png"}
# Licences that do not require attribution; anything else must carry one.
FREE_NO_ATTRIBUTION = {"public domain", "public-domain", "cc0", "cc0-1.0"}


def _validate_manifest(problems: list[str]) -> None:
    registry = load_registry()
    by_id = {e["id"]: e for e in registry["logos"]}
    denylist = {str(x) for x in registry["denylist"]}

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    seen: set[str] = set()

    for rec in manifest.get("logos", []):
        eid = rec.get("id", "<missing id>")
        where = f"manifest logo (id={eid!r})"

        if eid in seen:
            problems.append(f"{where}: duplicate id")
        seen.add(eid)

        if eid not in by_id:
            problems.append(f"{where}: not in registry.yaml")
        if eid in denylist:
            problems.append(f"{where}: id is on the denylist but present in the manifest")

        fmt = rec.get("format")
        if fmt not in ALLOWED_FORMATS:
            problems.append(f"{where}: format {fmt!r} not in {sorted(ALLOWED_FORMATS)}")

        file_rel = rec.get("file", "")
        path = REPO_ROOT / file_rel
        if not path.is_file():
            problems.append(f"{where}: file missing: {file_rel}")
        else:
            if fmt and not file_rel.lower().endswith(f".{fmt}"):
                problems.append(f"{where}: file extension does not match format {fmt!r}")
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != rec.get("sha256"):
                problems.append(f"{where}: sha256 mismatch (file changed since manifest build)")

        small = rec.get("derivatives", {}).get("small")
        if small and not (REPO_ROOT / small).is_file():
            problems.append(f"{where}: derivative missing: {small}")

        # Re-derive rather than trust: `background` is a claim a consumer acts on
        # when placing the mark, so a stale or hand-edited value must not ship.
        variants = rec.get("variants") or []
        if not variants:
            problems.append(f"{where}: no variants")
        for i, variant in enumerate(variants):
            vwhere = f"{where}: variant[{i}]"
            claimed = variant.get("background")
            vfile = variant.get("file", "")
            vpath = REPO_ROOT / vfile
            if claimed not in VALID_BACKGROUNDS:
                problems.append(
                    f"{vwhere}: background {claimed!r} not in {sorted(VALID_BACKGROUNDS)}"
                )
            elif not vpath.is_file():
                problems.append(f"{vwhere}: file missing: {vfile}")
            elif (actual := derive_background(vpath)) != claimed:
                problems.append(
                    f"{vwhere}: background claims {claimed!r} but {vfile} is {actual!r} "
                    "— re-run 03_manifest.py"
                )

        licence = rec.get("licence")
        if licence and licence.strip().lower() not in FREE_NO_ATTRIBUTION and not rec.get(
            "attribution"
        ):
            problems.append(f"{where}: licence {licence!r} requires an attribution")


def main() -> int:
    problems = check_registry(load_registry())

    if MANIFEST_PATH.is_file():
        _validate_manifest(problems)
    else:
        print("note: no manifest.json yet — registry-only validation.")

    if problems:
        print("validation failed:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print("dataset valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
