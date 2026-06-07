# CLAUDE.md

Guidance for agents working in this repo. Read `README.md` for the full project
rationale and licensing posture; this file is the working playbook.

## What this repo is

A curated, versioned set of **canonical sailing logos** consumed by Sail Scoring.
The canonical set is a **human curation decision**, not a scrape:
`sources/registry.yaml` is the source of truth, and a pipeline turns it into a
published dataset (`data/manifest.json` + the normalised files in `logos/`).

## The shape of a change

Everything flows from `sources/registry.yaml`. Adding or upgrading a logo means
editing that file and re-running the pipeline — never hand-edit `data/` or
`logos/` (they are generated).

```sh
uv run python scripts/01_fetch.py       # resolve & download assets from registry.yaml
uv run python scripts/02_normalise.py   # trim, cap size, force transparent PNG (or SVGO for vectors)
uv run python scripts/03_manifest.py    # build data/manifest.json (+ provenance.json, unresolved.json) and logos/index.html landing page
uv run python scripts/04_validate.py    # shape, formats, denylist, attribution — must end "dataset valid."
```

Then the dev checks:

```sh
uv run pytest
uv run ruff check
```

`scripts/05_scout.py` is an optional research aid: for entries without an
`assetUrl` it gathers candidate logos (site og:image/icons, Wikimedia, explicit
`candidateUrls`) into `.scout/` for visual review. It **never edits the
registry** — picking a winner stays a human call. `.scout/` is gitignored.

## The logo-upgrade workflow

This is the established pattern (see issues **#4 GP14** and **#5 Skerries** for
worked examples — both closed, with the full decision trail preserved). When
improving a specific logo:

1. **Pick** the entity to improve (usually one flagged `quality: provisional`).
2. **Research** — source every variation you can find. Download each candidate
   and actually look at it: dimensions and transparency (`uv run python -c "from
   PIL import Image; im = Image.open('FILE').convert('RGBA');
   print(im.size, im.getchannel('A').getextrema() != (255, 255))"`), whether it's
   a clean vector/asset or a scan/JPG with a baked background. Beware extensions
   that lie (e.g. a `.ico` that is really a 1024px PNG with alpha).
3. **Decide** against the house standard (below) and, where the call is a real
   curation judgement, ask the user before committing to a direction.
4. **File a GitHub issue** capturing the findings and reasoning *before or with*
   the change. Model it on #4/#5:
   - `## Outcome (done)` — what was chosen, the asset path, `source` URL,
     `sourceKind`, and the `quality` flag.
   - `## Options considered` — a table of every candidate with source, size,
     transparency, and the accept/reject reason.
   - `## Why still open — upgrade path` — what a better asset would look like and
     who to contact, if we're settling for "good enough".
5. **Ship** "good enough for now": update the registry, re-run the pipeline,
   verify the rendered `logos/<id>.png` + `.small.png`, commit, push, and **tag**
   a patch release.
6. **Close the issue** as good enough, with a closing comment pointing at the
   commit/tag and summarising the revisit trail. Closed-but-documented beats a
   pile of open issues — the history stays one click away if we revisit.

The point of the issue is durable, easily-accessible history: the registry
`qualityNote` carries a `See issue #N` back-reference, so anyone landing on the
entry later can find the full reasoning even after the issue is closed.

## House standard for assets

- **Never distort a mark.** Format + size normalisation only — no recolouring,
  no restyling, no manufacturing a logo the owner never issued (e.g. don't bolt
  a wordmark onto a burgee, or recolour an insignia). Source the owner's real
  asset. The normalise step enforces format/size only by design.
- **Prefer** the owner's official, current mark; transparent background; vector
  (SVG) where one exists publicly, otherwise a clean high-res raster.
- **Avoid** baked-in background fills (they show as a coloured bar on a light
  header), extreme aspect ratios, distressed/scan artifacts, and tiny crops.
- `source` records the canonical human-facing/live URL for provenance; when the
  live URL is hotlink-protected or unreliable, commit the bytes to
  `sources/assets/<id>.<ext>` and point `assetUrl` at that local path (the fetch
  step reads local files directly). See the GP14 entry for the pattern.

## Quality flags

- `quality: ok` (default) — a clean, official, on-standard asset.
- `quality: provisional` — a deliberately-kept best-available asset with a known
  limitation. **`qualityNote` is required** and must state the limitation *and*
  what a better asset would be. Validation enforces the note. Reference the
  tracking issue (`See issue #N`) so provisional entries stay revisitable.

## Commit / tag / release conventions

- **One logical change per commit.** Messages: `Source <id> (...)` for a new
  entry, `Upgrade <id> to ...` for a replacement. Include the reasoning and an
  issue reference. End with the `Co-Authored-By` trailer.
- **Tag a patch release** (`vMAJOR.MINOR.PATCH`, annotated) after a sourcing or
  upgrade change — e.g. `v0.1.1 — skerries-sc upgraded to the official
  transparent burgee`. Semantic versioning: patch/minor for entities, assets,
  and provenance; major only for a manifest **schema** break.
- Commit the regenerated `data/` and `logos/` alongside the registry edit so the
  published dataset always matches the registry.

## Heads-up: concurrent edits

Multiple agents have collided on `sources/registry.yaml` in the past, leaving it
briefly malformed (e.g. an entry losing its `- id:` line and silently merging
into its neighbour). Before editing, re-read the region you're touching; after
editing, run `04_validate.py` and sanity-check that the entry count and the
`provisional` list look right. If `git diff` shows churn you didn't make,
reconcile it rather than committing over it.

## Takedown / denylist

If asked to remove a logo: drop the asset, record it in `data/unresolved.json`
with the reason, and add the entity to the denylist in `sources/registry.yaml`
so the pipeline won't re-fetch it. See `README.md` → Takedown.
