from __future__ import annotations

import pytest

from atlas.sync import apple_music as am


def test_in_sync() -> None:
    p = am.plan(["1", "2", "3"], ["1", "2", "3"])
    assert p.in_sync and p.feasible_in_place and not (p.to_add or p.to_remove or p.moved)


def test_append_only() -> None:
    p = am.plan(["1", "2", "3", "4"], ["1", "2"])
    assert p.to_add == ["3", "4"] and p.append_only and p.feasible_in_place


def test_reorder_detected_and_not_feasible_in_place() -> None:
    p = am.plan(["1", "2", "3", "4"], ["1", "3", "2", "4"])
    assert p.to_add == [] and p.to_remove == []
    assert len(p.moved) == 1
    assert not p.feasible_in_place
    assert "cannot be applied in place" in p.summary()


def test_removals_and_duplicates() -> None:
    p = am.plan(["1", "2"], ["1", "9", "2", "2"])
    assert p.to_remove == ["9"] and p.duplicates_in_current == ["2"]
    assert not p.feasible_in_place


def test_unresolved_reported(atlas) -> None:  # type: ignore[no-untyped-def]
    desired, unresolved = am.desired_song_ids(atlas.collection("bach-cantabile-harmony"))
    assert len(desired) == 628 and len(unresolved) == 42
    p = am.plan(desired, desired, unresolved)
    assert not p.in_sync


def test_disabled_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(am.ENV_ENABLE, raising=False)
    monkeypatch.setenv(am.ENV_DEVELOPER_TOKEN, "x")
    with pytest.raises(am.SyncDisabled):
        am.AppleMusicClient.from_env(need_user=False)


def test_cli_apply_requires_typed_confirmation(monkeypatch: pytest.MonkeyPatch, capsys) -> None:  # type: ignore[no-untyped-def]
    from atlas.cli import main

    monkeypatch.setenv(am.ENV_ENABLE, "1")
    called = []
    monkeypatch.setattr(am.AppleMusicClient, "create_playlist", lambda *a, **k: called.append(a) or "p.x")
    assert main(["sync", "apply", "--create-new", "Bach test", "--skip-unresolved"]) == 1
    assert main(["sync", "apply", "--create-new", "Bach test", "--skip-unresolved", "--confirm", "yes"]) == 1
    assert called == []
    assert "CREATE Bach test" in capsys.readouterr().out
