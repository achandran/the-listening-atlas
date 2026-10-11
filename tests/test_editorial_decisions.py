"""Recording decisions in the handoff that must not drift silently."""

from __future__ import annotations


def _c(atlas):  # type: ignore[no-untyped-def]
    return atlas.collection("bach-cantabile-harmony")


def test_stage_counts(atlas) -> None:  # type: ignore[no-untyped-def]
    counts = {st.name: len(st.selections) for st in _c(atlas).stages}
    assert counts == {
        "Ground": 21,
        "Breath": 19,
        "Motion": 89,
        "Line": 107,
        "Rhetoric": 25,
        "Exchange": 59,
        "Span": 54,
        "Order": 96,
        "Transformation": 32,
        "Convergence": 135,
        "Essence": 37,
    }


def test_hewitt_preludes_not_reordered(atlas) -> None:  # type: ignore[no-untyped-def]
    ground = _c(atlas).stage("ground").selections
    assert ground[3].work == "bwv-924"  # ED-001: BWV 939 question is open, order unchanged
    assert ground[15].work == "bwv-939"
    hewitt = [s.work for s in ground if s.recording == "hewitt-plays-bach-and-more"]
    assert len(hewitt) == 18 and ground[3:] == [
        s for s in ground if s.recording == "hewitt-plays-bach-and-more"
    ]


def test_breath_is_the_approved_19(atlas) -> None:  # type: ignore[no-untyped-def]
    """Approved sequence (editorial/BREATH_19_APPROVED.md), applied 2026-10-11 with editor-confirmed tracks."""
    breath = atlas.collection("bach-cantabile-harmony").stage("breath").selections
    assert [s.work for s in breath] == [
        "bwv-177", "bwv-639", "bwv-227", "bwv-208", "bwv-208", "bwv-147", "bwv-170", "bwv-199", "bwv-32",
        "bwv-57", "bwv-105", "bwv-659", "bwv-21", "bwv-12", "bwv-12", "bwv-12", "bwv-56", "bwv-127", "bwv-82",
    ]  # fmt: skip
    assert [s.song_id for s in breath if s.source_position is None] == [
        "1721137597", "1724264838", "73238385", "1707368183", "1727109118",
    ]  # fmt: skip
    assert "fleisher-two-hands" not in {s.recording for s in breath}
    assert breath[4].recording == "hewitt-bach-arrangements-transcriptions"
    assert breath[-1].song_id == "73238160"  # ends with the opening BWV 82 aria only


def test_line_uses_hewitt_1994_inventions(atlas) -> None:  # type: ignore[no-untyped-def]
    """ED-004/005 (2026-10-11): all 30 matched on Apple album 1721143424; Invention No. 1 is BWV 772."""
    line = _c(atlas).stage("line").selections
    inv = [s for s in line if s.recording == "hewitt-inventions-sinfonias-1994"]
    assert len(inv) == 30
    assert all(s.song_id and s.verification == "verified" and s.duration for s in inv)
    assert inv[0].work == "bwv-772" and inv[0].title == "2-Part Invention No. 1 in C Major, BWV 772"
    assert inv[-1].title == "Sinfonia (3-Part Invention) No. 15 in B Minor, BWV 801"
    assert "bwv-772a" not in atlas.works
    rec = atlas.recordings["hewitt-inventions-sinfonias-1994"]
    assert (rec.label, rec.release_year, rec.apple_album_id) == ("Hyperion", 1994, "1721143424")
    assert not any("Schiff" in s.credits or "Schiff" in s.title for s in line)


def test_span_olafsson_aria_variata_with_da_capo(atlas) -> None:  # type: ignore[no-untyped-def]
    """ED-006 (2026-10-11): matched on DG 2018 album 1410551592, the same album as Ólafsson's BWV 659."""
    span = [s for s in _c(atlas).stage("span").selections if s.work == "bwv-989"]
    assert len(span) == 12
    assert {s.recording for s in span} == {"olafsson-johann-sebastian-bach"}
    assert span[0].movement == "Thema" and span[-1].movement == "Aria da capo"
    assert all(s.song_id and s.duration and s.duration_status is None for s in span)
    rec = atlas.recordings["olafsson-johann-sebastian-bach"]
    assert (rec.label, rec.release_year, rec.apple_album_id) == ("Deutsche Grammophon", 2018, "1410551592")
    breath_659 = [s for s in _c(atlas).stage("breath").selections if s.work == "bwv-659"]
    assert breath_659[0].recording == rec.id


def test_order_is_hewitt_wtc_both_books(atlas) -> None:  # type: ignore[no-untyped-def]
    order = _c(atlas).stage("order").selections
    assert len(order) == 96
    assert {s.recording for s in order} == {"hewitt-wtc"}
    assert order[0].work == "bwv-846" and order[-1].work == "bwv-893"
    rec = atlas.recordings["hewitt-wtc"]
    assert "later" in (rec.version or "") and rec.verification == "verified"
    assert (rec.label, rec.release_year, rec.apple_album_id) == ("Hyperion", 2009, "1721145434")


def test_no_fabricated_identifiers(atlas) -> None:  # type: ignore[no-untyped-def]
    for s in _c(atlas).selections():
        if s.song_id:
            assert s.url and s.song_id in s.url
        else:
            assert s.verification == "needs_verification"
