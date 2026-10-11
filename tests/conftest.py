from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from atlas import yamlio
from atlas.model import Atlas, load_atlas

ROOT = Path(__file__).resolve().parents[1]
COLLECTION = "bach-cantabile-harmony"


@pytest.fixture(scope="session")
def root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def atlas() -> Atlas:
    return load_atlas(ROOT / "data")


@pytest.fixture()
def sandbox(tmp_path: Path) -> Path:
    """A writable copy of the repository's data, schemas and archive."""
    for name in ("data", "schemas", "archive"):
        shutil.copytree(ROOT / name, tmp_path / name)
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    return tmp_path


def stage_file(root: Path, name: str) -> Path:
    return root / "data" / "collections" / COLLECTION / "selections" / name


def edit_yaml(path: Path, fn) -> None:  # type: ignore[no-untyped-def]
    data = yamlio.load(path)
    fn(data)
    yamlio.dump(data, path)
