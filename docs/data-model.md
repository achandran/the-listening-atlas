# Data model

All canonical data is YAML under `data/`, validated against JSON Schemas in `schemas/` and then
cross-checked by `atlas validate`. YAML is written with stable key order and no line folding, so a one-field
change is a one-line diff.

```
data/
  atlas.yaml                        Atlas title, cross-volume method, list of collections
  works/bach.yaml                   musical works (one file per composer)
  recordings.yaml                   recordings / releases, shared by all collections
  collections/<collection>/
    collection.yaml                 volume metadata, principle, intro texts, fallback prompts, stage file order
    stages.yaml                     stages: number, name, principle, question, direction, piano, itinerary, constraints
    selections/NN-<stage>.yaml      the playlist — ordered selections for one stage
    notes/work-focus.yaml           work-level listening notes, keyed by work ID
    notes/deep-focus.yaml           close-listening studies, keyed by selection ID
    issues.yaml                     editorial issue register (ED-001 …)
    retired.yaml                    selections removed from the playlist, kept with reason and date
    proposals/*.yaml                approved-but-unapplied editorial changes
```

## Entities

**Work** (`works/*.yaml`) — `id` (`bwv-812`, `bwv-anh-114`), `catalogue` (`BWV 812`), `title`, `composer`
(`null` when attribution is uncertain), optional `attribution_note`. Works are reused across selections,
stages and collections.

**Recording** (`recordings.yaml`) — a performance as released in Apple Music: `id`, `principal_artist`
(pianist / ensemble / conductor), `album_title`, `apple_album_id`, `label`, `release_year`, `version` (e.g.
"Hewitt's later WTC, rec. 2008"), `verification`, optional `notes` and `sources`. Label and year are filled
only where a source states them; otherwise they are `null`.

**Stage** (`stages.yaml`) — `id`, `number` (1…N, contiguous), `name`, `principle`, `question`, `direction`,
`at_the_piano`, `itinerary`, optional `itinerary_source` (original wording before an approved factual
update), `editorial_notice`, and `constraints`:
- `max_selections` — e.g. Breath ≤ 19
- `pinned_opening_song_ids` — e.g. Ground must open with `1577781357`, `1577780575`

**Selection** (`selections/*.yaml`) — one playlist entry:

| Field | Meaning |
|---|---|
| `id` | Stable, opaque (`s-` + 7 chars). Never reused, never derived from position. |
| `work`, `movement`, `arrangement` | What is heard. `movement: null` for single-movement works. |
| `recording` | Which performance. |
| `title`, `credits` | Exactly as listed in Apple Music (typos included). |
| `principal_artist`, `album_as_listed` | Only when they differ from the recording's. |
| `duration` | Seconds, or `null`. `duration_status: approximate` when not from Apple. |
| `apple_music.song_id` / `url` / `album_url` | Exact Apple identifiers; `song_id: null` if unmatched. |
| `link_kind` | `album` or `search` when `url` is a fallback, not a track. |
| `status` | `keep` or `replacement_selected` (an approved replacement still being matched). |
| `verification` | `verified` · `snapshot_matched` (from the 669-row export) · `user_supplied` · `needs_verification` |
| `editorial_note` | Free text, verbatim from the source where migrated. |
| `source` | Provenance: `{snapshot, position}` and, where the work was not named in the title, `work_inferred_from`. |

## Invariant: each recording at most once per playlist

Within one collection's playlist, every recorded track appears **at most once**. "Recorded track" means an
Apple song ID, and independently the same work + movement + arrangement from the same recording. This rule
has no override. Different performances of the same music (e.g. a vocal original and a piano transcription,
or two ensembles) are allowed. The rule is enforced by `atlas validate` and by `atlas proposal check`.

## Order

There is no stored `order` or `position` field. **Playlist order is list order**: stages in the order given
by `collection.yaml` → `stage_files` (which must match ascending stage numbers), then selections in file order.
Positions are computed when exporting or building the site.

That's what keeps diffs clean. Moving one selection is a cut-and-paste of its block:

```diff
@@ -35,6 +35,22 @@ selections:
     source:
       snapshot: master-669
       position: 2
+  - id: s-amydr6o
+    work: bwv-939
+    movement: null
+    recording: hewitt-plays-bach-and-more
+    title: Prelude in C Major, BWV 939
+    credits: Angela Hewitt
+    duration: 37
+    apple_music:
+      song_id: '1852229990'
+      url: https://music.apple.com/us/song/prelude-in-c-major-bwv-939/1852229990
+      album_url: https://music.apple.com/us/album/prelude-in-c-major-bwv-939/1852229971
+    status: keep
+    verification: snapshot_matched
+    source:
+      snapshot: master-669
+      position: 15
   - id: s-cvmqbut
     work: bwv-924
@@ -227,22 +243,6 @@ selections:
     source:
       snapshot: master-669
       position: 14
-  - id: s-amydr6o
-    work: bwv-939
-    … (same 16 lines removed)
```

*(Illustration only — this is the open question ED-001 and has **not** been applied.)* `git diff --stat`
reports `16 insertions(+), 16 deletions(-)`. No other selection changes, and no renumbering. `atlas audit`
then lists every selection whose computed position moved in `reports/…/migration-report.md`.

## Validation rules (`atlas validate`)

| Code | Level | Rule |
|---|---|---|
| `SCHEMA`, `YAML-SYNTAX` | error | File structure, types, enums, unknown fields |
| `DUPLICATE-SELECTION-ID`, `RETIRED-ID-REUSED` | error | Selection IDs are unique across active and retired |
| `DUPLICATE-WORK-ID`, `DUPLICATE-RECORDING-ID` | error | |
| `MISSING-WORK`, `MISSING-RECORDING` | error | References must resolve |
| `STAGE-NUMBER-INVALID / -DUPLICATE / -GAP`, `STAGE-ORDER`, `STAGE-FILE-ORDER`, `STAGE-FILE-NUMBER` | error | Stages numbered 1…N; files in matching order |
| `PINNED-OPENING`, `STAGE-TOO-LONG` | error | Per-stage editorial constraints |
| `BAD-URL`, `MISSING-URL`, `LINK-KIND` | error | https Apple Music URLs; fallback links must be declared |
| `SONG-ID-MISMATCH`, `SONG-ID-NOT-RECORDED` | error | `song_id` must equal the ID in the URL |
| `VERIFICATION-INCONSISTENT` | error | A "matched" selection must have a song ID |
| `DUPLICATE-SONG` | error | Same Apple song twice in one collection (invariant, no override) |
| `DUPLICATE-MOVEMENT` | error | Same work + movement + arrangement **from the same recording** twice (invariant, no override) |
| `REPEATED-MOVEMENT` | info | Same work + movement in a *different* recording — allowed; listed so a re-release of the same performance can be spotted |
| `DUPLICATE-SOURCE-ROW` | error | Two selections claim the same snapshot row |
| `DANGLING-NOTE`, `DANGLING-ISSUE-REF` | error | Notes and issues point at real IDs |
| `UNRESOLVED-SONG-IDS` | warning | Selections without an exact song ID (`--strict` makes this fail) |
| `LINK-UNREACHABLE` | warning | Only with `--check-links` (network) |

Titles are never used to decide identity. Duplicates are detected by song ID and by work/movement/
arrangement/recording.

## Migration provenance

The initial data was produced once by `atlas migrate` from `archive/2026-10-11-handoff/`. Tests prove that
the migration reproduces the 669-row master CSV **byte for byte**. They also check that every snapshot row
is accounted for, either as an active selection or in `retired.yaml`, and that the opening Ground song IDs are
intact. `reports/<collection>/migration-report.md` shows the current state against the snapshot.
