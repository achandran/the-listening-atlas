"""Parsing catalogue numbers (BWV …) and Apple Music identifiers out of free text and URLs."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlparse

_BWV = re.compile(r"\bBWV\.?\s*(?P<anh>Anh\.?\s*)?(?P<num>\d+)(?P<suffix>[a-zA-Z]?)(?:/(?P<sub>\d+))?", re.I)
_BWV_SLUG = re.compile(r"\bbwv-(?P<anh>anh-)?(?P<num>\d+)(?P<suffix>[a-z]?)\b")


@dataclass(frozen=True)
class CatalogueRef:
    catalogue: str  # e.g. "BWV"
    number: str  # e.g. "Anh. 114", "1060R", "772a"
    sub: str | None  # e.g. "9" in "BWV 208/9"
    span: tuple[int, int]  # location in the source text (or (-1, -1) if not from the title)

    @property
    def work_id(self) -> str:
        return f"{self.catalogue.lower()}-{slugify(self.number)}"

    @property
    def label(self) -> str:
        return f"{self.catalogue} {self.number}"


def _ref(m: re.Match[str], from_title: bool) -> CatalogueRef:
    num = m.group("num") + m.group("suffix")
    if m.group("anh"):
        num = f"Anh. {num}"
    sub = m.groupdict().get("sub")
    return CatalogueRef("BWV", num, sub, m.span() if from_title else (-1, -1))


def find_bwv(title: str) -> CatalogueRef | None:
    m = _BWV.search(title)
    return _ref(m, True) if m else None


def find_bwv_in_slug(url: str) -> CatalogueRef | None:
    m = _BWV_SLUG.search(urlparse(url).path)
    if not m:
        return None
    num = m.group("num") + m.group("suffix").upper()
    if m.group("anh"):
        num = f"Anh. {num}"
    return CatalogueRef("BWV", num, None, (-1, -1))


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text


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
