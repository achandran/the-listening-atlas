"""Deterministic exports: the student guide, generated from canonical data.

No export contains timestamps or other run-dependent values, so re-running an export on unchanged data
produces byte-identical files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .model import Atlas, Collection, Selection

MATCH_EXACT = "exact_song_id"
MATCH_USER = "user_supplied_song_id"
MATCH_ALBUM = "unmatched_album_link"
MATCH_SEARCH = "unmatched_search_link"
MATCH_NONE = "unmatched"


def match_status(s: Selection) -> str:
    if s.song_id:
        return MATCH_USER if s.verification == "user_supplied" else MATCH_EXACT
    return {"album": MATCH_ALBUM, "search": MATCH_SEARCH}.get(s.link_kind or "", MATCH_NONE)


def format_long_duration(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m:02d}m {s:02d}s"


@dataclass
class ExportFile:
    path: Path  # relative to the export directory
    content: bytes


def build_exports(atlas: Atlas, c: Collection) -> list[ExportFile]:
    return [ExportFile(Path(c.id) / "student-guide.md", student_guide(atlas, c).encode())]


def write_exports(files: list[ExportFile], out_dir: Path) -> list[Path]:
    written = []
    for f in files:
        target = out_dir / f.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f.content)
        written.append(target)
    return written


def student_guide(atlas: Atlas, c: Collection) -> str:
    """The collection's student guide as Markdown, generated from canonical data so it cannot go stale.

    Follows the structure of the handoff's guide: vision, how to use, each stage's principle / question /
    direction / itinerary / piano exercise with its current track range and timing, then listening beyond.
    """
    meta = c.meta
    guide = meta.get("guide") or {}
    positions = c.positions()
    out = [f"# {guide.get('title', c.title)}", ""]
    if guide.get("subtitle"):
        out += [f"*{guide['subtitle']}*", ""]
    if meta.get("epigraph"):
        out += [f"> {meta['epigraph']}", ""]
    if meta.get("vision"):
        out += ["# The vision", ""]
        for para in meta["vision"]:
            out += [para, ""]
    if meta.get("how_to_use"):
        out += ["# How to use the guide", ""]
        out += [f"- {item}" for item in meta["how_to_use"]]
        out.append("")
    out += [f"# {guide.get('stages_heading', 'Stages')}", ""]
    total = 0
    for st in c.stages:
        secs = sum(s.duration or 0 for s in st.selections)
        total += secs
        out += [f"## {st.number:02d}  {st.name}", ""]
        for label, text in (
            ("Principle", st.principle),
            ("Listening question", st.question),
            ("Direction", st.direction),
            ("Recording itinerary", st.itinerary),
            ("At the piano", st.at_the_piano),
        ):
            out += [f"**{label}** — {text}", ""]
        if st.selections:
            first, last = positions[st.selections[0].id], positions[st.selections[-1].id]
            missing = sum(1 for s in st.selections if s.duration is None)
            note = "sum of displayed track times" + (f"; {missing} without a duration" if missing else "")
            out += [
                f"**Playlist tracks** — {first}–{last} · {len(st.selections)} tracks · "
                f"{format_long_duration(secs)} ({note})",
                "",
            ]
    if meta.get("beyond_the_sequence"):
        out += ["# Listening beyond the sequence", ""]
        for para in meta["beyond_the_sequence"]:
            out += [para, ""]
    sels = c.selections()
    missing = sum(1 for s in sels if s.duration is None)
    out += [
        "# Recording and timing note",
        "",
        f"This guide is generated from the Atlas's canonical data (`atlas export`). The playlist has "
        f"{len(sels)} selections; the displayed track durations sum to {format_long_duration(total)}"
        + (f", with {missing} tracks still without a duration" if missing else "")
        + ". Editorial questions are listed on the website's Editorial status page.",
        "",
    ]
    if meta.get("public_playlist_url"):
        out += [f"Public playlist: {meta['public_playlist_url']}", ""]
    return "\n".join(out).rstrip("\n") + "\n"
