"""Proposal mechanics, exercised on a fresh migration of the 669-row snapshot (Breath pending, 15 tracks).

The live breath-19 proposal has been applied (see test_editorial_decisions), so these tests use the migrated
pre-reconciliation state as a fixture rather than the live data.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest

from atlas import audit, migrate, validate, yamlio
from atlas.model import load_atlas
from atlas.proposal import apply_proposal, check_proposal

from .conftest import COLLECTION

PROPOSAL = Path("data/collections") / COLLECTION / "proposals" / "breath-19.yaml"


@pytest.fixture()
def pristine(root: Path, tmp_path: Path) -> Path:
    """A repository copy whose data is a fresh migration of the archived snapshot."""
    for name in ("schemas", "archive"):
        shutil.copytree(root / name, tmp_path / name)
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    migrate.write(tmp_path, migrate.migrate(root))
    return tmp_path


def test_breath_proposal_is_pending(pristine: Path) -> None:
    atlas = load_atlas(pristine / "data")
    res = check_proposal(atlas, atlas.collection(COLLECTION), yamlio.load(pristine / PROPOSAL))
    assert res.errors == []
    assert (res.current_count, res.resulting_count, res.kept, res.new, res.retire) == (15, 19, 14, 5, 1)
    assert (res.playlist_before, res.playlist_after) == (669, 673)
    assert not res.ready and len(res.pending) == 5
    assert len(res.notes) == 1 and "close-listening study" in res.notes[0]


def test_apply_refuses_until_verified(pristine: Path) -> None:
    atlas = load_atlas(pristine / "data")
    res, files = apply_proposal(
        pristine, atlas, atlas.collection(COLLECTION), pristine / PROPOSAL, write=True
    )
    assert not res.ready and files == {}
    assert len(load_atlas(pristine / "data").collection(COLLECTION).stage("breath").selections) == 15


def _complete_proposal(root: Path) -> None:
    """Fill the five new items with clearly fake test values (tests only — never real data)."""
    recs = yamlio.load(root / "data/recordings.yaml")
    recs["recordings"].append(
        {
            "id": "test-recording",
            "principal_artist": "Test",
            "album_title": "Test",
            "apple_album_id": "1",
            "label": None,
            "release_year": None,
            "version": None,
            "verification": "needs_verification",
        }
    )
    yamlio.dump(recs, root / "data/recordings.yaml")
    doc = yamlio.load(root / PROPOSAL)
    for i, item in enumerate(x for x in doc["sequence"] if "new" in x):
        n = item["new"]
        n.update(
            recording="test-recording",
            title=f"Test title {i}",
            credits="Test credits",
            verification="verified",
            apple_music={"song_id": f"90000000{i}", "url": f"https://music.apple.com/us/song/t/90000000{i}"},
        )
    yamlio.dump(doc, root / PROPOSAL)


def test_apply_complete_proposal(pristine: Path) -> None:
    _complete_proposal(pristine)
    atlas = load_atlas(pristine / "data")
    c = atlas.collection(COLLECTION)
    res, files = apply_proposal(
        pristine, atlas, c, pristine / PROPOSAL, today=date(2026, 10, 11), write=False
    )
    assert res.ready and files
    assert (
        len(load_atlas(pristine / "data").collection(COLLECTION).stage("breath").selections) == 15
    )  # dry run

    apply_proposal(pristine, atlas, c, pristine / PROPOSAL, today=date(2026, 10, 11), write=True)
    after = load_atlas(pristine / "data")
    c2 = after.collection(COLLECTION)
    breath = c2.stage("breath").selections
    assert len(breath) == 19
    assert "fleisher-two-hands" not in {s.recording for s in breath}
    assert [r["selection"]["recording"] for r in c2.retired] == ["fleisher-two-hands"]
    assert "piano transcription" in c2.retired[0]["deep_focus"]["listen"]  # curated study kept, not lost
    assert {"bwv-147", "bwv-199", "bwv-21", "bwv-127"} <= set(after.works)
    assert len(c2.selections()) == 673
    assert validate.run(pristine).errors == []
    report = audit.migration_report(pristine, after, c2)
    assert "| Snapshot rows accounted for (active + retired) | 669 / 669 |" in report
    assert "| New selections (not in snapshot) | 5 |" in report
    assert yamlio.load(pristine / PROPOSAL)["status"] == "applied"


def test_proposal_cannot_duplicate_a_recording(pristine: Path) -> None:
    _complete_proposal(pristine)
    doc = yamlio.load(pristine / PROPOSAL)
    item = next(x for x in doc["sequence"] if "new" in x)
    item["new"]["apple_music"] = {
        "song_id": "1577781357",  # Trifonov Anh. 114, already in Ground
        "url": "https://music.apple.com/us/song/x/1577781357",
    }
    atlas = load_atlas(pristine / "data")
    res = check_proposal(atlas, atlas.collection(COLLECTION), doc)
    assert any("each recording may appear only once" in e for e in res.errors)
    assert not res.ready


def test_live_breath_proposal_is_applied(root: Path) -> None:
    assert yamlio.load(root / PROPOSAL)["status"] == "applied"
