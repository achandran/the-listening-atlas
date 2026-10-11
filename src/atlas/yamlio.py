"""Deterministic YAML reading and writing.

Canonical data is written with stable key order, no line folding and real Unicode, so that a one-line
editorial change produces a one-line Git diff.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class _Dumper(yaml.SafeDumper):
    pass


def _str_representer(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


def _none_representer(dumper: yaml.SafeDumper, _value: None) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:null", "null")


_Dumper.add_representer(str, _str_representer)
_Dumper.add_representer(type(None), _none_representer)


def _increase_indent(self: _Dumper, flow: bool = False, indentless: bool = False) -> None:
    # Indent sequences inside mappings ("selections:\n  - id: …"), which is easier to read and edit.
    yaml.SafeDumper.increase_indent(self, flow, False)


_Dumper.increase_indent = _increase_indent  # type: ignore[method-assign,assignment]


def dumps(data: Any) -> str:
    return yaml.dump(
        data,
        Dumper=_Dumper,
        allow_unicode=True,
        sort_keys=False,
        width=10_000,
        default_flow_style=False,
    )


def dump(data: Any, path: Path, header: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = dumps(data)
    if header:
        text = "".join(f"# {line}\n" if line else "#\n" for line in header.splitlines()) + text
    path.write_text(text, encoding="utf-8", newline="\n")


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)
