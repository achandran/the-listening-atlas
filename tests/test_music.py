from __future__ import annotations

import pytest

from atlas import music
from atlas.model import Selection


def _tracks(sels: list[Selection]) -> list[music.Track]:
    """The playlist exactly as the data describes it (artist spelled as Apple does, durations rounded up)."""
    return [
        music.Track(i, f"P{i:04d}", s.title, s.credits.replace(";", " &"), "", (s.duration or 0) + 0.6)
        for i, s in enumerate(sels, start=1)
    ]


def _extra(index: int, artist: str = "Masaaki Suzuki", duration: float = 33.0) -> music.Track:
    return music.Track(index, f"X{index:04d}", "14 Verschiedene Canones, BWV 1087", artist, "Opfer", duration)


def _renumber(tracks: list[music.Track]) -> list[music.Track]:
    return [
        music.Track(i, t.persistent_id, t.name, t.artist, t.album, t.duration)
        for i, t in enumerate(tracks, 1)
    ]


@pytest.fixture
def sels(atlas) -> list[Selection]:  # type: ignore[no-untyped-def]
    return atlas.collection("bach-cantabile-harmony").selections()


def test_in_sync(sels: list[Selection]) -> None:
    p = music.plan("Bach", sels, _tracks(sels))
    assert p.in_sync and "In sync" in p.summary()


def test_extra_tracks_are_removed(sels: list[Selection]) -> None:
    tracks = _tracks(sels)
    tracks = _renumber(tracks[:653] + [_extra(0) for _ in range(19)] + tracks[653:])
    p = music.plan("Bach", sels, tracks)
    assert [t.index for t in p.remove] == list(range(654, 673))
    assert p.add == []


def test_missing_and_moved_are_listed_for_hand_edits(sels: list[Selection]) -> None:
    tracks = _tracks(sels)
    moved = tracks.pop(10)
    del tracks[100]
    tracks = _renumber([*tracks[:50], moved, *tracks[50:]])
    p = music.plan("Bach", sels, tracks)
    assert [pos for pos, _ in p.add] == [11, 102]
    assert [t.persistent_id for t in p.remove] == [moved.persistent_id]
    assert "add by hand" in p.summary()


def test_other_performer_does_not_match(sels: list[Selection]) -> None:
    s = sels[199]  # Hewitt, 2-Part Invention No. 1
    schiff = music.Track(1, "S", s.title, "András Schiff", "", float(s.duration or 0))
    assert music.matches(s, music.Track(1, "H", s.title, "Angela Hewitt", "", float(s.duration or 0)))
    assert not music.matches(s, schiff)


def test_duration_tolerance(sels: list[Selection]) -> None:
    s = sels[0]
    near = music.Track(1, "a", s.title, s.credits, "", float(s.duration or 0) + music.DURATION_TOLERANCE)
    far = music.Track(1, "b", s.title, s.credits, "", float(s.duration or 0) + music.DURATION_TOLERANCE + 1)
    assert music.matches(s, near) and not music.matches(s, far)


def test_parse_tracks() -> None:
    fs, rs = music.FIELD_SEP, music.RECORD_SEP
    out = (
        fs.join(["A1", "Aria", "Hewitt", "Goldberg", "105,85"])
        + rs
        + fs.join(["B2", "X", "Y", "Z", "missing value"])
    )
    tracks = music.parse_tracks(out + "\n")
    assert [(t.index, t.persistent_id, t.duration) for t in tracks] == [(1, "A1", 105.85), (2, "B2", None)]
    assert music.parse_tracks("") == []


def test_apply_is_a_dry_run_without_write(monkeypatch: pytest.MonkeyPatch, capsys, sels) -> None:  # type: ignore[no-untyped-def]
    from atlas.cli import main

    tracks = _renumber([*_tracks(sels), _extra(0)])
    removed: list[list[music.Track]] = []
    monkeypatch.setattr(music, "read_playlist", lambda name: tracks)
    monkeypatch.setattr(music, "remove_tracks", lambda name, ts: removed.append(ts) or (len(ts), 674))
    assert main(["music", "check"]) == 1
    assert main(["music", "apply"]) == 0
    assert removed == []
    assert "Dry run" in capsys.readouterr().out
    assert main(["music", "apply", "--write"]) == 0
    assert [t.index for t in removed[0]] == [675]
