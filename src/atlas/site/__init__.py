"""Static website generator. Pages are fully rendered at build time; JavaScript only adds search,
filters and the browser-local listening journal."""

from __future__ import annotations

import json
import re
import shutil
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, PackageLoader, select_autoescape

from ..catalogue import parse_apple_url
from ..export import match_status
from ..model import Atlas, Collection, Selection, Stage

STATIC = Path(__file__).parent / "static"


def _fold(parts: tuple[str | None, ...]) -> str:
    text = " ".join(p for p in parts if p)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def search_text(*parts: str | None, plain: tuple[str | None, ...] = ()) -> str:
    """Normalised search text. Catalogue numbers in ``parts`` are also indexed without spaces ("bwv846"), which
    is what a query for either "BWV 846" or "bwv846" matches. ``plain`` fields (albums, credits) are not, so an
    album called "… BWV 846-893" does not match every prelude and fugue."""
    text = _fold(parts)
    collapsed = re.sub(r"\b(bwv|anh) (\d)", r"\1\2", text)
    return " ".join(x for x in (text, collapsed, _fold(plain)) if x)


def selection_search_text(atlas: Atlas, s: Selection) -> str:
    w = atlas.works[s.work]
    return search_text(
        s.title,
        s.movement,
        s.arrangement,
        w.title,
        w.catalogue,
        plain=(s.credits, atlas.recordings[s.recording].album_title, s.album_as_listed),
    )


def fmt_duration(seconds: int | None) -> str:
    if seconds is None:
        return ""
    return f"{seconds // 60}:{seconds % 60:02d}"


def fmt_total(seconds: int) -> str:
    if seconds < 3600:
        return fmt_duration(seconds)
    h, rem = divmod(seconds, 3600)
    return f"{h}h {rem // 60:02d}m"


@dataclass
class Link:
    url: str
    label: str
    badge: str | None


def apple_link(s: Selection) -> Link | None:
    if not s.url:
        return None
    kind = parse_apple_url(s.url).kind
    if s.song_id:
        badge = (
            "Song ID supplied by editor; pending confirmation" if s.verification == "user_supplied" else None
        )
        return Link(s.url, "Listen on Apple Music", badge)
    if kind == "album":
        return Link(s.url, "Open the album in Apple Music", "Track not yet matched — find it on the album")
    if kind == "search":
        return Link(s.url, "Search Apple Music", "Track not yet matched — search link")
    return Link(s.url, "Open in Apple Music", "Link not verified")


@dataclass
class Group:
    work_id: str
    selections: list[Selection]

    @property
    def seconds(self) -> int:
        return sum(s.duration or 0 for s in self.selections)


def group_by_work(selections: list[Selection]) -> list[Group]:
    groups: list[Group] = []
    for s in selections:
        if groups and groups[-1].work_id == s.work:
            groups[-1].selections.append(s)
        else:
            groups.append(Group(s.work, [s]))
    return groups


def fallback_prompt(c: Collection, st: Stage, s: Selection) -> str:
    title = s.title.lower()
    for rule in c.meta.get("fallback_prompts", []) or []:
        if re.search(rule["match"], title, re.I):
            return str(rule["prompt"])
    return st.question


def stage_slug(st: Stage) -> str:
    return f"{st.number:02d}-{st.id}"


class SiteBuilder:
    def __init__(self, atlas: Atlas, out: Path, base_url: str = "") -> None:
        self.atlas = atlas
        self.out = out
        self.base_url = base_url.rstrip("/")
        self.env = Environment(
            loader=PackageLoader("atlas.site", "templates"),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )
        self.env.filters["duration"] = fmt_duration
        self.env.filters["total"] = fmt_total
        self.env.globals.update(apple_link=apple_link, stage_slug=stage_slug, match_status=match_status)

    def _write(self, rel: str, template: str, depth: int, prefix: str | None = None, **ctx: Any) -> None:
        html = self.env.get_template(template).render(
            rel="../" * depth if prefix is None else prefix,
            atlas=self.atlas,
            path=rel,
            base_url=self.base_url,
            **ctx,
        )
        target = self.out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8", newline="\n")

    def build(self) -> list[Path]:
        if self.out.exists():
            shutil.rmtree(self.out)
        self.out.mkdir(parents=True)
        shutil.copytree(STATIC, self.out / "assets")
        (self.out / ".nojekyll").write_text("", encoding="utf-8")
        self._write("index.html", "home.html", 0)
        for c in self.atlas.collections:
            self.build_collection(c)
        # GitHub Pages serves 404.html at any path, so its links must be absolute (from --base-url).
        self._write("404.html", "404.html", 0, prefix=f"{self.base_url}/")
        return sorted(p for p in self.out.rglob("*") if p.is_file())

    def build_collection(self, c: Collection) -> None:
        positions = c.positions()
        totals = {st.id: sum(s.duration or 0 for s in st.selections) for st in c.stages}
        ctx: dict[str, Any] = {
            "c": c,
            "positions": positions,
            "totals": totals,
            "works": self.atlas.works,
            "recordings": self.atlas.recordings,
        }
        self._write(f"{c.id}/index.html", "collection.html", 1, **ctx)
        for i, st in enumerate(c.stages):
            prev_st = c.stages[i - 1] if i > 0 else None
            next_st = c.stages[i + 1] if i + 1 < len(c.stages) else None
            self._write(
                f"{c.id}/{stage_slug(st)}/index.html",
                "stage.html",
                2,
                st=st,
                groups=group_by_work(st.selections),
                prev_st=prev_st,
                next_st=next_st,
                prompt_for=lambda s, st=st: fallback_prompt(c, st, s),
                search_text=lambda s: selection_search_text(self.atlas, s),
                **ctx,
            )
        self._write(f"{c.id}/search/index.html", "search.html", 2, **ctx)
        self._write(f"{c.id}/journal/index.html", "journal.html", 2, **ctx)
        self._write(f"{c.id}/status/index.html", "status.html", 2, **ctx)
        self._write_json(c, positions)

    def _write_json(self, c: Collection, positions: dict[str, int]) -> None:
        index = []
        for st in c.stages:
            for s in st.selections:
                w = self.atlas.works[s.work]
                r = self.atlas.recordings[s.recording]
                index.append(
                    {
                        "id": s.id,
                        "p": positions[s.id],
                        "stage": stage_slug(st),
                        "stageName": st.name,
                        "title": s.title,
                        "artist": s.credits,
                        "album": s.album_as_listed or r.album_title,
                        "work": f"{w.catalogue} · {w.title}",
                        "d": fmt_duration(s.duration),
                        "q": selection_search_text(self.atlas, s),
                    }
                )
        legacy_key = (c.meta.get("legacy") or {}).get("journal_keyed_by")
        legacy_map = {
            str(s.source_position): s.id
            for s in c.selections()
            if s.source_position and (s.raw.get("source") or {}).get("snapshot") == legacy_key
        }
        for retired in c.retired:
            sel = retired.get("selection") or {}
            src = sel.get("source") or {}
            if src.get("snapshot") == legacy_key:
                legacy_map[str(src.get("position"))] = str(sel.get("id"))
        data = {
            "collection": c.id,
            "title": c.title,
            "total": len(index),
            "selections": index,
            "legacy": {
                "storageKey": (c.meta.get("legacy") or {}).get("journal_storage_key"),
                "positions": legacy_map,
            },
        }
        (self.out / c.id / "atlas-data.json").write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8"
        )


def build_site(atlas: Atlas, out: Path, base_url: str = "") -> list[Path]:
    return SiteBuilder(atlas, out, base_url).build()
