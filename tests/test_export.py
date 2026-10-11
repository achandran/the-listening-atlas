from __future__ import annotations

import csv
import io
from pathlib import Path

from atlas.export import IMPORTER_COLUMNS, build_exports, write_exports
from atlas.model import load_atlas

SNAP = Path(__file__).parent / "snapshots"


def _files(root: Path) -> dict[str, bytes]:
    atlas = load_atlas(root / "data")
    return {str(f.path): f.content for f in build_exports(atlas, atlas.collections[0])}


def test_exports_are_deterministic(root: Path, tmp_path: Path) -> None:
    a, b = _files(root), _files(root)
    assert a == b
    atlas = load_atlas(root / "data")
    write_exports(build_exports(atlas, atlas.collections[0]), tmp_path / "1")
    write_exports(build_exports(atlas, atlas.collections[0]), tmp_path / "2")
    for p in (tmp_path / "1").rglob("*"):
        if p.is_file():
            assert p.read_bytes() == (tmp_path / "2" / p.relative_to(tmp_path / "1")).read_bytes()


def test_legacy_exports_reproduce_handoff(root: Path) -> None:
    files = _files(root)
    src = root / "archive/2026-10-11-handoff/source"
    p = "bach-cantabile-harmony/"
    assert files[p + "legacy-master.csv"] == (src / "Bach_Cantabile_Master_Ground_Revised.csv").read_bytes()
    assert (
        files[p + "legacy-transfer.csv"] == (src / "Bach_Cantabile_Transfer_Ground_Revised.csv").read_bytes()
    )


def test_importer_csv_schema_and_match_status(root: Path) -> None:
    content = _files(root)["bach-cantabile-harmony/playlist-full.csv"].decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(content)))
    assert tuple(rows[0].keys()) == IMPORTER_COLUMNS
    assert len(rows) == 669
    assert [r["Position"] for r in rows] == [str(i) for i in range(1, 670)]
    status: dict[str, int] = {}
    for r in rows:
        status[r["Match Status"]] = status.get(r["Match Status"], 0) + 1
    assert status == {"exact_song_id": 627, "unmatched_album_link": 30, "unmatched_search_link": 12}
    assert all(r["ISRC"] == "" for r in rows)  # never fabricated
    unmatched = [r for r in rows if r["Match Status"] != "exact_song_id"]
    assert all(r["Apple Music ID"] == "" for r in unmatched)


def test_stage_exports_partition_the_playlist(root: Path) -> None:
    files = _files(root)
    stage_rows = []
    for name, data in sorted(files.items()):
        if "/stages/" in name:
            stage_rows += list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
    full = list(
        csv.DictReader(io.StringIO(files["bach-cantabile-harmony/playlist-full.csv"].decode("utf-8-sig")))
    )
    assert stage_rows == full


def test_ground_export_snapshot(root: Path) -> None:
    """Snapshot test. If this fails after an intended edit, regenerate with:
    uv run atlas export --format csv && cp exports/bach-cantabile-harmony/stages/01-ground.csv tests/snapshots/
    """
    assert (
        _files(root)["bach-cantabile-harmony/stages/01-ground.csv"] == (SNAP / "01-ground.csv").read_bytes()
    )


def test_song_id_list_contains_only_exact_ids(root: Path) -> None:
    ids = _files(root)["bach-cantabile-harmony/apple-song-ids.txt"].decode().split()
    assert len(ids) == 627 and ids[:2] == ["1577781357", "1577780575"]
    assert all(i.isdigit() for i in ids)
