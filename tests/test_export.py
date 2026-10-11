from __future__ import annotations

import csv
import io
import shutil
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


def test_legacy_exports_keep_handoff_format(root: Path) -> None:
    """Byte-identity with the handoff is proven for the migration (test_migration). After editorial changes the
    legacy export keeps the handoff's exact format; content changes are listed by `atlas audit`."""
    from atlas.snapshot import MASTER_COLUMNS

    files = _files(root)
    data = files["bach-cantabile-harmony/legacy-master.csv"]
    assert data.startswith(b"\xef\xbb\xbf" + ",".join(MASTER_COLUMNS).encode() + b"\r\n")
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
    assert [r["position"] for r in rows] == [str(i) for i in range(1, len(rows) + 1)]
    assert len(rows) == len(load_atlas(root / "data").collections[0].selections())


def test_importer_csv_schema_and_match_status(root: Path) -> None:
    content = _files(root)["bach-cantabile-harmony/playlist-full.csv"].decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(content)))
    assert tuple(rows[0].keys()) == IMPORTER_COLUMNS
    assert len(rows) == 674
    assert [r["Position"] for r in rows] == [str(i) for i in range(1, 675)]
    status: dict[str, int] = {}
    for r in rows:
        status[r["Match Status"]] = status.get(r["Match Status"], 0) + 1
    assert status == {"exact_song_id": 674}  # every selection matched (2026-10-11 review)
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
    assert len(ids) == 674 and ids[:3] == ["1577781357", "1577781609", "1577781863"]
    assert all(i.isdigit() for i in ids)


def test_student_guide_reproduces_archived_text(root: Path, tmp_path: Path) -> None:
    """From a fresh migration of the snapshot, every line of the archived guide is regenerated verbatim, except
    the known differences: itineraries given approved factual updates (Stages 1, 4, 7), per-stage durations,
    the closing timing note, and track ranges from Stage 7 (the archived guide predates the Aria da capo; ED-011).
    """
    from atlas import migrate
    from atlas.export import student_guide

    for name in ("schemas", "archive"):
        shutil.copytree(root / name, tmp_path / name)
    migrate.write(tmp_path, migrate.migrate(root))
    atlas = load_atlas(tmp_path / "data")
    c = atlas.collections[0]
    generated = student_guide(atlas, c).splitlines()
    archived = (root / migrate.STUDENT_GUIDE).read_text(encoding="utf-8").splitlines()
    updated_itineraries = {
        f"**Recording itinerary** — {st.itinerary_source}" for st in c.stages if st.itinerary_source
    }
    timing_note = archived[archived.index("# Recording and timing note") + 1 : -1]

    checked = 0
    for ln in archived:
        if not ln or ln in updated_itineraries or ln in timing_note or ln.startswith("**Playlist tracks**"):
            continue
        assert ln in generated, ln
        checked += 1
    assert checked > 70

    def ranges(lines: list[str]) -> list[str]:
        return [" · ".join(ln.split(" · ")[:2]) for ln in lines if ln.startswith("**Playlist tracks**")]

    assert ranges(generated)[:6] == ranges(archived)[:6]
    assert ranges(generated)[6:] != ranges(archived)[6:]  # the archived guide's known off-by-one (ED-011)


def test_student_guide_is_current(root: Path) -> None:
    guide = _files(root)["bach-cantabile-harmony/student-guide.md"].decode()
    assert "**Playlist tracks** — 1–21 · 21 tracks" in guide
    assert "**Playlist tracks** — 22–40 · 19 tracks" in guide
    assert "Mary Howe transcription (Hewitt)" in guide and "BWV511" not in guide
    assert "The playlist has 674 selections" in guide
