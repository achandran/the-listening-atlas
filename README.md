# The Listening Atlas

A curated, pedagogical classical-music listening atlas. Each volume is a sequence of recordings arranged into
stages, with listening questions and prompts, published as a read-only static website with search.

> **Method across the Atlas:** listen to what the music is doing; let expressive understanding arise from
> audible musical relationships.

The first volume is **Bach: Cantabile & Harmony** — eleven hearing stages, 674 selections. *Cantabile* is
that volume's own principle, not a rule for future volumes: each composer's volume defines its own principles
and stage structure as data.

| | |
|---|---|
| Canonical data | `data/` — human-edited YAML, validated by JSON Schemas in `schemas/` |
| Tools | `atlas` CLI — validate, build, preview, student guide, Music app playlist check/sync |
| Website | static HTML generated into `_site/`, published with GitHub Pages |
| Apple Music | the `Bach` playlist in the Music app, synced to the public playlist through iCloud |
| Original inputs | `archive/2026-10-11-handoff/` — byte-identical, checksummed (`archive/PROVENANCE.yaml`) |
| Reports | `reports/<collection>/` — migration and editorial review reports, frozen on 2026-10-11 |

## Quick start

Requires [uv](https://docs.astral.sh/uv/) (it installs the pinned Python 3.12 and locked dependencies).

```sh
uv sync                          # install from uv.lock
uv run atlas validate            # check the data
uv run atlas build               # generate the website into _site/
uv run atlas serve               # preview at http://127.0.0.1:8000/
uv run pytest                    # run the test suite
```

The site works when opened directly from disk, but search loads a JSON file, which browsers only allow
over HTTP — use `atlas serve` for a full local preview.

**Site layout:** the home page has the volumes and a search across all of them. Each volume page lists its
stages and has a search for that volume. Stage pages show the music. A ☰ menu on volume pages links to
*About this guide*, *Editorial status* and the Apple Music playlist.

## Common tasks

| Task | Command |
|---|---|
| Validate (schemas, references, duplicates, URLs, stage rules) | `uv run atlas validate` (`-v` for info, `--strict` to fail on unresolved song IDs) |
| Check every Apple Music URL over the network (slow, optional) | `uv run atlas validate --check-links` |
| Generate the student guide (Markdown, always current) | `uv run atlas export` → `exports/` |
| Mint IDs for new selections | `uv run atlas new-id -n 3` |
| Compare the Music app playlist with the data (macOS) | `uv run atlas music check` |
| Remove extra tracks from the Music app playlist | `uv run atlas music apply` (dry run) · `--write` |
| Lint / format / type-check | `uv run ruff check . && uv run ruff format --check . && uv run mypy` |

## Editing a playlist

The usual loop: browse the site, ask Claude Code for a change, review the diff, then sync the Music app.

Playlist order is the order of selections in each stage file under
`data/collections/<collection>/selections/`. To move, add or remove a selection, edit that YAML file, then:

```sh
uv run atlas validate && uv run pytest
uv run atlas music check          # then `music apply`, and any additions or moves by hand
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow, [docs/data-model.md](docs/data-model.md) for
every field and [docs/music-sync.md](docs/music-sync.md) for the Music app sync. Within a playlist each
recording may appear only once; the validator enforces this with no override.

## Publishing

The site deploys to GitHub Pages via `.github/workflows/pages.yml` on every push to `main`, once Pages is
enabled with **Source: GitHub Actions**. See [docs/publishing.md](docs/publishing.md).

## Documentation

- [docs/methodology.md](docs/methodology.md) — the Atlas's method; how volumes differ; adding a composer
- [docs/data-model.md](docs/data-model.md) — files, fields, IDs, validation rules, clean diffs
- [docs/editorial-status.md](docs/editorial-status.md) — open editorial questions and how they are tracked
- [docs/music-sync.md](docs/music-sync.md) — keeping the Music app playlist in step; what is done by hand
- [docs/publishing.md](docs/publishing.md) — GitHub Pages
- [archive/PROVENANCE.yaml](archive/PROVENANCE.yaml) — origin and checksums of every input file

## Licence

[MIT](LICENSE). Track titles, album names and Apple Music identifiers are third-party catalogue
metadata; no recordings are distributed.
