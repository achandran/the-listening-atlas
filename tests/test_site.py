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
    retired = {"2"}  # Anh. 120, retired 2026-10-11; its study is preserved in retired.yaml
    for pos, entry in deep.items():
        for v in entry.values():
            assert (v in text) is (pos not in retired), pos
    for key, v in notes.items():
        if key != "BWV 511":  # work no longer in the playlist; kept as orphaned note
            assert v in text, key


def test_search_index(site: Path) -> None:
    data = json.loads((site / "bach-cantabile-harmony/atlas-data.json").read_text())
    assert data["total"] == 670 == len(data["selections"])
    assert set(data) == {"collection", "title", "total", "selections"}


def test_read_only_no_journal_or_storage(site: Path) -> None:
    """The site is a read view: no checklists, no note fields, no journal page, nothing stored in the browser."""
    assert not (site / "bach-cantabile-harmony/journal").exists()
    for page in site.rglob("*.html"):
        html = page.read_text()
        for forbidden in ("<textarea", 'type="checkbox"', "Heard attentively", "journal", "Unheard"):
            assert forbidden not in html, (page.relative_to(site), forbidden)
    js = (site / "assets/atlas.js").read_text()
    assert "localStorage" not in js and "sessionStorage" not in js and "indexedDB" not in js


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
    for m in re.finditer(r'<(?:input|select) id="([^"]+)"', stage):
        assert f'for="{m.group(1)}"' in stage


def test_404_uses_base_url(root: Path, tmp_path: Path) -> None:
    build_site(load_atlas(root / "data"), tmp_path, base_url="/the-listening-atlas")
    html = (tmp_path / "404.html").read_text()
    assert 'href="/the-listening-atlas/assets/atlas.css"' in html
    assert 'href="/the-listening-atlas/index.html"' in html


def _card(html: str, sel_id: str) -> str:
    start = html.index(f'id="{sel_id}"')
    return html[start : html.index("</article>", start)]


def test_single_track_work_is_one_flat_card(site: Path, atlas) -> None:  # type: ignore[no-untyped-def]
    """A work with one track has no collapsible wrapper; its heading, meta and focus appear once."""
    html = (site / "bach-cantabile-harmony/01-ground/index.html").read_text()
    first = atlas.collection("bach-cantabile-harmony").stage("ground").selections[0]
    assert re.search(
        rf'<div class="work work-single" data-group>\s*<article class="sel sel-single" id="{first.id}"', html
    )
    card = _card(html, first.id)
    assert card.count("Minuet in G Major (Notebook for Anna Magdalena Bach, 1725)") == 1
    assert card.count("Listening focus") == 1 and "Work-level focus" not in card
    assert "Follow the bass under the familiar melody." in card  # work note merged into the one panel
    assert "Daniil Trifonov · BACH: The Art of Life · 1:45" in card


def test_single_recording_work_shows_recording_once(site: Path, atlas) -> None:  # type: ignore[no-untyped-def]
    html = (site / "bach-cantabile-harmony/09-transformation/index.html").read_text()
    assert (
        html.count('<p class="recording-line">Murray Perahia · <span class="album">Bach: Goldberg Variations')
        == 1
    )
    sels = atlas.collection("bach-cantabile-harmony").stage("transformation").selections
    card = _card(html, sels[1].id)
    assert "Bach: Goldberg Variations" not in card.split("<a ")[0]  # album not repeated per track
    assert '<span class="t-short">Variation 1 a 1 Clav. (Instrumental)</span>' in card
    assert (
        '<span class="t-full">Goldberg Variations, BWV 988: Variation 1 a 1 Clav. (Instrumental)</span>'
        in card
    )


def test_mixed_recordings_keep_per_track_details(site: Path, atlas) -> None:  # type: ignore[no-untyped-def]
    """St Matthew includes one track from another album (ED-009), so nothing is collapsed for that work."""
    html = (site / "bach-cantabile-harmony/10-convergence/index.html").read_text()
    smp = [
        s
        for s in atlas.collection("bach-cantabile-harmony").stage("convergence").selections
        if s.work == "bwv-244"
    ]
    card = _card(html, smp[0].id)
    assert "t-short" not in card and "J.S. Bach: St. Matthew Passion, BWV 244" in card


def test_variations_get_the_variation_prompt(atlas) -> None:  # type: ignore[no-untyped-def]
    """'Variation' contains 'aria'; the vocal prompt must not be chosen for variation movements."""
    from atlas.site import fallback_prompt

    c = atlas.collection("bach-cantabile-harmony")
    st = c.stage("transformation")
    prompts = {fallback_prompt(c, st, s) for s in st.selections}
    assert prompts == {"Hear what changes and what remains recognizable in the underlying pattern."}
    span = c.stage("span")
    olafsson = [s for s in span.selections if s.work == "bwv-989"]
    assert all("Hear what changes" in fallback_prompt(c, span, s) for s in olafsson[1:-1])
