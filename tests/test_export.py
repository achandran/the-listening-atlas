from __future__ import annotations

from pathlib import Path

from atlas.export import build_exports, write_exports
from atlas.model import load_atlas


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


def test_student_guide_is_current(root: Path) -> None:
    guide = _files(root)["bach-cantabile-harmony/student-guide.md"].decode()
    assert "**Playlist tracks** — 1–21 · 21 tracks" in guide
    assert "**Playlist tracks** — 22–40 · 19 tracks" in guide
    assert "Mary Howe transcription (Hewitt)" in guide and "BWV511" not in guide
    assert "The playlist has 674 selections" in guide
