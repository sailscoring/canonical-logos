"""Build data/manifest.json + data/unresolved.json (see CLAUDE.md).

Joins the curation decision (registry.yaml), the fetch provenance
(provenance.json), and the normalised files on disk (logos/). One manifest
record per shipped logo: id, class, displayName, file + format + post-
normalisation sha256, any small derivative, colourway variants, source
provenance, and any free-licence terms. Entities that could not be sourced, or
are on the denylist, are carried into unresolved.json with their reason.

Run after 01_fetch.py and 02_normalise.py.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from _registry import (
    LOGOS_DIR,
    MANIFEST_PATH,
    PROVENANCE_PATH,
    REPO_ROOT,
    UNRESOLVED_PATH,
    load_registry,
)

# Preference order when several files exist for one id (vector beats raster).
PRIMARY_PREFERENCE = [".svg", ".png"]


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _primary_file(eid: str) -> Path | None:
    candidates = [
        p
        for p in LOGOS_DIR.glob(f"{eid}.*")
        if ".small." not in p.name and p.suffix.lower() in PRIMARY_PREFERENCE
    ]
    candidates.sort(key=lambda p: PRIMARY_PREFERENCE.index(p.suffix.lower()))
    return candidates[0] if candidates else None


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def main() -> int:
    if not PROVENANCE_PATH.is_file():
        print("no data/provenance.json — run 01_fetch.py first.", file=sys.stderr)
        return 1

    registry = load_registry()
    by_id = {e["id"]: e for e in registry["logos"]}
    provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))

    logos: list[dict] = []
    unresolved: list[dict] = list(provenance.get("unresolved", []))

    for asset in provenance.get("assets", []):
        eid = asset["id"]
        entry = by_id.get(eid)
        if entry is None:
            unresolved.append({"id": eid, "reason": "fetched but no longer in registry"})
            continue
        primary = _primary_file(eid)
        if primary is None:
            unresolved.append({"id": eid, "reason": "no normalised file on disk"})
            continue

        fmt = primary.suffix.lower().lstrip(".")
        small = LOGOS_DIR / f"{eid}.small.png"
        record = {
            "id": eid,
            "class": entry["class"],
            "displayName": entry["displayName"],
            "file": _rel(primary),
            "format": fmt,
            "sha256": _sha256_file(primary),
            "variants": [{"file": _rel(primary), "variant": "primary", "background": "any"}],
            "sourceUrl": entry["source"],
            "sourceKind": entry["sourceKind"],
            "assetUrl": asset["assetUrl"],
            "licence": entry.get("licence"),
            "attribution": entry.get("attribution"),
            "usageNote": entry.get("usageNote"),
            "quality": entry.get("quality", "ok"),
            "qualityNote": entry.get("qualityNote"),
            "retrievedAt": asset["retrievedAt"],
        }
        if small.is_file():
            record["derivatives"] = {"small": _rel(small)}
        logos.append(record)

    logos.sort(key=lambda r: r["id"])
    unresolved.sort(key=lambda r: r["id"])

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(
            {"schemaVersion": "1.0", "generatedAt": _now(), "logos": logos},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    UNRESOLVED_PATH.write_text(
        json.dumps(
            {"schemaVersion": "1.0", "generatedAt": _now(), "entries": unresolved},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    provisional = [r["id"] for r in logos if r["quality"] == "provisional"]
    print(
        f"manifest: {len(logos)} logo(s) -> {_rel(MANIFEST_PATH)}; "
        f"{len(unresolved)} unresolved -> {_rel(UNRESOLVED_PATH)}"
    )
    if provisional:
        print(f"  provisional (best-available, replace when possible): {', '.join(provisional)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
