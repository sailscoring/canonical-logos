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

from PIL import Image, ImageDraw

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
  - id: sample-opaque
    class: sailing-club
    displayName: Sample Opaque Club
    source: https://example.test/
    sourceKind: direct
    assetUrl: sources/assets/opaque.png
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

    # A transparent raster with content in a sub-region (exercises the trim). An
    # ellipse, not a rectangle: it spans the same bounding box, so the trim still
    # lands on 120x60, but it leaves the corners transparent — a filled rectangle
    # would trim to a fully opaque image and be background-bound, which is true
    # of that shape but not what this fixture is here to represent.
    img = Image.new("RGBA", (300, 120), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((40, 30, 159, 89), fill=(251, 58, 59, 255))
    img.save(tmp_path / "sources" / "assets" / "sample.png")
    (tmp_path / "sources" / "assets" / "sample.svg").write_text(SAMPLE_SVG, encoding="utf-8")

    # An opaque mark on a baked white fill — the case `background` exists to warn
    # about (a white block on a dark header).
    opaque = Image.new("RGBA", (200, 100), (255, 255, 255, 255))
    for x in range(60, 140):
        for y in range(30, 70):
            opaque.putpixel((x, y), (18, 58, 94, 255))
    opaque.save(tmp_path / "sources" / "assets" / "opaque.png")

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
    assert set(by_id) == {"sample-raster", "sample-svg", "sample-opaque"}
    assert by_id["sample-raster"]["format"] == "png"
    assert by_id["sample-raster"]["derivatives"]["small"] == "logos/sample-raster.small.png"
    assert by_id["sample-svg"]["format"] == "svg"

    # `background` is derived from the bytes, not hardcoded: a transparent mark
    # composites over anything, a baked white fill is light-only, and the SVG
    # fixture is a full-canvas mid-red rect, so it is dark-only.
    def background(eid: str) -> str:
        (variant,) = by_id[eid]["variants"]
        return variant["background"]

    assert background("sample-raster") == "any"
    assert background("sample-opaque") == "light"
    assert background("sample-svg") == "dark"

    # And it is enforced, not merely emitted: a hand-edited claim fails validation.
    manifest_path = tmp_path / "data" / "manifest.json"
    tampered = json.loads(manifest_path.read_text())
    for rec in tampered["logos"]:
        if rec["id"] == "sample-opaque":
            rec["variants"][0]["background"] = "any"
    manifest_path.write_text(json.dumps(tampered), encoding="utf-8")

    proc = _run("04_validate.py", tmp_path)
    assert proc.returncode != 0
    assert "background claims 'any'" in proc.stdout + proc.stderr

    # Restore, so later assertions read the real manifest.
    _run("03_manifest.py", tmp_path)
    manifest = json.loads(manifest_path.read_text())
    by_id = {r["id"]: r for r in manifest["logos"]}

    unresolved = json.loads((tmp_path / "data" / "unresolved.json").read_text())
    reasons = {e["id"]: e["reason"] for e in unresolved["entries"]}
    assert reasons["blocked"] == "denylisted"
    assert "not yet sourced" in reasons["not-sourced"]
