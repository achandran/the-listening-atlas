from __future__ import annotations

from datetime import date
from pathlib import Path

from atlas import audit, validate, yamlio
from atlas.model import load_atlas
from atlas.proposal import apply_proposal, check_proposal

from .conftest import COLLECTION

PROPOSAL = Path("data/collections") / COLLECTION / "proposals" / "breath-19.yaml"


def test_breath_proposal_is_pending(root: Path, atlas) -> None:  # type: ignore[no-untyped-def]
    c = atlas.collection(COLLECTION)
    res = check_proposal(atlas, c, yamlio.load(root / PROPOSAL))
    assert res.errors == []
    assert (res.current_count, res.resulting_count, res.kept, res.new, res.retire) == (15, 19, 14, 5, 1)
    assert (res.playlist_before, res.playlist_after) == (669, 673)
    assert not res.ready and len(res.pending) == 5
    assert len(res.notes) == 1 and "close-listening study" in res.notes[0]


def test_apply_refuses_until_verified(root: Path, sandbox: Path) -> None:
    atlas = load_atlas(sandbox / "data")
    res, files = apply_proposal(sandbox, atlas, atlas.collection(COLLECTION), sandbox / PROPOSAL, write=True)
    assert not res.ready and files == {}
    assert len(atlas.collection(COLLECTION).stage("breath").selections) == 15


def _complete_proposal(sandbox: Path) -> None:
    """Fill the five new items with clearly fake test values (tests only — never real data)."""
    recs = yamlio.load(sandbox / "data/recordings.yaml")
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
    yamlio.dump(recs, sandbox / "data/recordings.yaml")
    doc = yamlio.load(sandbox / PROPOSAL)
    for i, item in enumerate(x for x in doc["sequence"] if "new" in x):
        n = item["new"]
        n.update(
            recording="test-recording",
            title=f"Test title {i}",
            credits="Test credits",
            verification="verified",
            apple_music={"song_id": f"90000000{i}", "url": f"https://music.apple.com/us/song/t/90000000{i}"},
        )
    yamlio.dump(doc, sandbox / PROPOSAL)


def test_apply_complete_proposal(sandbox: Path) -> None:
    _complete_proposal(sandbox)
    atlas = load_atlas(sandbox / "data")
    c = atlas.collection(COLLECTION)
    res, files = apply_proposal(sandbox, atlas, c, sandbox / PROPOSAL, today=date(2026, 10, 11), write=False)
    assert res.ready and files
    assert len(atlas.collection(COLLECTION).stage("breath").selections) == 15  # dry run wrote nothing

    apply_proposal(sandbox, atlas, c, sandbox / PROPOSAL, today=date(2026, 10, 11), write=True)
    after = load_atlas(sandbox / "data")
    c2 = after.collection(COLLECTION)
    breath = c2.stage("breath").selections
    assert len(breath) == 19
    assert "fleisher-two-hands" not in {s.recording for s in breath}
    assert [r["selection"]["recording"] for r in c2.retired] == ["fleisher-two-hands"]
    assert "piano transcription" in c2.retired[0]["deep_focus"]["listen"]  # curated study kept, not lost
    assert {"bwv-147", "bwv-199", "bwv-21", "bwv-127"} <= set(after.works)
    assert len(c2.selections()) == 673
    assert validate.run(sandbox).errors == []
    report = audit.migration_report(sandbox, after, c2)
    assert "| Snapshot rows accounted for (active + retired) | 669 / 669 |" in report
    assert "| New selections (not in snapshot) | 5 |" in report
    assert yamlio.load(sandbox / PROPOSAL)["status"] == "applied"


def test_proposal_cannot_duplicate_a_recording(sandbox: Path) -> None:
    _complete_proposal(sandbox)
    doc = yamlio.load(sandbox / PROPOSAL)
    item = next(x for x in doc["sequence"] if "new" in x)
    item["new"]["apple_music"] = {
        "song_id": "1577781357",  # Trifonov Anh. 114, already in Ground
        "url": "https://music.apple.com/us/song/x/1577781357",
    }
    atlas = load_atlas(sandbox / "data")
    res = check_proposal(atlas, atlas.collection(COLLECTION), doc)
    assert any("each recording may appear only once" in e for e in res.errors)
    assert not res.ready
