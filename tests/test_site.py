from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import pytest

from atlas.model import load_atlas
from atlas.site import build_site, search_text


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory, root: Path) -> Path:
    out = tmp_path_factory.mktemp("site")
    build_site(load_atlas(root / "data"), out)
    return out


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = dict(attrs)
        if d.get("id"):
            self.ids.add(str(d["id"]))
        for key in ("href", "src"):
            if d.get(key):
                self.links.append(str(d[key]))


def test_every_selection_rendered_once(site: Path, atlas) -> None:  # type: ignore[no-untyped-def]
    c = atlas.collection("bach-cantabile-harmony")
    html = "".join(p.read_text() for p in sorted((site / c.id).glob("*/index.html")))
    for s in c.selections():
        assert html.count(f'id="{s.id}"') == 1, s.id


def test_internal_links_resolve(site: Path) -> None:
    for page in site.rglob("*.html"):
        if page.name == "404.html":
            continue  # absolute links by design; see test_404_uses_base_url
        parser = _Links()
        parser.feed(page.read_text())
        for link in parser.links:
            u = urlparse(link)
            if u.scheme or link.startswith("#") or not u.path:
                continue
            target = (page.parent / u.path).resolve()
            assert target.exists(), f"{page.relative_to(site)} → {link}"


def test_apple_links_are_honest(site: Path) -> None:
    line = (site / "bach-cantabile-harmony/04-line/index.html").read_text()
    assert line.count("Track not yet matched — find it on the album") == 30
    span = (site / "bach-cantabile-harmony/07-span/index.html").read_text()
    assert span.count("Track not yet matched — search link") == 12


def test_original_prompts_preserved(site: Path, root: Path) -> None:
    src = (
        root / "archive/2026-10-11-handoff/source/Bach_Cantabile_Interactive_Guide_Ground_Revised.html"
    ).read_text()
    deep = json.loads(re.search(r"const DEEP_FOCUS=(\{.*?\});let", src, re.S).group(1))  # type: ignore[union-attr]
    notes = json.loads(re.search(r"const NOTES=(\{.*?\});const", src, re.S).group(1))  # type: ignore[union-attr]
    html = "".join(p.read_text() for p in (site / "bach-cantabile-harmony").glob("*/index.html"))
    import html as h

    text = h.unescape(html)
    for entry in deep.values():
        for v in entry.values():
            assert v in text
    for key, v in notes.items():
        if key != "BWV 511":  # work no longer in the playlist; kept as orphaned note
            assert v in text, key


def test_search_index_and_legacy_journal_map(site: Path) -> None:
    data = json.loads((site / "bach-cantabile-harmony/atlas-data.json").read_text())
    assert data["total"] == 669
    assert len(data["legacy"]["positions"]) == 669
    assert data["legacy"]["positions"]["1"] == "s-fjvf7ay"
    assert data["legacy"]["storageKey"] == "bachCantabileJournal"


def test_search_text_matches_catalogue_spellings() -> None:
    t = search_text("Prelude No. 1 in C Major, BWV 846/1")
    assert "bwv 846" in t and "bwv846" in t
    assert "olafsson" in search_text("Víkingur Ólafsson")
    album = search_text("Prelude No. 2", plain=("Bach: The Well-Tempered Clavier Books 1 & 2, BWV 846-893",))
    assert "bwv846" not in album  # an album range must not make every track match "BWV 846"


def test_catalogue_search_hits_only_that_work(site: Path) -> None:
    data = json.loads((site / "bach-cantabile-harmony/atlas-data.json").read_text())
    hits = [s["title"] for s in data["selections"] if "bwv846" in s["q"].split()]
    assert hits == ["Prelude No. 1 in C Major, BWV 846/1", "Fugue No. 1 in C Major, BWV 846/2"]


def test_build_is_deterministic(root: Path, tmp_path: Path) -> None:
    atlas = load_atlas(root / "data")
    build_site(atlas, tmp_path / "a")
    build_site(atlas, tmp_path / "b")
    for p in (tmp_path / "a").rglob("*"):
        if p.is_file():
            assert p.read_bytes() == (tmp_path / "b" / p.relative_to(tmp_path / "a")).read_bytes()


def test_accessibility_basics(site: Path) -> None:
    for page in site.rglob("*.html"):
        html = page.read_text()
        assert '<html lang="en">' in html
        assert 'class="skip" href="#main"' in html
        assert html.count("<h1") == 1, page
    stage = (site / "bach-cantabile-harmony/01-ground/index.html").read_text()
    assert 'aria-current="page"' in stage
    for m in re.finditer(r'<textarea id="([^"]+)"', stage):
        assert f'for="{m.group(1)}"' in stage


def test_404_uses_base_url(root: Path, tmp_path: Path) -> None:
    build_site(load_atlas(root / "data"), tmp_path, base_url="/the-listening-atlas")
    html = (tmp_path / "404.html").read_text()
    assert 'href="/the-listening-atlas/assets/atlas.css"' in html
    assert 'href="/the-listening-atlas/index.html"' in html
