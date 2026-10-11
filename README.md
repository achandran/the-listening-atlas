# The Listening Atlas

A curated, pedagogical classical-music listening atlas. Each volume is a sequence of recordings arranged into
stages, with listening questions and prompts, published as a read-only static website with search.

> **Method across the Atlas:** listen to what the music is doing; let expressive understanding arise from
> audible musical relationships.

The first volume is **Bach: Cantabile & Harmony** — eleven hearing stages, 670 selections. *Cantabile* is
that volume's own principle, not a rule for future volumes: each composer's volume defines its own principles
and stage structure as data.

| | |
|---|---|
| Canonical data | `data/` — human-edited YAML, validated by JSON Schemas in `schemas/` |
| Tools | `atlas` CLI — validate, audit, export, build, preview, proposals, (inactive) Apple Music sync |
| Website | static HTML generated into `_site/`, published with GitHub Pages |
| Original inputs | `archive/2026-10-11-handoff/` — byte-identical, checksummed (`archive/PROVENANCE.yaml`) |
| Reports | `reports/<collection>/` — migration report and editorial discrepancy report (generated) |

## Quick start

Requires [uv](https://docs.astral.sh/uv/) (it installs the pinned Python 3.12 and locked dependencies).

```sh
uv sync                          # install from uv.lock
uv run atlas validate            # check the data
uv run atlas build               # generate the website into _site/
uv run atlas serve               # preview at http://127.0.0.1:8000/
uv run pytest                    # run the test suite
```

The site works when opened directly from disk, but the search page loads a JSON file, which browsers
only allow over HTTP — use `atlas serve` for a full local preview.

## Common tasks

| Task | Command |
|---|---|
| Validate (schemas, references, duplicates, URLs, stage rules) | `uv run atlas validate` (`-v` for info, `--strict` to fail on unresolved song IDs) |
| Check every Apple Music URL over the network (slow, optional) | `uv run atlas validate --check-links` |
| Regenerate migration + editorial reports | `uv run atlas audit` (CI runs `atlas audit --check`) |
| Export playlists (full + per stage CSV, legacy CSVs, song-ID list, match report) | `uv run atlas export` → `exports/` |
| Export only importer CSVs | `uv run atlas export --format csv` |
| Check / dry-run / apply an editorial proposal | `uv run atlas proposal check breath-19` · `apply breath-19` · `apply breath-19 --write` |
| Mint IDs for new selections | `uv run atlas new-id -n 3` |
| Plan an Apple Music sync (dry run, no network) | `uv run atlas sync plan --current current-ids.txt` |
| Lint / format / type-check | `uv run ruff check . && uv run ruff format --check . && uv run mypy` |

## Editing a playlist

Playlist order is the order of selections in each stage file under
`data/collections/<collection>/selections/`. To move, add or remove a selection, edit that YAML file, then:

```sh
uv run atlas validate && uv run atlas audit && uv run pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow and [docs/data-model.md](docs/data-model.md) for
every field. Within a playlist each recording may appear only once; the validator enforces this with no override.
Approved changes that are not yet ready (for example the 19-selection Breath sequence) live in
`proposals/` and are applied explicitly — never silently.

## Exports and Apple Music

`atlas export` writes deterministic CSVs in a documented schema suitable for manual-review import through
services such as Soundiiz or TuneMyMusic. **Apple Music does not import arbitrary CSV files directly**, and
text-matching importers can pick the wrong recording; see [docs/exporting.md](docs/exporting.md).

The live Apple Music playlist is never modified by this repository. A phase-two sync command is designed but
disabled; see [docs/apple-music-sync.md](docs/apple-music-sync.md) for what it can and cannot do.

## Publishing

The site deploys to GitHub Pages via `.github/workflows/pages.yml` on every push to `main`, once Pages is
enabled with **Source: GitHub Actions**. See [docs/publishing.md](docs/publishing.md).

## Documentation

- [docs/methodology.md](docs/methodology.md) — the Atlas's method; how volumes differ; adding a composer
- [docs/data-model.md](docs/data-model.md) — files, fields, IDs, validation rules, clean diffs
- [docs/editorial-status.md](docs/editorial-status.md) — open editorial questions and how they are tracked
- [docs/exporting.md](docs/exporting.md) — CSV schema; Soundiiz / TuneMyMusic with manual review
- [docs/apple-music-sync.md](docs/apple-music-sync.md) — phase-two sync design and API limitations
- [docs/publishing.md](docs/publishing.md) — GitHub Pages
- [archive/PROVENANCE.yaml](archive/PROVENANCE.yaml) — origin and checksums of every input file

## Licence

[MIT](LICENSE). Track titles, album names and Apple Music identifiers are third-party catalogue
metadata; no recordings are distributed.
