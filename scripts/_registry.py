"""Shared helpers for loading and checking sources/registry.yaml.

registry.yaml is the curation decision (the hand-maintained canonical set).
Both the pipeline scripts and the tests load it through here so the schema is
defined in one place.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "sources" / "registry.yaml"
LOGOS_DIR = REPO_ROOT / "logos"
DATA_DIR = REPO_ROOT / "data"
MANIFEST_PATH = DATA_DIR / "manifest.json"
UNRESOLVED_PATH = DATA_DIR / "unresolved.json"
PROVENANCE_PATH = DATA_DIR / "provenance.json"

# A "venue" is a non-club racing location; a "sailing-club" is the club itself.
# A club is often the venue, but the scorer picks the club logo when configuring
# a venue, so the two are tracked as distinct classes. A "regatta" is a recurring
# regatta-series brand (Cork Week, Volvo Dún Laoghaire Regatta) — its stable mark,
# not the one-off year-stamped artwork, which belongs in a per-workspace library.
VALID_CLASSES = {"governing-body", "sailing-club", "class-assoc", "sponsor", "venue", "regatta"}
VALID_SOURCE_KINDS = {"brand-portal", "direct", "wikimedia"}
REQUIRED_FIELDS = {"id", "class", "displayName", "source", "sourceKind"}
# "ok" (default, absent) = meets the quality bar; "provisional" = sub-par but the
# best available, kept deliberately and flagged for replacement. The latter must
# carry a qualityNote explaining the limitation.
VALID_QUALITY = {"ok", "provisional"}


def load_registry() -> dict[str, Any]:
    """Parse registry.yaml into {'logos': [...], 'denylist': [...]}."""
    data = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}
    data.setdefault("logos", [])
    data.setdefault("denylist", [])
    return data


def check_registry(data: dict[str, Any]) -> list[str]:
    """Return a list of human-readable problems with the registry. Empty == OK.

    Shape only — this does not touch the network or the logos/ files.
    """
    problems: list[str] = []
    seen_ids: set[str] = set()

    # A denylisted id may still appear in `logos` — the denylist exists to
    # override (suppress) a curation row when an owner asks for removal, not to
    # require deleting it. The fetch step skips denylisted ids; coexistence is
    # expected, so it is not flagged here.
    for i, entry in enumerate(data.get("logos", [])):
        where = f"logos[{i}]"
        if not isinstance(entry, dict):
            problems.append(f"{where}: not a mapping")
            continue

        missing = REQUIRED_FIELDS - entry.keys()
        if missing:
            problems.append(f"{where}: missing field(s): {', '.join(sorted(missing))}")
            continue

        eid = entry["id"]
        where = f"{where} (id={eid!r})"
        if eid in seen_ids:
            problems.append(f"{where}: duplicate id")
        seen_ids.add(eid)

        if entry["class"] not in VALID_CLASSES:
            problems.append(f"{where}: class must be one of {sorted(VALID_CLASSES)}")
        if entry["sourceKind"] not in VALID_SOURCE_KINDS:
            problems.append(f"{where}: sourceKind must be one of {sorted(VALID_SOURCE_KINDS)}")

        quality = entry.get("quality", "ok")
        if quality not in VALID_QUALITY:
            problems.append(f"{where}: quality must be one of {sorted(VALID_QUALITY)}")
        if quality == "provisional" and not entry.get("qualityNote"):
            problems.append(f"{where}: quality 'provisional' requires a qualityNote")
        if "candidateUrls" in entry and not isinstance(entry["candidateUrls"], list):
            problems.append(f"{where}: candidateUrls must be a list")

    return problems
