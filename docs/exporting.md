# Exporting playlists

```sh
uv run atlas export                 # everything → exports/<collection>/
uv run atlas export --format csv    # importer CSVs only
```

| File | Purpose |
|---|---|
| `playlist-full.csv` | Whole playlist in the importer schema below |
| `stages/NN-<stage>.csv` | One importer CSV per stage (e.g. to build per-stage playlists) |
| `apple-song-ids.txt` | Exact Apple song IDs, in order, one per line (unmatched selections omitted) |
| `match-report.md` | Every selection without an exact song ID, with its fallback link |
| `legacy-master.csv`, `legacy-transfer.csv` | The handoff's original formats (byte-identical to the archived files while data is unchanged) |

Exports are deterministic: the same data always produces byte-identical files (CI checks this).

## Importer CSV schema

UTF-8 with BOM (for Excel), CRLF line endings, RFC 4180 quoting. Columns, in order:

| Column | Content |
|---|---|
| `Title` | Track title exactly as listed in Apple Music |
| `Artist` | Track credits exactly as listed |
| `Album` | Album title as listed |
| `Duration` | `m:ss`, blank if unknown |
| `ISRC` | Always blank today — ISRCs are never inferred |
| `Apple Music ID` | Exact Apple song ID, blank if not yet matched |
| `Apple Music URL` | Song URL, or the album/search URL used as a fallback |
| `Composer`, `Work`, `Catalogue`, `Movement` | Canonical work metadata |
| `Stage` | e.g. `01 Ground` |
| `Position` | Playlist position (1-based) |
| `Selection ID` | Stable Atlas ID |
| `Match Status` | `exact_song_id`, `user_supplied_song_id`, `unmatched_album_link`, `unmatched_search_link`, `unmatched` |

## Getting the playlist into Apple Music

**Apple Music cannot import a CSV file directly.** Your options:

1. **By hand (most reliable).** Use `match-report.md` and the Apple Music links on the website.
2. **Through a transfer service, with review.** Soundiiz and TuneMyMusic can create an Apple Music playlist
   from an uploaded CSV or text list. They match by title/artist/album text, not by Apple song ID, so they can
   choose a different recording or edition of the same work. Classical metadata makes this especially likely.
   - Upload `playlist-full.csv` (or a stage CSV). Map `Title`, `Artist` and `Album` to the service's fields
     when it asks.
   - Before saving, review **every** row the service marks as uncertain, plus every row whose `Match Status`
     isn't `exact_song_id`, and spot-check the rest against the `Apple Music URL` column.
   - Create a **new** playlist. Don't overwrite the live one.
   - Afterwards, compare the new playlist's tracks with `apple-song-ids.txt` (see
     [apple-music-sync.md](apple-music-sync.md) — `atlas sync plan --current` does this comparison offline).

Both services change their features and limits over time. Check their current documentation, and treat their
output as a draft for review, not as a synchronised copy.
