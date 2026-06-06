"""Resolve and download the official asset for every entity in registry.yaml.

Per scoping note §5: an entry's `assetUrl` points at the official file — an
http(s) URL (brand portal / press kit / Wikimedia) or a repo-relative path for
an asset an owner sent us directly and we dropped under sources/. Entries on the
denylist are skipped; entries without an assetUrl (not yet sourced) are recorded
as unresolved rather than failing the run. Resumable: a re-run skips a file
whose local copy already matches, preserving its original retrievedAt so the
rebuild diff stays stable.

Outputs:
  logos/<id>.<ext>        — downloaded raw asset
  data/provenance.json    — per-asset fetch provenance + the unresolved ledger
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from _registry import LOGOS_DIR, PROVENANCE_PATH, REPO_ROOT, check_registry, load_registry

# Wikimedia (and some brand CDNs) reject the default requests UA with a 403.
USER_AGENT = "canonical-logos/0 (+https://github.com/sailscoring/canonical-logos; mark@hyc.ie)"
# Raw formats accepted on fetch. Rasters are converted to PNG by 02_normalise.
ALLOWED_EXTS = {"svg", "png", "jpg", "jpeg", "gif", "webp", "bmp"}
CONTENT_TYPE_EXT = {
    "image/svg+xml": "svg",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/bmp": "bmp",
    "image/x-ms-bmp": "bmp",
}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ext_for(url: str, content_type: str | None) -> str | None:
    ext = Path(urlparse(url).path).suffix.lower().lstrip(".")
    if ext in ALLOWED_EXTS:
        return "jpg" if ext == "jpeg" else ext
    if content_type:
        return CONTENT_TYPE_EXT.get(content_type.split(";")[0].strip().lower())
    return None


def _load(asset_url: str) -> tuple[bytes, str | None]:
    """Return (bytes, content_type) for an http(s) URL or repo-relative path."""
    if asset_url.startswith(("http://", "https://")):
        resp = requests.get(asset_url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.content, resp.headers.get("Content-Type")
    local = (REPO_ROOT / asset_url).resolve()
    if not local.is_file():
        raise FileNotFoundError(asset_url)
    return local.read_bytes(), None


def _prior_retrieved_at() -> dict[str, tuple[str, str]]:
    """Map id -> (rawSha256, retrievedAt) from a previous run, for resumability."""
    if not PROVENANCE_PATH.is_file():
        return {}
    prior = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    return {a["id"]: (a["rawSha256"], a["retrievedAt"]) for a in prior.get("assets", [])}


def main() -> int:
    registry = load_registry()
    problems = check_registry(registry)
    if problems:
        print("registry.yaml has problems; fix before fetching:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    PROVENANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    denylist = {str(x) for x in registry["denylist"]}
    prior = _prior_retrieved_at()

    assets: list[dict] = []
    unresolved: list[dict] = []

    for entry in registry["logos"]:
        eid = entry["id"]
        if eid in denylist:
            unresolved.append({"id": eid, "reason": "denylisted"})
            continue
        asset_url = entry.get("assetUrl")
        if not asset_url or asset_url == "TODO":
            unresolved.append({"id": eid, "reason": "no assetUrl (not yet sourced)"})
            continue

        try:
            data, content_type = _load(asset_url)
        except (requests.RequestException, OSError) as exc:
            unresolved.append({"id": eid, "reason": f"fetch failed: {exc}"})
            continue

        ext = _ext_for(asset_url, content_type)
        if ext is None:
            unresolved.append({"id": eid, "reason": "unrecognised image format"})
            continue

        sha = _sha256(data)
        dest = LOGOS_DIR / f"{eid}.{ext}"
        if dest.is_file() and _sha256(dest.read_bytes()) == sha:
            action = "unchanged"
        else:
            dest.write_bytes(data)
            action = "fetched"

        # Preserve the original timestamp when the bytes are unchanged.
        retrieved_at = prior[eid][1] if prior.get(eid, (None,))[0] == sha else _now()
        print(f"  {action}: {eid} -> {dest.relative_to(REPO_ROOT)} ({len(data)} B)")
        assets.append(
            {
                "id": eid,
                "assetUrl": asset_url,
                "file": str(dest.relative_to(REPO_ROOT)),
                "fetchedFormat": ext,
                "rawSha256": sha,
                "retrievedAt": retrieved_at,
            }
        )

    PROVENANCE_PATH.write_text(
        json.dumps(
            {
                "schemaVersion": "1.0",
                "generatedAt": _now(),
                "assets": assets,
                "unresolved": unresolved,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"fetched {len(assets)}, unresolved {len(unresolved)} "
        f"-> {PROVENANCE_PATH.relative_to(REPO_ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
