"""Reading and writing the legacy 14-column master snapshot format.

The handoff's master CSV is UTF-8 with a BOM, CRLF line endings and minimal quoting. Writing rows back
with :func:`write_master_csv` reproduces that file byte for byte, which the migration tests rely on.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

MASTER_COLUMNS: tuple[str, ...] = (
    "position",
    "stage_number",
    "stage",
    "title",
    "artists",
    "principal_artist",
    "album",
    "duration",
    "seconds",
    "apple_song_id",
    "apple_music_url",
    "album_url",
    "status",
    "editorial_note",
)

TRANSFER_COLUMNS: tuple[str, ...] = ("Title", "Artist", "Album", "Stage", "Apple Music URL")

# Raw status strings used by the snapshot, mapped to canonical (status, link) pairs.
STATUS_KEEP = "Keep"
STATUS_REPLACEMENT_ALBUM = (
    "Replacement selected — album link; individual Apple Music track URL pending verification"
)
STATUS_REPLACEMENT_APPROX = "Replacement selected — catalog duration approximate; individual Apple Music track URL pending verification"

Row = dict[str, str]


def read_master_csv(path: Path) -> list[Row]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != MASTER_COLUMNS:
            raise ValueError(f"{path}: unexpected columns {reader.fieldnames!r}")
        return [dict(row) for row in reader]


def render_csv(columns: tuple[str, ...], rows: list[Row], *, bom: bool = True, crlf: bool = True) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(columns), lineterminator="\r\n" if crlf else "\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({c: row.get(c, "") for c in columns})
    data = buf.getvalue().encode("utf-8")
    return (b"\xef\xbb\xbf" + data) if bom else data


def write_master_csv(rows: list[Row]) -> bytes:
    return render_csv(MASTER_COLUMNS, rows)


def transfer_rows(rows: list[Row]) -> list[Row]:
    return [
        {
            "Title": r["title"],
            "Artist": r["artists"],
            "Album": r["album"],
            "Stage": r["stage"],
            "Apple Music URL": r["apple_music_url"],
        }
        for r in rows
    ]


def format_duration(seconds: int | None) -> str:
    if seconds is None:
        return ""
    return f"{seconds // 60}:{seconds % 60:02d}"


def format_long_duration(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m:02d}m {s:02d}s"
