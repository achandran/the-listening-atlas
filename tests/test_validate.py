"""Each validator rule is exercised by breaking a copy of the real data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from atlas import validate

from .conftest import COLLECTION, edit_yaml, stage_file

GROUND = "01-ground.yaml"


def codes(root: Path) -> dict[str, str]:
    """code -> level for every finding."""
    return {f.code: f.level for f in validate.run(root).findings}


def test_committed_data_is_clean(root: Path) -> None:
    """After the 2026-10-11 editorial review: no errors, no warnings, every song matched, no open issues."""
    report = validate.run(root)
    assert report.findings == [], "\n".join(f.format() for f in report.findings)
    assert report.ok(strict=True)


def test_strict_mode_fails_on_unresolved_song_ids(sandbox: Path) -> None:
    def drop(s: list[dict[str, Any]]) -> None:
        s[3]["apple_music"]["song_id"] = None
        s[3]["apple_music"]["url"] = s[3]["apple_music"]["album_url"].split("?")[0]
        s[3]["link_kind"] = "album"
        s[3]["verification"] = "needs_verification"

    _ground(sandbox, drop)
    report = validate.run(sandbox)
    assert report.ok() and not report.ok(strict=True)


def _ground(sandbox: Path, fn: Any) -> None:
    edit_yaml(stage_file(sandbox, GROUND), lambda d: fn(d["selections"]))


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda s: s[3].update(id=s[2]["id"]), "DUPLICATE-SELECTION-ID"),
        (lambda s: s[3].update(work="bwv-99999"), "MISSING-WORK"),
        (lambda s: s[3].update(recording="nobody-nothing"), "MISSING-RECORDING"),
        (lambda s: s[3]["apple_music"].update(song_id="1"), "SONG-ID-MISMATCH"),
        (lambda s: s[3]["apple_music"].update(url="http://example.com/x"), "BAD-URL"),
        (lambda s: s[3]["apple_music"].update(song_id=None), "SONG-ID-NOT-RECORDED"),
        (lambda s: s.insert(0, s.pop(2)), "PINNED-OPENING"),
        (lambda s: s[3].update(colour="blue"), "SCHEMA"),
        (lambda s: s[3].update(verification="probably"), "SCHEMA"),
    ],
)
def test_selection_errors(sandbox: Path, mutate: Any, code: str) -> None:
    _ground(sandbox, mutate)
    assert codes(sandbox).get(code) == "error"


def test_unresolved_song_id_is_warning_not_error(sandbox: Path) -> None:
    def drop(s: list[dict[str, Any]]) -> None:
        s[3]["apple_music"]["song_id"] = None
        s[3]["apple_music"]["url"] = s[3]["apple_music"]["album_url"].split("?")[0]
        s[3]["link_kind"] = "album"
        s[3]["verification"] = "needs_verification"

    _ground(sandbox, drop)
    report = validate.run(sandbox)
    assert report.errors == []
    assert "UNRESOLVED-SONG-IDS" in {f.code for f in report.warnings}


def test_verified_without_song_id_is_inconsistent(sandbox: Path) -> None:
    def bad(s: list[dict[str, Any]]) -> None:
        s[3]["apple_music"].update(song_id=None, url="https://music.apple.com/us/album/x/1852229971")
        s[3]["link_kind"] = "album"

    _ground(sandbox, bad)
    assert codes(sandbox).get("VERIFICATION-INCONSISTENT") == "error"


def test_duplicate_recording_has_no_override(sandbox: Path) -> None:
    """Invariant: each recording appears at most once per playlist. A `reuse` key is not accepted."""
    import copy

    def dup(s: list[dict[str, Any]]) -> None:
        clone = copy.deepcopy(s[5])
        clone["id"] = "s-zzzzzz1"
        clone["source"] = {"snapshot": "manual", "position": 9999}
        s.append(clone)

    _ground(sandbox, dup)
    c = codes(sandbox)
    assert c.get("DUPLICATE-SONG") == "error"
    assert "DUPLICATE-MOVEMENT" not in c  # one problem, reported once

    _ground(sandbox, lambda s: s[-1].update(reuse={"of": s[5]["id"], "reason": "Deliberate return."}))
    c = codes(sandbox)
    assert c.get("DUPLICATE-SONG") == "error"
    assert c.get("SCHEMA") == "error"


def test_duplicate_across_stages(sandbox: Path) -> None:
    import copy

    from atlas import yamlio

    first = copy.deepcopy(yamlio.load(stage_file(sandbox, GROUND))["selections"][0])
    first["id"] = "s-zzzzzz4"
    first.pop("source")
    edit_yaml(stage_file(sandbox, "11-essence.yaml"), lambda d: d["selections"].append(first))
    assert codes(sandbox).get("DUPLICATE-SONG") == "error"


def test_same_movement_same_recording_different_song(sandbox: Path) -> None:
    import copy

    def dup(s: list[dict[str, Any]]) -> None:
        clone = copy.deepcopy(s[5])
        clone["id"] = "s-zzzzzz3"
        clone["apple_music"] = {
            "song_id": "1852239999",
            "url": "https://music.apple.com/us/song/x/1852239999",
        }
        clone.pop("source")
        s.append(clone)

    _ground(sandbox, dup)
    assert codes(sandbox).get("DUPLICATE-MOVEMENT") == "error"


def test_same_movement_other_recording_is_allowed(sandbox: Path) -> None:
    """A title match alone never decides: same work/movement in a different recording is only flagged."""

    def other(s: list[dict[str, Any]]) -> None:
        motion = stage_file(sandbox, "03-motion.yaml")
        from atlas import yamlio

        src = yamlio.load(motion)["selections"][0]  # Perahia BWV 812 Allemande
        src = dict(
            src,
            id="s-zzzzzz2",
            recording="hewitt-plays-bach-and-more",
            source={"snapshot": "manual", "position": 9998},
        )
        src["apple_music"] = dict(
            src["apple_music"], song_id="1852229999", url="https://music.apple.com/us/song/x/1852229999"
        )
        s.append(src)

    _ground(sandbox, other)
    c = codes(sandbox)
    assert c.get("REPEATED-MOVEMENT") == "info"
    assert "DUPLICATE-MOVEMENT" not in c and "DUPLICATE-SONG" not in c


def test_stage_rules(sandbox: Path) -> None:
    stages = sandbox / "data" / "collections" / COLLECTION / "stages.yaml"
    edit_yaml(stages, lambda d: d["stages"][2].update(number=7))
    c = codes(sandbox)
    assert c.get("STAGE-NUMBER-DUPLICATE") == "error"
    assert c.get("STAGE-NUMBER-GAP") == "error"


def test_stage_file_order(sandbox: Path) -> None:
    coll = sandbox / "data" / "collections" / COLLECTION / "collection.yaml"
    edit_yaml(coll, lambda d: d["stage_files"].insert(0, d["stage_files"].pop(1)))
    assert codes(sandbox).get("STAGE-FILE-ORDER") == "error"


def test_breath_maximum(sandbox: Path) -> None:
    import copy

    def grow(s: list[dict[str, Any]]) -> None:
        for i in range(5):
            clone = copy.deepcopy(s[0])
            clone["id"] = f"s-zzzzzx{i}"
            clone["movement"] = f"padding {i}"
            clone["apple_music"] = {
                "song_id": f"99999{i}",
                "url": f"https://music.apple.com/us/song/x/99999{i}",
            }
            clone.pop("source", None)
            s.append(clone)

    edit_yaml(stage_file(sandbox, "02-breath.yaml"), lambda d: grow(d["selections"]))
    assert codes(sandbox).get("STAGE-TOO-LONG") == "error"


def test_dangling_notes_and_issue_refs(sandbox: Path) -> None:
    notes = sandbox / "data" / "collections" / COLLECTION / "notes" / "deep-focus.yaml"
    edit_yaml(
        notes, lambda d: d["deep_focus"].update({"s-nothere": {"listen": "x", "piano": "y", "question": "z"}})
    )
    assert codes(sandbox).get("DANGLING-NOTE") == "error"


def test_yaml_syntax_error_is_reported_not_raised(sandbox: Path) -> None:
    stage_file(sandbox, GROUND).write_text("stage: ground\nselections: [\n", encoding="utf-8")
    assert codes(sandbox).get("YAML-SYNTAX") == "error"
