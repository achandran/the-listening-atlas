# Editorial status

The generated, always-current list is in
[`reports/bach-cantabile-harmony/editorial-discrepancies.md`](../reports/bach-cantabile-harmony/editorial-discrepancies.md)
(`uv run atlas audit`), built from `data/collections/bach-cantabile-harmony/issues.yaml`. Readers see a summary
on the website's *Editorial status* page.

**Current state (after the 2026-10-11 review): no open issues.** All 674 selections have exact Apple song IDs
and durations, and `atlas validate --strict` passes with no findings.

## Changes since the migration

- **Ground opening.** Ground opens with Trifonov's Anh. 114 → Anh. 116 → Anh. 121, then the 18 Hewitt
  preludes in catalogue order. Anh. 120 is retired, and its close-listening study is kept in `retired.yaml`.
- **Breath, the approved 19.** Applied with five tracks the editor confirmed from Apple's catalogue: Hewitt's
  Mary Howe transcription, Suzuki BWV 147/X, Hunt Lieberson BWV 199/IV, Schlick/Herreweghe BWV 21/III
  (remastered) and Suzuki BWV 127/III. Fleisher is retired, and his study carried over to the Howe
  transcription.
- **Line.** All 30 Hewitt (Hyperion, 1994) Inventions & Sinfonias are matched, replacing the leftover Schiff
  titles. Invention No. 1 is BWV 772.
- **Span.** Ólafsson's BWV 989 is matched on his DG 2018 album, the same album as his BWV 659. Suzuki's
  BWV 582 track is confirmed to include the fugue.
- **Order.** Hewitt's WTC album is confirmed as the later cycle (℗ 2009 Hyperion).
- **Convergence.** "Erbarme dich" is refiled under the St Matthew Passion album, where the same song appears as
  No. 39.
- **Essence.** The Musical Offering is confirmed to be in Suzuki's recorded order.
- **Student guide.** It is now generated from the data (`atlas export --format guide`); the archived guide is
  kept as a historical record.

## Resolved issues

| ID | Stage | Outcome |
|---|---|---|
| ED-001 | Ground | Keep BWV 924 first; Hewitt preludes stay in catalogue order |
| ED-002 | Ground | Moot — Anh. 120 retired |
| ED-003 | Breath | Approved 19-selection sequence applied |
| ED-004 | Line | 30 Hewitt tracks matched on album `1721143424` (℗ 1994 Hyperion) |
| ED-005 | Line | Invention No. 1 is BWV 772 (772a came from Schiff's track) |
| ED-006 | Span | 12 Ólafsson tracks matched on album `1410551592` (℗ 2018 DG) |
| ED-007 | Span | BWV 582 track contains Passacaglia and Fugue |
| ED-008 | Order | Album `1721145434` is Hewitt's later WTC (℗ 2009) |
| ED-009 | Convergence | "Erbarme dich" = No. 39 on the Passion album; dead compilation link replaced |
| ED-010 | Essence | Playlist order = album tracks 1–16 (recorded order) |
| ED-011 | — | Itineraries updated; student guide generated from data |
| ED-012 | — | Previously hidden work notes now display |
| ED-013 | — | HTML "Replaces Angela Hewitt Decca" slip; CSV text (Schiff) used |
| ED-014 | — | "E-FlA" kept as Apple's title, corrected `display_title` shown; organ credit fixed |
| ED-015 | Ground | Durations for Anh. 116 (1:12) and Anh. 121 (1:33) |

Optional editorial work that remains: close-listening studies for the new Trifonov minuets (Anh. 116, Anh. 121).

## How tracks were matched

Exact song IDs, titles, credits and durations come from Apple's public catalogue:
- the iTunes Lookup API (`https://itunes.apple.com/lookup?id=<album or song id>&entity=song`), or
- an album page's embedded track data where the API returns no tracks.

Every match was confirmed by the editor. Track titles and credits are stored as Apple's catalogue gives them,
and durations are whole seconds rounded down, the same convention as the original playlist export.

## Adding a new issue

1. Add an entry to `issues.yaml` (`ED-0NN`, stage, title, detail, affected selection IDs, action).
2. When it is decided, make the data change, set `status: resolved` (or `wont_fix`) and record the decision in
   `detail`.
3. `uv run atlas validate && uv run atlas audit && uv run pytest`, then commit data and reports together.
