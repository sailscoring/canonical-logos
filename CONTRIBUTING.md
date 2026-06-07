# Contributing

Thanks for helping build the canonical sailing logo library.

## I just want to request a logo (no coding)

Open an issue — pick the matching form on the
[new-issue page](https://github.com/sailscoring/canonical-logos/issues/new/choose):

- **Request a new logo** — add an entity's logo to the library
- **Request a logo update** — an existing one is wrong, outdated, or a better file exists
- **Request a takedown** — you own a logo here and want it removed or corrected
  (or just email **mark@hyc.ie** — actioned promptly)

## I want to add or upgrade a logo (code)

`sources/registry.yaml` is the source of truth; a pipeline turns it into the
published dataset (`data/manifest.json` + the normalised files in `logos/`).
Never hand-edit `data/` or `logos/` — they are generated.

The full playbook — sourcing, the house standard, quality flags, and
commit/tag/release conventions — is in **[CLAUDE.md](./CLAUDE.md)**. In short:

1. Add or edit the entity in `sources/registry.yaml`. (Optional: run
   `scripts/05_scout.py` to gather candidate logos for review — it never edits
   the registry.)
2. Run the pipeline; `04_validate.py` must end `dataset valid.`:
   ```sh
   uv run python scripts/01_fetch.py
   uv run python scripts/02_normalise.py
   uv run python scripts/03_manifest.py
   uv run python scripts/04_validate.py
   ```
3. `uv run pytest` and `uv run ruff check` must pass.
4. Commit the registry edit **together with** the regenerated `data/` and
   `logos/`, so the published dataset always matches the registry.

**Dev setup:** Python 3.12+ with [uv](https://docs.astral.sh/uv/), and
[SVGO](https://github.com/svg/svgo) (`npm install -g svgo`) for vector
minification. See the [README](./README.md).

## Posture

Logos remain their owners' property. We host them in good faith for use by
scorers connected to the entity, never distort a mark (format/size normalisation
only), and remove anything on request. See the README's "Nature of this
dataset" and "Takedown".
