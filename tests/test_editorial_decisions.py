"""Recording decisions in the handoff that must not drift silently."""

from __future__ import annotations


def _c(atlas):  # type: ignore[no-untyped-def]
    return atlas.collection("bach-cantabile-harmony")


def test_stage_counts(atlas) -> None:  # type: ignore[no-untyped-def]
    counts = {st.name: len(st.selections) for st in _c(atlas).stages}
    assert counts == {
        "Ground": 20,
        "Breath": 15,
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
    assert ground[2].work == "bwv-924"  # ED-001: BWV 939 question is open, order unchanged
    assert ground[14].work == "bwv-939"


def test_breath_snapshot_is_not_silently_replaced(atlas) -> None:  # type: ignore[no-untyped-def]
    breath = _c(atlas).stage("breath").selections
    assert len(breath) == 15
    assert any(s.recording == "fleisher-two-hands" for s in breath)


def test_line_uses_hewitt_1994_inventions(atlas) -> None:  # type: ignore[no-untyped-def]
    line = _c(atlas).stage("line").selections
    inv = [s for s in line if s.recording == "hewitt-inventions-sinfonias-1994"]
    assert len(inv) == 30
    assert all(s.song_id is None and s.verification == "needs_verification" for s in inv)
    rec = atlas.recordings["hewitt-inventions-sinfonias-1994"]
    assert (rec.label, rec.release_year) == ("Hyperion", 1994)
    assert not any("Schiff" in s.credits for s in line)


def test_span_olafsson_aria_variata_with_da_capo(atlas) -> None:  # type: ignore[no-untyped-def]
    span = [s for s in _c(atlas).stage("span").selections if s.work == "bwv-989"]
    assert len(span) == 12
    assert {s.recording for s in span} == {"olafsson-dg-2018"}
    assert span[0].movement == "Aria" and span[-1].movement == "Aria da capo"
    assert all(s.duration_status == "approximate" and s.song_id is None for s in span)


def test_order_is_hewitt_wtc_both_books(atlas) -> None:  # type: ignore[no-untyped-def]
    order = _c(atlas).stage("order").selections
    assert len(order) == 96
    assert {s.recording for s in order} == {"hewitt-wtc"}
    assert order[0].work == "bwv-846" and order[-1].work == "bwv-893"
    rec = atlas.recordings["hewitt-wtc"]
    assert "later" in (rec.version or "") and rec.verification == "needs_verification"


def test_no_fabricated_identifiers(atlas) -> None:  # type: ignore[no-untyped-def]
    for s in _c(atlas).selections():
        if s.song_id:
            assert s.url and s.song_id in s.url
        else:
            assert s.verification == "needs_verification"
