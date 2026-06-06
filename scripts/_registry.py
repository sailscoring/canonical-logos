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

VALID_CLASSES = {"governing-body", "class-assoc", "sponsor", "venue"}
VALID_SOURCE_KINDS = {"brand-portal", "direct", "wikimedia"}
REQUIRED_FIELDS = {"id", "class", "displayName", "source", "sourceKind"}


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

    return problems
