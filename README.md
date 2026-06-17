# canonical-logos

A maintained, versioned set of **canonical sailing logos** — governing bodies,
sailing clubs, class associations, recurring sponsors, and non-club venues —
built to be consumed by [Sail Scoring](https://app.sailscoring.ie) as the
built-in tier of its shared logo library.

A scorer building a series reaches for these so the venue, class, governing
body, or sponsor is shown with a clean, current, official asset rather than a
decayed ad-hoc URL or a stretched screenshot. It is the sibling of
[`sailscoring/national-letters`](https://github.com/sailscoring/national-letters)
and borrows its methodology (versioned dataset repo, per-asset provenance
manifest, build-time consumption, scheduled rebuild). The licensing posture is
the inverse — see [Nature of this dataset](#nature-of-this-dataset).

> **Status: sourcing in progress.** The pipeline (fetch → normalise → manifest
> → validate) and the scout are implemented; an initial set of logos is sourced,
> with more tracked in the GitHub issues. See `CLAUDE.md` for the contributor
> playbook; the original design rationale lives in the Sail Scoring repo.

## What's in a release

Each tagged GitHub Release will attach:

- **`manifest.json`** — the canonical dataset: every logo, its `id`, `class`
  (`governing-body` / `sailing-club` / `class-assoc` / `sponsor` / `venue` / `regatta`),
  display name,
  file + format + `sha256`, available colourway variants, source provenance
  (`sourceUrl`, `sourceKind`, `retrievedAt`), the org's official homepage
  (`homepageUrl`, optional — the default click-through target a consumer applies
  when a scorer picks the logo), and a `quality` flag (`ok`, or `provisional`
  with a `qualityNote` for a sub-par best-available asset kept deliberately and
  flagged for upgrade).
- **`logos.tar.gz`** — all normalised logo files (SVG where the owner has one;
  otherwise a normalised transparent PNG, plus a small derivative for the
  ~100 px results-header slot).
- **`unresolved.json`** — entities we wanted but couldn't source a clean asset
  for, or that are on the takedown/denylist, with reasons. A visible audit
  ledger.

## Nature of this dataset

This repository hosts third-party logos that **remain the property of their
respective owners**. It does not claim a licence to each. The posture is
good-faith and low-risk, mirroring what clubs already do across the sport when
they put a sponsor's or class's logo on a results page:

- The **legitimate basis** for using a logo sits with the scorer or organiser
  who selects it — they have a sponsorship agreement, they represent the club,
  or they are running that class's event. This library makes acting on that
  basis easy, and makes the result *better for the owner*: prominent, correct,
  current artwork. For a sponsor, prominence is the whole point of the
  sponsorship.
- We **don't seek per-asset permission up front.** We source a clean asset,
  record its provenance, and stand ready to remove it.
- We **never distort a mark** — format and size normalisation only, no
  recolouring or restyling. Official colourways (light/dark) are offered where
  the owner publishes them.
- We **honour explicit restrictions and objections.** If an entity's published
  terms forbid third-party hosting, or it asks us to stop, it goes on the
  denylist and is removed. See [Takedown](#takedown).

The **tooling and the manifest** (factual provenance data) are released under
the MIT licence. The **logo assets** are owned by others; see [LICENSE](./LICENSE).

## Takedown

If you own a logo hosted here and would like it removed or corrected, email
**mark@hyc.ie**. Removals are actioned promptly and recorded in
`data/unresolved.json` with the reason, and the entity is added to the denylist
in `sources/registry.yaml` so it is not re-fetched.

## Consuming this dataset

Build-time download of a tagged release, identical in shape to national-letters:
pin a tag, fetch `manifest.json` + `logos.tar.gz`, verify the SHA, extract into
a gitignored path. Canonical logos are referenced by a stable public URL
(`logos.sailscoring.ie/...`) rather than inlined into published results HTML —
the reference is the point, and mixed image formats don't inline cleanly. Clean
SVGs may optionally be inlined for the offline-archival case — a possible future
enhancement on the consuming side.

## Layout

- `sources/registry.yaml` — the hand-maintained list of canonical entities (the
  curation decision) plus the takedown denylist
- `sources/` — committed raw inputs and any usage terms an owner published, for
  provenance and diffability
- `scripts/` — fetch → normalise → manifest → validate pipeline
- `logos/` — normalised per-entity assets
- `data/` — published dataset (`manifest.json`, `unresolved.json`)

## Development

Requires Python 3.12+ and [`uv`](https://docs.astral.sh/uv/). The SVG
normalisation step also needs [SVGO](https://github.com/svg/svgo)
(`npm install -g svgo`); without it, vectors are passed through un-minified
(still valid) and a warning is printed — raster normalisation is unaffected.

```sh
uv sync
uv run pytest
uv run ruff check
```

### Pipeline

```sh
uv run python scripts/01_fetch.py       # resolve & download assets from registry.yaml
uv run python scripts/02_normalise.py   # SVGO (vectors) / Pillow (rasters); format + size only
uv run python scripts/03_manifest.py    # build data/manifest.json with post-normalisation sha256 (+ logos/index.html landing page)
uv run python scripts/04_validate.py    # shape, formats, denylist, attribution, exclusions
```

`scripts/05_scout.py` is an optional research aid: for entries without an
`assetUrl` it proposes candidate logos (homepage og:image/icons, Wikimedia,
explicit `candidateUrls`) into `.scout/` for review — it never edits the registry.

Curation lives in `sources/registry.yaml`: adding a logo is editing that file
and re-running the pipeline. The canonical set is a human decision, not a scrape.
See `CLAUDE.md` for the full contributor / logo-upgrade workflow.

## Contributing

To **request** a logo (add / update / takedown), open an issue using the forms
on the [new-issue page](https://github.com/sailscoring/canonical-logos/issues/new/choose).
To **contribute** a logo or code, see [CONTRIBUTING.md](./CONTRIBUTING.md) and
[CLAUDE.md](./CLAUDE.md).

## Versioning

Semantic versioning. `v1.x.y` adds entities, refreshes assets, or fixes
provenance; a major bump is reserved for a breaking change to the manifest
schema.

## Licence

- **Tooling and manifest** (`scripts/`, `data/manifest.json`,
  `data/unresolved.json`): MIT.
- **Logo assets** (`logos/`): owned by their respective owners; hosted in good
  faith, removable on request. See [LICENSE](./LICENSE) and [Takedown](#takedown).
