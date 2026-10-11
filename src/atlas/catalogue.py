"""Parsing Apple Music identifiers out of URLs."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

APPLE_HOSTS = frozenset({"music.apple.com", "classical.music.apple.com"})


@dataclass(frozen=True)
class AppleLink:
    kind: str  # "song" | "album" | "album-track" | "search" | "playlist" | "unknown"
    song_id: str | None
    album_id: str | None


def parse_apple_url(url: str) -> AppleLink:
    """Classify an Apple Music URL. Never guesses: only IDs literally present in the URL are returned."""
    p = urlparse(url)
    if p.scheme != "https" or p.netloc not in APPLE_HOSTS:
        return AppleLink("unknown", None, None)
    parts = [x for x in p.path.split("/") if x]
    query = dict(q.split("=", 1) for q in p.query.split("&") if "=" in q)
    if len(parts) >= 2 and parts[1] == "search":
        return AppleLink("search", None, None)
    if "song" in parts:
        last = parts[-1]
        return AppleLink("song", last if last.isdigit() else None, None)
    if "album" in parts:
        last = parts[-1]
        album_id = last if last.isdigit() else None
        song = query.get("i")
        if song and song.isdigit():
            return AppleLink("album-track", song, album_id)
        return AppleLink("album", None, album_id)
    if "playlist" in parts:
        return AppleLink("playlist", None, None)
    return AppleLink("unknown", None, None)
