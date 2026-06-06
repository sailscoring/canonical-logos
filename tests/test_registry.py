"""The seed registry.yaml must parse and conform to its schema."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from _registry import check_registry, load_registry  # noqa: E402


def test_registry_parses():
    data = load_registry()
    assert isinstance(data["logos"], list)
    assert isinstance(data["denylist"], list)


def test_registry_conforms():
    problems = check_registry(load_registry())
    assert problems == [], "registry.yaml problems:\n" + "\n".join(problems)
