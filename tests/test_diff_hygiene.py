"""Canonical YAML must round-trip unchanged, and moving one selection must be a small diff."""

from __future__ import annotations

import difflib
from pathlib import Path

from atlas import yamlio


def _body(text: str) -> str:
    return "".join(line + "\n" for line in text.splitlines() if not line.startswith("#"))


def test_yaml_files_round_trip_byte_identical(root: Path) -> None:
    for path in sorted((root / "data").rglob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        assert yamlio.dumps(yamlio.load(path)) == _body(text), path


def test_moving_one_selection_is_a_small_diff(root: Path) -> None:
    path = root / "data/collections/bach-cantabile-harmony/selections/01-ground.yaml"
    data = yamlio.load(path)
    before = yamlio.dumps(data).splitlines()
    sel = data["selections"].pop(14)  # BWV 939
    data["selections"].insert(2, sel)  # move to first Hewitt slot (the ED-001 question)
    after = yamlio.dumps(data).splitlines()
    diff = [
        ln
        for ln in difflib.unified_diff(before, after, lineterm="", n=0)
        if ln[:1] in "+-" and not ln.startswith(("+++", "---"))
    ]
    block = len(yamlio.dumps([sel]).splitlines())
    assert len(diff) == 2 * block  # the moved block, removed once and added once — nothing else
