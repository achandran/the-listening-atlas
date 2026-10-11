# Contributing

Thank you for helping. The Atlas is editorial first: musical and recording decisions belong to the editors.
Code changes should never alter repertoire, order or recordings as a side effect.

## Ground rules

1. **Never edit `archive/`.** Those files are byte-identical inputs with recorded checksums.
2. **Never invent data.** Unknown Apple song IDs, durations, ISRCs, labels or years stay `null`. Mark the
   selection `verification: needs_verification` and, if useful, add an `editorial_note`.
3. **A title alone never identifies a recording.** Match by Apple song ID, and record the recording
   (performer + album) explicitly.
4. **Selection IDs are permanent.** Never renumber, reuse, or derive them from position. Use
   `uv run atlas new-id` for new selections.
5. **Each recording appears at most once per playlist.** Within one collection, a recorded track (an Apple
   song, or the same movement of the same recording) may not be repeated. There is no override.
   Different performances of the same music are allowed.
6. **Flag, don't resolve, editorial questions.** Add an entry to `issues.yaml` instead of changing an
   editorial decision in passing.

## Setup

```sh
uv sync
uv run pytest
```

## Editing playlist data

| Change | How |
|---|---|
| Move a selection | Cut its whole `- id: …` block and paste it at the new place (same or another stage file). |
| Add a selection | `uv run atlas new-id`, then add a block with `work`, `recording`, exact Apple `title` and `credits`, and `apple_music`. Add the work/recording first if they are new. |
| Remove a selection | Move its block into `retired.yaml` with `former_stage`, `retired_on` and `reason`. Don't just delete it. |
| Record a verified song ID | Set `apple_music.song_id` and the song `url`, remove `link_kind`, set `verification: verified`, fill `duration`. |
| Change stage texts | Edit `stages.yaml`. If you change approved wording, keep the original in `itinerary_source`. |
| Add a listening study | `notes/deep-focus.yaml` (keyed by selection ID) or `notes/work-focus.yaml` (keyed by work ID). |
| Prepare a larger editorial change | Write a proposal in `proposals/` (see `breath-19.yaml`), then `atlas proposal check <name>`. |

After every change:

```sh
uv run atlas validate        # 0 errors required
uv run atlas audit           # regenerate reports/ and commit them
uv run pytest
```

Some tests pin approved editorial facts on purpose, for example the first two Ground song IDs, the Hewitt
1994 Inventions, Ólafsson's BWV 989 with its Aria da capo, and Hewitt's later WTC. If an approved editorial
change makes one of them fail, update the test in the same commit and say why in the commit message.

## Applying a proposal

```sh
uv run atlas proposal check breath-19        # what is still missing
uv run atlas proposal apply breath-19        # dry run: lists files it would write
uv run atlas proposal apply breath-19 --write
uv run atlas validate && uv run atlas audit && uv run pytest
```

`apply` refuses to run until every new selection has a recording, the exact Apple title and credits, and a
song ID.

## Code changes

- Python 3.12, `ruff` (lint + format) and `mypy --strict` must pass: `uv run ruff check . && uv run ruff format --check . && uv run mypy`.
- Keep exports and the site deterministic: no timestamps or random values in generated files.
- The website must work without JavaScript, and its JavaScript must work without a network connection
  (apart from the Apple Music links themselves).
- Add or update tests with every behaviour change.

## Adding a new volume (composer)

See [docs/methodology.md](docs/methodology.md#adding-a-volume). Don't copy the Bach volume's principles or
stages into another composer's volume. Each volume's curriculum is written by its editors.
