"""The initial migration must be lossless and deterministic."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from atlas import migrate, yamlio
from atlas.export import build_exports
from atlas.model import load_atlas
from atlas.snapshot import read_master_csv

SNAPSHOT = migrate.MASTER_CSV


def test_handoff_archive_matches_manifest(root: Path) -> None:
    base = root / migrate.HANDOFF_DIR
    manifest = json.loads((base / "MANIFEST.json").read_text())
    assert manifest["source_snapshot_rows"] == 669
    for f in manifest["files"]:
        assert hashlib.sha256((base / f["path"]).read_bytes()).hexdigest() == f["sha256"], f["path"]


def test_migration_is_deterministic(root: Path) -> None:
    a = migrate.migrate(root)
    b = migrate.migrate(root)
    assert {k: yamlio.dumps(v) for k, v in a.files.items()} == {
        k: yamlio.dumps(v) for k, v in b.files.items()
    }


def test_migration_round_trips_snapshot_byte_for_byte(root: Path, tmp_path: Path) -> None:
    """All 669 rows, their order, raw titles, credits, URLs, status and notes survive migration."""
    migrate.write(tmp_path, migrate.migrate(root))
    atlas = load_atlas(tmp_path / "data")
    c = atlas.collection(migrate.COLLECTION_ID)
    assert len(c.selections()) == 669
    legacy = next(f for f in build_exports(atlas, c) if f.path.name == "legacy-master.csv")
    assert legacy.content == (root / SNAPSHOT).read_bytes()


def test_selection_ids_are_unique_and_stable(root: Path) -> None:
    ids = [migrate.selection_id(p) for p in range(1, 670)]
    assert len(set(ids)) == 669
    assert migrate.selection_id(1) == "s-fjvf7ay"  # changing the ID scheme would break every journal


def test_committed_data_accounts_for_every_snapshot_row(root: Path) -> None:
    atlas = load_atlas(root / "data")
    c = atlas.collection(migrate.COLLECTION_ID)
    active = {s.source_position for s in c.selections() if s.source_position}
    retired = {(r["selection"].get("source") or {}).get("position") for r in c.retired}
    rows = read_master_csv(root / SNAPSHOT)
    assert len(rows) == 669
    assert {int(r["position"]) for r in rows} == active | retired
    assert not active & retired


def test_first_two_ground_song_ids(atlas) -> None:  # type: ignore[no-untyped-def]
    ground = atlas.collection("bach-cantabile-harmony").stage("ground")
    assert [s.song_id for s in ground.selections[:2]] == ["1577781357", "1577780575"]
    assert ground.selections[0].work == "bwv-anh-114"
    assert ground.selections[1].work == "bwv-anh-120"
    assert all(s.recording == "trifonov-art-of-life" for s in ground.selections[:2])
    assert atlas.recordings["trifonov-art-of-life"].apple_album_id == "1577776877"
    assert "bwv-511" not in {s.work for s in ground.selections}
