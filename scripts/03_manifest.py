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
import html
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

INDEX_PATH = LOGOS_DIR / "index.html"
REPO_URL = "https://github.com/sailscoring/canonical-logos"
PAGE_DESCRIPTION = (
    "A curated, versioned set of canonical sailing logos consumed by Sail Scoring."
)
# Inline sail/burgee favicon so the deployed page never 404s on /favicon.ico.
FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'"
    "%3E%3Cpath d='M2 13h12l-1 1H3z' fill='%23123a5e'/%3E"
    "%3Cpath d='M8 1 3 12h5z' fill='%231f6feb'/%3E%3C/svg%3E"
)

# Human-facing order for the class sections on the landing page.
CLASS_ORDER = [
    ("governing-body", "Governing bodies"),
    ("class-assoc", "Class associations"),
    ("sailing-club", "Sailing clubs"),
    ("venue", "Venues"),
    ("regatta", "Regattas"),
    ("sponsor", "Sponsors"),
]


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


def _basename(file_rel: str) -> str:
    """Path as served from the site root (outputDirectory is logos/)."""
    return Path(file_rel).name


def _render_card(rec: dict) -> str:
    name = html.escape(rec["displayName"])
    eid = html.escape(rec["id"])
    full = html.escape(_basename(rec["file"]))
    small = rec.get("derivatives", {}).get("small")
    thumb = html.escape(_basename(small)) if small else full
    fmt = html.escape(rec["format"].upper())
    badge = ""
    if rec.get("quality") == "provisional":
        badge = (
            '<span class="badge prov" title="best-available; see registry note">'
            "provisional</span>"
        )
    return (
        f'<a class="card" href="{full}">'
        f'<span class="swatch"><img loading="lazy" src="{thumb}" alt="{name} logo"></span>'
        f'<span class="meta"><span class="name">{name}</span>'
        f'<span class="sub"><code>{eid}</code>'
        f'<span class="badge">{fmt}</span>{badge}</span></span></a>'
    )


def write_index(logos: list[dict], generated_at: str) -> None:
    by_class: dict[str, list[dict]] = {}
    for rec in logos:
        by_class.setdefault(rec["class"], []).append(rec)

    sections: list[str] = []
    # Known classes in curated order, then any unexpected class alphabetically.
    ordered = list(CLASS_ORDER) + [
        (c, c.replace("-", " ").title()) for c in sorted(by_class) if c not in dict(CLASS_ORDER)
    ]
    for cls, title in ordered:
        recs = by_class.get(cls)
        if not recs:
            continue
        cards = "\n".join(_render_card(r) for r in recs)
        sections.append(
            f'      <section>\n        <h2>{html.escape(title)} '
            f'<span class="n">{len(recs)}</span></h2>\n'
            f'        <div class="grid">\n{cards}\n        </div>\n      </section>'
        )

    provisional = sum(1 for r in logos if r.get("quality") == "provisional")
    prov_note = (
        f" · {provisional} provisional" if provisional else ""
    )
    doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sail Scoring · Canonical Logos</title>
  <meta name="description" content="{PAGE_DESCRIPTION}">
  <link rel="icon" href="{FAVICON}">
  <style>
    :root {{ color-scheme: light; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; font: 16px/1.5 system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      color: #0f172a; background: #f6f8fb;
    }}
    header {{ padding: 2.5rem 1.5rem 1rem; max-width: 1100px; margin: 0 auto; }}
    h1 {{ margin: 0 0 .25rem; font-size: 1.6rem; letter-spacing: -.01em; }}
    .lead {{ margin: 0; color: #475569; }}
    .lead a {{ color: #1f6feb; }}
    main {{ max-width: 1100px; margin: 0 auto; padding: 1rem 1.5rem 3rem; }}
    section {{ margin-top: 2rem; }}
    h2 {{ font-size: .85rem; text-transform: uppercase; letter-spacing: .06em;
      color: #64748b; margin: 0 0 .75rem; }}
    h2 .n {{ color: #94a3b8; font-weight: 400; }}
    .grid {{ display: grid; gap: .75rem;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }}
    .card {{ display: flex; align-items: center; gap: .75rem; padding: .6rem;
      background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
      text-decoration: none; color: inherit; transition: border-color .15s, box-shadow .15s; }}
    .card:hover {{ border-color: #1f6feb; box-shadow: 0 1px 8px rgba(31,111,235,.12); }}
    .swatch {{ flex: 0 0 56px; height: 56px; display: grid; place-items: center;
      border-radius: 8px; padding: 6px;
      background-image:
        linear-gradient(45deg, #eef2f7 25%, transparent 25%),
        linear-gradient(-45deg, #eef2f7 25%, transparent 25%),
        linear-gradient(45deg, transparent 75%, #eef2f7 75%),
        linear-gradient(-45deg, transparent 75%, #eef2f7 75%);
      background-size: 12px 12px;
      background-position: 0 0, 0 6px, 6px -6px, -6px 0; }}
    .swatch img {{ max-width: 100%; max-height: 100%; }}
    .meta {{ display: flex; flex-direction: column; min-width: 0; }}
    .name {{ font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .sub {{ display: flex; align-items: center; gap: .4rem; margin-top: .15rem; }}
    .sub code {{ font-size: .8rem; color: #64748b; }}
    .badge {{ font-size: .65rem; font-weight: 600; letter-spacing: .03em;
      padding: .1rem .35rem; border-radius: 5px; background: #eef2f7; color: #475569; }}
    .badge.prov {{ background: #fef3c7; color: #92400e; }}
    footer {{ max-width: 1100px; margin: 0 auto; padding: 0 1.5rem 3rem;
      color: #94a3b8; font-size: .85rem; }}
    footer a {{ color: #64748b; }}
  </style>
</head>
<body>
  <header>
    <h1>Canonical Logos</h1>
    <p class="lead">A curated, versioned set of canonical sailing logos consumed by
      <a href="https://sailscoring.ie">Sail Scoring</a>.
      Source &amp; licensing on <a href="{REPO_URL}">GitHub</a>.</p>
  </header>
  <main>
{chr(10).join(sections)}
  </main>
  <footer>
    {len(logos)} logos{prov_note} · generated {html.escape(generated_at)} ·
    <a href="{REPO_URL}/blob/main/data/manifest.json">manifest.json</a>
  </footer>
</body>
</html>
"""
    INDEX_PATH.write_text(doc, encoding="utf-8")


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

    generated_at = _now()
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(
            {"schemaVersion": "1.0", "generatedAt": generated_at, "logos": logos},
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
    write_index(logos, generated_at)

    provisional = [r["id"] for r in logos if r["quality"] == "provisional"]
    print(
        f"manifest: {len(logos)} logo(s) -> {_rel(MANIFEST_PATH)}; "
        f"{len(unresolved)} unresolved -> {_rel(UNRESOLVED_PATH)}; "
        f"landing page -> {_rel(INDEX_PATH)}"
    )
    if provisional:
        print(f"  provisional (best-available, replace when possible): {', '.join(provisional)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
