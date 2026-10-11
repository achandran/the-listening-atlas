"""Deterministic exports: legacy master/transfer CSVs, importer CSVs (full + per stage) and a match report.

No export contains timestamps or other run-dependent values, so re-running an export on unchanged data
produces byte-identical files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .model import Atlas, Collection, Selection
from .snapshot import (
    MASTER_COLUMNS,
    STATUS_KEEP,
    STATUS_REPLACEMENT_ALBUM,
    STATUS_REPLACEMENT_APPROX,
    TRANSFER_COLUMNS,
    Row,
    format_duration,
    format_long_duration,
    render_csv,
    transfer_rows,
)

IMPORTER_COLUMNS: tuple[str, ...] = (
    "Title",
    "Artist",
    "Album",
    "Duration",
    "ISRC",
    "Apple Music ID",
    "Apple Music URL",
    "Composer",
    "Work",
    "Catalogue",
    "Movement",
    "Stage",
    "Position",
    "Selection ID",
    "Match Status",
)

MATCH_EXACT = "exact_song_id"
MATCH_USER = "user_supplied_song_id"
MATCH_ALBUM = "unmatched_album_link"
MATCH_SEARCH = "unmatched_search_link"
MATCH_NONE = "unmatched"


def match_status(s: Selection) -> str:
    if s.song_id:
        return MATCH_USER if s.verification == "user_supplied" else MATCH_EXACT
    return {"album": MATCH_ALBUM, "search": MATCH_SEARCH}.get(s.link_kind or "", MATCH_NONE)


def _status_text(s: Selection) -> str:
    if s.status == "keep":
        return STATUS_KEEP
    return STATUS_REPLACEMENT_APPROX if s.duration_status == "approximate" else STATUS_REPLACEMENT_ALBUM


def legacy_row(atlas: Atlas, c: Collection, s: Selection, position: int) -> Row:
    rec = atlas.recordings[s.recording]
    st = c.stage(s.stage)
    return {
        "position": str(position),
        "stage_number": str(st.number),
        "stage": st.name,
        "title": s.title,
        "artists": s.credits,
        "principal_artist": s.principal_artist or rec.principal_artist,
        "album": s.album_as_listed or rec.album_title or "",
        "duration": format_duration(s.duration),
        "seconds": "" if s.duration is None else str(s.duration),
        "apple_song_id": s.song_id or "",
        "apple_music_url": s.url or "",
        "album_url": s.album_url or "",
        "status": _status_text(s),
        "editorial_note": s.editorial_note or "",
    }


def legacy_rows(atlas: Atlas, c: Collection) -> list[Row]:
    return [legacy_row(atlas, c, s, i) for i, s in enumerate(c.selections(), start=1)]


def importer_row(atlas: Atlas, c: Collection, s: Selection, position: int) -> Row:
    rec = atlas.recordings[s.recording]
    work = atlas.works[s.work]
    st = c.stage(s.stage)
    return {
        "Title": s.title,
        "Artist": s.credits,
        "Album": s.album_as_listed or rec.album_title or "",
        "Duration": format_duration(s.duration),
        "ISRC": "",  # never inferred; left blank until verified from an authoritative source
        "Apple Music ID": s.song_id or "",
        "Apple Music URL": s.url or "",
        "Composer": work.composer or "",
        "Work": work.title,
        "Catalogue": work.catalogue,
        "Movement": s.movement or "",
        "Stage": f"{st.number:02d} {st.name}",
        "Position": str(position),
        "Selection ID": s.id,
        "Match Status": match_status(s),
    }


@dataclass
class ExportFile:
    path: Path  # relative to the export directory
    content: bytes


def build_exports(atlas: Atlas, c: Collection) -> list[ExportFile]:
    positions = c.positions()
    sels = c.selections()
    base = Path(c.id)
    files = [
        ExportFile(
            base / "playlist-full.csv",
            render_csv(IMPORTER_COLUMNS, [importer_row(atlas, c, s, positions[s.id]) for s in sels]),
        ),
        ExportFile(base / "legacy-master.csv", render_csv(MASTER_COLUMNS, legacy_rows(atlas, c))),
        ExportFile(
            base / "legacy-transfer.csv", render_csv(TRANSFER_COLUMNS, transfer_rows(legacy_rows(atlas, c)))
        ),
        ExportFile(
            base / "apple-song-ids.txt", "".join(f"{s.song_id}\n" for s in sels if s.song_id).encode()
        ),
        ExportFile(base / "match-report.md", match_report(atlas, c).encode()),
        ExportFile(base / "student-guide.md", student_guide(atlas, c).encode()),
    ]
    for st in c.stages:
        rows = [importer_row(atlas, c, s, positions[s.id]) for s in st.selections]
        files.append(
            ExportFile(base / "stages" / f"{st.number:02d}-{st.id}.csv", render_csv(IMPORTER_COLUMNS, rows))
        )
    return files


def write_exports(files: list[ExportFile], out_dir: Path) -> list[Path]:
    written = []
    for f in files:
        target = out_dir / f.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f.content)
        written.append(target)
    return written


def match_report(atlas: Atlas, c: Collection) -> str:
    sels = c.selections()
    positions = c.positions()
    counts: dict[str, int] = {}
    for s in sels:
        counts[match_status(s)] = counts.get(match_status(s), 0) + 1
    total = sum(s.duration or 0 for s in sels)
    lines = [
        f"# Match report — {c.title}",
        "",
        f"- Selections: {len(sels)}",
        f"- Sum of known durations: {format_long_duration(total)} "
        f"({sum(1 for s in sels if s.duration is None)} unknown, "
        f"{sum(1 for s in sels if s.duration_status == 'approximate')} approximate)",
    ]
    for k in (MATCH_EXACT, MATCH_USER, MATCH_ALBUM, MATCH_SEARCH, MATCH_NONE):
        if counts.get(k):
            lines.append(f"- `{k}`: {counts[k]}")
    lines += [
        "",
        "Rows without an exact Apple song ID must be matched by hand after import. Importers such as Soundiiz "
        "or TuneMyMusic match by title/artist/album text and can pick the wrong recording; review every row "
        "below and spot-check the rest.",
        "",
        "| Pos | Stage | Selection | Title | Artist | Status | Link |",
        "|---:|---|---|---|---|---|---|",
    ]
    for s in sels:
        ms = match_status(s)
        if ms == MATCH_EXACT:
            continue
        st = c.stage(s.stage)
        title = s.title.replace("|", "\\|")
        lines.append(
            f"| {positions[s.id]} | {st.name} | `{s.id}` | {title} | {s.credits} | {ms} | {s.url or ''} |"
        )
    return "\n".join(lines) + "\n"


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
        f"This guide is generated from the Atlas's canonical data (`atlas export --format guide`). The playlist has "
        f"{len(sels)} selections; the displayed track durations sum to {format_long_duration(total)}"
        + (f", with {missing} tracks still without a duration" if missing else "")
        + ". Editorial questions are listed on the website's Editorial status page.",
        "",
    ]
    if meta.get("public_playlist_url"):
        out += [f"Public playlist: {meta['public_playlist_url']}", ""]
    return "\n".join(out).rstrip("\n") + "\n"
