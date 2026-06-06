"""End-to-end pipeline test on local fixtures.

Runs fetch -> normalise -> manifest -> validate against a throwaway repo built in
a tmp dir, using `file`-relative assetUrls so no network and no real third-party
assets are involved. Proves the happy path (a raster gets normalised to PNG with
a small derivative and a manifest record) and the unresolved ledger (denylisted +
not-yet-sourced entries land in unresolved.json).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"

REGISTRY = """\
logos:
  - id: sample-raster
    class: sponsor
    displayName: Sample Raster Sponsor
    source: https://example.test/
    sourceKind: direct
    assetUrl: sources/assets/sample.png
  - id: sample-svg
    class: class-assoc
    displayName: Sample SVG Class
    source: https://example.test/
    sourceKind: brand-portal
    assetUrl: sources/assets/sample.svg
  - id: not-sourced
    class: governing-body
    displayName: Not Yet Sourced
    source: https://example.test/
    sourceKind: brand-portal
  - id: blocked
    class: sponsor
    displayName: Asked To Be Removed
    source: https://example.test/
    sourceKind: direct
    assetUrl: sources/assets/sample.png
denylist:
  - blocked
"""

SAMPLE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 10">'
    '<rect width="20" height="10" fill="#fb3a3b"/></svg>'
)


def _run(script: str, repo: Path) -> subprocess.CompletedProcess:
    # Run the COPIED script so REPO_ROOT (parent of scripts/) resolves to `repo`,
    # not the real repository this test lives in.
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / script)],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def test_pipeline_end_to_end(tmp_path: Path):
    # Build a throwaway repo: scripts come from the real repo, everything else
    # is fixture data so REPO_ROOT (parent of scripts/) resolves to tmp_path.
    shutil.copytree(SCRIPTS, tmp_path / "scripts")
    (tmp_path / "sources" / "assets").mkdir(parents=True)
    (tmp_path / "sources" / "registry.yaml").write_text(REGISTRY, encoding="utf-8")
    shutil.copy(REPO_ROOT / "svgo.config.mjs", tmp_path / "svgo.config.mjs")

    # A transparent raster with content in a sub-region (exercises the trim).
    img = Image.new("RGBA", (300, 120), (0, 0, 0, 0))
    for x in range(40, 160):
        for y in range(30, 90):
            img.putpixel((x, y), (251, 58, 59, 255))
    img.save(tmp_path / "sources" / "assets" / "sample.png")
    (tmp_path / "sources" / "assets" / "sample.svg").write_text(SAMPLE_SVG, encoding="utf-8")

    for script in ("01_fetch.py", "02_normalise.py", "03_manifest.py", "04_validate.py"):
        proc = _run(script, tmp_path)
        assert proc.returncode == 0, f"{script} failed:\n{proc.stdout}\n{proc.stderr}"

    # Raster normalised to a trimmed PNG + small derivative.
    primary = tmp_path / "logos" / "sample-raster.png"
    small = tmp_path / "logos" / "sample-raster.small.png"
    assert primary.is_file() and small.is_file()
    with Image.open(primary) as norm:
        assert norm.size == (120, 60)  # trimmed to the painted region
    assert not (tmp_path / "logos" / "sample-raster.jpg").exists()

    manifest = json.loads((tmp_path / "data" / "manifest.json").read_text())
    by_id = {r["id"]: r for r in manifest["logos"]}
    assert set(by_id) == {"sample-raster", "sample-svg"}
    assert by_id["sample-raster"]["format"] == "png"
    assert by_id["sample-raster"]["derivatives"]["small"] == "logos/sample-raster.small.png"
    assert by_id["sample-svg"]["format"] == "svg"

    unresolved = json.loads((tmp_path / "data" / "unresolved.json").read_text())
    reasons = {e["id"]: e["reason"] for e in unresolved["entries"]}
    assert reasons["blocked"] == "denylisted"
    assert "not yet sourced" in reasons["not-sourced"]
