# Keeping the Apple Music playlist in step

The public playlist (`public_playlist_url` in `collection.yaml`) is a playlist in the Music app on the
editor's Mac, named by `library_playlist` (`Bach`). iCloud syncs changes made there to Apple Music; it can
take a few minutes for the public page to show them.

## Workflow

1. Change the data (by hand or by asking Claude Code), then `uv run atlas validate && uv run pytest`, and
   commit.
2. `uv run atlas music check` reads the playlist from the Music app and compares it with the data.
3. `uv run atlas music apply` shows what it would remove; `--write` removes it. Tracks are removed from the
   playlist only, never from the library.
4. Make any additions or moves by hand (below), then run `atlas music check` again until it reports
   *In sync*.

The Music app must be running, and the first run asks macOS for permission to control it.

## How tracks are matched

Music.app's scripting interface does not expose Apple catalogue song IDs, so a track matches a selection when
a name in the selection's `credits` appears in the track's artist and the durations differ by at most three
seconds. The playlist is aligned against the canonical order, so the check also catches tracks in the wrong
place: a moved track is reported as one removal plus one addition. Titles are not compared, because the
library and the catalogue often word them differently.

For an exact check by song ID, the public playlist page lists the first 300 tracks with their IDs; anything
beyond that needs the Apple Music API (a developer token).

## What has to be done by hand

Music.app can add a track to a playlist only if it is already in the library, and only at the end; it cannot
move tracks. So `atlas music` lists additions with their position and Apple Music link: open the link, add
the song to the playlist, and drag it into place. To move a track, drag it.
