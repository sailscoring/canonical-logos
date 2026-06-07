"""Propose candidate logo files for unsourced registry entries.

Casts the net wider than Commons: per registry entry without
an assetUrl, gather candidates from
  - candidateUrls   explicit hints on the entry
  - homepage        og:image / icons / logo <img>s on the entity's own site
  - Wikimedia       Commons search by display name
Each candidate is downloaded and inspected (format, size, transparency); the
list is ranked best-first, written to .scout/report.json, and the top pick per
entity is staged under .scout/stage/ for visual review.

The scout NEVER edits the registry. Picking a winner and adding its assetUrl
stays a human decision — the scout just removes the digging.

Usage:
  python scripts/05_scout.py                 # all unsourced, non-denylisted
  python scripts/05_scout.py squib 1720      # only these ids
  python scripts/05_scout.py --no-stage      # report only, don't download picks
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
from urllib.parse import quote, urljoin, urlparse

import requests
from _registry import REPO_ROOT, load_registry
from PIL import Image

UA = {
    "User-Agent": "canonical-logos/0 (+https://github.com/sailscoring/canonical-logos; mark@hyc.ie)"
}
SCOUT_DIR = REPO_ROOT / ".scout"
EXT_BY_FORMAT = {"PNG": "png", "JPEG": "jpg", "GIF": "gif", "WEBP": "webp", "BMP": "bmp"}

RE_OG = re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', re.I)
RE_ICON = re.compile(r'<link[^>]+rel=["\'][^"\']*icon[^"\']*["\'][^>]+href=["\']([^"\']+)', re.I)
RE_IMG = re.compile(r"<img[^>]+>", re.I)
RE_SRC = re.compile(r'(?:data-src|src)=["\']([^"\']+)', re.I)


def _get(url: str) -> requests.Response:
    return requests.get(url, headers=UA, timeout=20)


def _homepage(entry: dict) -> str | None:
    if entry.get("home"):
        return entry["home"]
    src = entry.get("source", "")
    if src.startswith("http"):
        u = urlparse(src)
        return f"{u.scheme}://{u.netloc}/"
    return None


def _scrape(home: str) -> list[str]:
    """og:image, icons, and logo <img>s from a homepage (heuristic)."""
    try:
        html = _get(home).text
    except requests.RequestException:
        return []
    out: list[str] = []
    out += RE_OG.findall(html)
    out += RE_ICON.findall(html)
    for tag in RE_IMG.findall(html):
        if re.search(r"logo", tag, re.I):
            m = RE_SRC.search(tag)
            if m:
                out.append(m.group(1))
    return [urljoin(home, u) for u in out][:8]


def _commons(name: str) -> list[tuple[str, str]]:
    """Return [(url, licenceShortName)] for the top Commons image hits."""
    q = re.sub(r"\(.*?\)", "", name).strip()
    try:
        r = _get(
            "https://commons.wikimedia.org/w/api.php?action=query&list=search"
            f"&srsearch={quote(q + ' logo')}&srnamespace=6&format=json&srlimit=4"
        ).json()
        titles = [
            h["title"] for h in r.get("query", {}).get("search", [])
            if h["title"].lower().endswith((".svg", ".png"))
        ]
        out = []
        for t in titles[:3]:
            ii = _get(
                "https://commons.wikimedia.org/w/api.php?action=query"
                f"&titles={quote(t)}&prop=imageinfo&iiprop=url|extmetadata&format=json"
            ).json()
            p = list(ii["query"]["pages"].values())[0]["imageinfo"][0]
            lic = p.get("extmetadata", {}).get("LicenseShortName", {}).get("value", "")
            out.append((p["url"], lic))
        return out
    except (requests.RequestException, KeyError, IndexError):
        return []


def _inspect(url: str, via: str, licence: str = "") -> dict:
    info = {"url": url, "via": via, "licence": licence}
    try:
        data = _get(url).content
    except requests.RequestException as e:
        return {**info, "error": str(e)[:50]}
    if url.lower().split("?")[0].endswith(".svg") or b"<svg" in data[:400]:
        return {**info, "kind": "svg", "bytes": len(data)}
    try:
        im = Image.open(io.BytesIO(data))
    except OSError as e:
        return {**info, "error": f"not an image: {str(e)[:40]}"}
    palette = im.mode in ("P", "L", "1")
    fmt = im.format or "?"
    rgba = im.convert("RGBA")
    bb = rgba.getchannel("A").getbbox()
    tw, th = (bb[2] - bb[0], bb[3] - bb[1]) if bb else (0, 0)
    transparent = rgba.getchannel("A").getextrema() != (255, 255)
    return {
        **info, "kind": "raster", "format": fmt, "size": list(im.size),
        "trim": [tw, th], "transparent": transparent, "palette": palette, "bytes": len(data),
    }


def _score(c: dict) -> float:
    if c.get("error"):
        return -1.0
    if c.get("kind") == "svg":
        return 1e9
    tw, th = c["trim"]
    area = float(tw * th)
    if c["transparent"]:
        area *= 1.3
    if c["palette"]:
        area *= 0.6
    if min(tw, th) < 32:
        return 0.0
    if min(tw, th) < 100:
        area *= 0.4
    return area


def _ext(c: dict) -> str:
    return "svg" if c.get("kind") == "svg" else EXT_BY_FORMAT.get(c.get("format", ""), "png")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*", help="registry ids to scout (default: all unsourced)")
    ap.add_argument("--no-stage", action="store_true", help="report only; don't download picks")
    args = ap.parse_args()

    registry = load_registry()
    denylist = {str(x) for x in registry["denylist"]}
    targets = [
        e for e in registry["logos"]
        if e["id"] in args.ids
        or (not args.ids and not e.get("assetUrl") and e["id"] not in denylist)
    ]
    if not targets:
        print("nothing to scout (all sourced, or no matching ids).")
        return 0

    stage = SCOUT_DIR / "stage"
    if not args.no_stage:
        stage.mkdir(parents=True, exist_ok=True)

    report: dict[str, list[dict]] = {}
    for entry in targets:
        eid = entry["id"]
        raw: list[tuple] = [(u, "hint", "") for u in entry.get("candidateUrls", [])]
        home = _homepage(entry)
        if home:
            raw += [(u, "homepage", "") for u in _scrape(home)]
        raw += [(u, "commons", lic) for u, lic in _commons(entry["displayName"])]

        seen: set[str] = set()
        results: list[dict] = []
        for url, via, lic in raw:
            if url in seen:
                continue
            seen.add(url)
            results.append(_inspect(url, via, lic))
        results.sort(key=_score, reverse=True)
        report[eid] = results

        best = results[0] if results and _score(results[0]) > 0 else None
        if best:
            if best.get("kind") == "svg":
                d = "svg"
            else:
                sz = f"{best['size'][0]}x{best['size'][1]}"
                tr = f"{best['trim'][0]}x{best['trim'][1]}"
                t = "transp" if best["transparent"] else "opaque"
                pal = " palette" if best["palette"] else ""
                d = f"{sz} trim={tr} {t}{pal}"
            print(f"{eid}: {len(results)} cand -> BEST [{best['via']}] {d}")
            print(f"    {best['url']}")
            if not args.no_stage:
                with contextlib.suppress(requests.RequestException):
                    (stage / f"{eid}.{_ext(best)}").write_bytes(_get(best["url"]).content)
        else:
            print(f"{eid}: {len(results)} cand -> NONE usable")

    SCOUT_DIR.mkdir(parents=True, exist_ok=True)
    (SCOUT_DIR / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nreport -> {(SCOUT_DIR / 'report.json').relative_to(REPO_ROOT)}"
          + ("" if args.no_stage else f"; staged picks -> {stage.relative_to(REPO_ROOT)}/"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
