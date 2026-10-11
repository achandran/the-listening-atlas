"""Keep a playlist in the local Music app (macOS) in step with the canonical data.

The library playlist syncs to Apple Music through iCloud, so this is how the public playlist is updated.

Music.app's scripting interface does not expose Apple catalogue song IDs, so tracks are matched to
selections by performer and duration (and order): a track matches a selection when at least one name word of
the selection's credits appears in the track's artist and the durations differ by at most
``DURATION_TOLERANCE`` seconds. The playlist is aligned against the canonical order with a longest common
subsequence, so a moved track shows up as one removal plus one addition.

Only removals can be applied automatically. Music.app can add a track to a playlist only if it is already in
the library, and only at the end; additions and reorders are listed with their Apple Music links for doing
by hand.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field

from .model import Collection, Selection

DURATION_TOLERANCE = 3  # seconds
FIELD_SEP = "\x1f"
RECORD_SEP = "\x1e"

# Words in credits that say nothing about who is performing.
_STOPWORDS = {"and", "the", "der", "die", "das", "von", "van", "de", "la", "le", "of", "for"}


class MusicAppError(RuntimeError):
    pass


@dataclass(frozen=True)
class Track:
    index: int  # 1-based position in the playlist
    persistent_id: str
    name: str
    artist: str
    album: str
    duration: float | None


@dataclass
class Plan:
    playlist: str
    selections: int
    tracks: int
    remove: list[Track] = field(default_factory=list)
    add: list[tuple[int, Selection]] = field(default_factory=list)  # (canonical position, selection)

    @property
    def in_sync(self) -> bool:
        return not (self.remove or self.add)

    def summary(self) -> str:
        lines = [
            f'Playlist "{self.playlist}": {self.tracks} tracks · canonical order: {self.selections} selections',
        ]
        if self.in_sync:
            lines.append("In sync: every track matches the canonical order (performer, duration, position).")
            return "\n".join(lines)
        if self.remove:
            lines += ["", f"To remove ({len(self.remove)}):"]
            lines += [f"  {t.index:>4}  {t.name} | {t.artist} | {t.album}" for t in self.remove]
        if self.add:
            lines += ["", f"To add by hand ({len(self.add)}) — position in canonical order:"]
            for pos, s in self.add:
                lines.append(f"  {pos:>4}  {s.title} | {s.credits} | {s.url or 'no link'}")
            lines += [
                "",
                "Music.app can only append tracks that are already in the library, so additions and reorders "
                "are done by hand: open each link, add the song to the playlist, then drag it into place.",
            ]
        return "\n".join(lines)


# ------------------------------------------------------------------------------------------- matching


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[^\W\d_]+", text.casefold()) if len(w) > 1 and w not in _STOPWORDS}


def matches(s: Selection, t: Track) -> bool:
    if not (_words(s.credits) & _words(t.artist)):
        return False
    if s.duration is None or t.duration is None:
        return bool(_words(s.title) & _words(t.name))
    return abs(s.duration - t.duration) <= DURATION_TOLERANCE


def plan(playlist: str, sels: list[Selection], tracks: list[Track]) -> Plan:
    """Align the playlist with the canonical order (LCS under :func:`matches`)."""
    n, m = len(sels), len(tracks)
    lcs = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            if matches(sels[i], tracks[j]):
                lcs[i][j] = lcs[i + 1][j + 1] + 1
            else:
                lcs[i][j] = max(lcs[i + 1][j], lcs[i][j + 1])
    p = Plan(playlist, n, m)
    i = j = 0
    while i < n and j < m:
        if matches(sels[i], tracks[j]) and lcs[i][j] == lcs[i + 1][j + 1] + 1:
            i, j = i + 1, j + 1
        elif lcs[i + 1][j] >= lcs[i][j + 1]:
            p.add.append((i + 1, sels[i]))
            i += 1
        else:
            p.remove.append(tracks[j])
            j += 1
    p.add += [(k + 1, sels[k]) for k in range(i, n)]
    p.remove += tracks[j:]
    return p


# ------------------------------------------------------------------------------------------- Music.app


def _osascript(script: str, *args: str) -> str:
    try:
        res = subprocess.run(
            ["osascript", "-", *args], input=script, capture_output=True, text=True, timeout=300, check=False
        )
    except FileNotFoundError as exc:
        raise MusicAppError("osascript not found: the Music app commands only work on macOS") from exc
    if res.returncode != 0:
        raise MusicAppError(res.stderr.strip() or f"osascript exited with {res.returncode}")
    return res.stdout


_FIND = """
on findPlaylist(playlistName)
  tell application "Music"
    set found to (every user playlist whose name is playlistName)
    if (count of found) is 0 then error "no playlist named " & quoted form of playlistName
    if (count of found) > 1 then error "more than one playlist named " & quoted form of playlistName
    return item 1 of found
  end tell
end findPlaylist
"""

_READ = (
    _FIND
    + """
on run argv
  set p to findPlaylist(item 1 of argv)
  set fs to character id 31
  set rs to character id 30
  tell application "Music"
    set n to count of tracks of p
    if n is 0 then return ""
    set pids to persistent ID of every track of p
    set nms to name of every track of p
    set ars to artist of every track of p
    set als to album of every track of p
    set dus to duration of every track of p
  end tell
  set out to {}
  repeat with i from 1 to n
    set end of out to (item i of pids) & fs & (item i of nms) & fs & (item i of ars) & fs & (item i of als) & fs & ((item i of dus) as text)
  end repeat
  set AppleScript's text item delimiters to rs
  return out as text
end run
"""
)

# Deletes from the end so earlier indexes stay valid; checks each index still holds the expected track.
_DELETE = (
    _FIND
    + """
on run argv
  set p to findPlaylist(item 1 of argv)
  set nDeleted to 0
  tell application "Music"
    repeat with k from 2 to (count of argv) by 2
      set idx to (item k of argv) as integer
      set pid to item (k + 1) of argv
      if persistent ID of track idx of p is not pid then error "track " & idx & " is no longer " & pid
    end repeat
    repeat with k from 2 to (count of argv) by 2
      delete track ((item k of argv) as integer) of p
      set nDeleted to nDeleted + 1
    end repeat
    return (nDeleted as text) & " " & ((count of tracks of p) as text)
  end tell
end run
"""
)


def parse_tracks(output: str) -> list[Track]:
    tracks = []
    for i, rec in enumerate((r for r in output.rstrip("\n").split(RECORD_SEP) if r), start=1):
        pid, name, artist, album, dur = rec.split(FIELD_SEP)
        try:
            duration: float | None = float(dur.replace(",", "."))
        except ValueError:
            duration = None
        tracks.append(Track(i, pid, name, artist, album, duration))
    return tracks


def read_playlist(name: str) -> list[Track]:
    return parse_tracks(_osascript(_READ, name))


def remove_tracks(name: str, tracks: list[Track]) -> tuple[int, int]:
    """Remove tracks from the playlist (not from the library). Returns (removed, tracks left)."""
    args: list[str] = []
    for t in sorted(tracks, key=lambda t: t.index, reverse=True):
        args += [str(t.index), t.persistent_id]
    removed, left = _osascript(_DELETE, name, *args).split()
    return int(removed), int(left)


def playlist_name(c: Collection) -> str:
    name = c.meta.get("library_playlist")
    if not name:
        raise MusicAppError(
            f"{c.id}: set `library_playlist` in collection.yaml to the Music app playlist name"
        )
    return str(name)
