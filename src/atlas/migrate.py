"""One-time migration of the 2026-10-11 handoff package into canonical YAML.

The migration is deterministic: running it twice on the same inputs produces identical files. It never
invents identifiers, durations or URLs — anything missing from the source stays ``null`` and is marked
``needs_verification``. After the initial import the YAML under ``data/`` is the source of truth and is
edited by hand; this module is kept so the import can be audited and re-run in tests.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import yamlio
from .catalogue import CatalogueRef, find_bwv, find_bwv_in_slug, parse_apple_url, slugify
from .snapshot import STATUS_KEEP, STATUS_REPLACEMENT_ALBUM, STATUS_REPLACEMENT_APPROX, Row, read_master_csv

COLLECTION_ID = "bach-cantabile-harmony"
SNAPSHOT_ID = "master-669"
HANDOFF_DIR = Path("archive/2026-10-11-handoff")
MASTER_CSV = HANDOFF_DIR / "source/Bach_Cantabile_Master_Ground_Revised.csv"
GUIDE_HTML = HANDOFF_DIR / "source/Bach_Cantabile_Interactive_Guide_Ground_Revised.html"
STUDENT_GUIDE = HANDOFF_DIR / "editorial/Bach_Cantabile_Student_Guide.md"

BACH = "Johann Sebastian Bach"

# Curated work titles where the title cannot be cleanly derived from an Apple track title.
WORK_TITLES: dict[str, str] = {
    "bwv-anh-114": "Minuet in G Major (Notebook for Anna Magdalena Bach, 1725)",
    "bwv-anh-120": "Minuet in A Minor (Notebook for Anna Magdalena Bach, 1725)",
    "bwv-177": "Ich ruf zu dir, Herr Jesu Christ (cantata)",
    "bwv-639": "Ich ruf zu dir, Herr Jesu Christ (chorale prelude)",
    "bwv-140": "Wachet auf, ruft uns die Stimme (cantata)",
    "bwv-645": "Wachet auf, ruft uns die Stimme (chorale prelude)",
    "bwv-208": "Was mir behagt, ist nur die muntre Jagd (“Hunt Cantata”)",
    "bwv-170": "Vergnügte Ruh, beliebte Seelenlust",
    "bwv-57": "Selig ist der Mann",
    "bwv-105": "Herr, gehe nicht ins Gericht mit deinem Knecht",
    "bwv-659": "Nun komm, der Heiden Heiland (chorale prelude)",
    "bwv-12": "Weinen, Klagen, Sorgen, Zagen",
    "bwv-82": "Ich habe genug",
    "bwv-156": "Ich steh mit einem Fuß im Grabe",
    "bwv-527": "Trio Sonata No. 3 in D Minor",
    "bwv-992": "Capriccio in B-flat Major “On the Departure of His Beloved Brother”",
    "bwv-831": "Overture in the French Style",
    "bwv-542": "Fantasia and Fugue in G Minor",
    "bwv-578": "Fugue in G Minor (“Little”)",
    "bwv-1039": "Trio Sonata for Two Flutes and Continuo in G Major",
    "bwv-1044": "Concerto for Flute, Violin and Harpsichord in A Minor",
    "bwv-1049": "Brandenburg Concerto No. 4 in G Major",
    "bwv-1050": "Brandenburg Concerto No. 5 in D Major",
    "bwv-1057": "Keyboard Concerto No. 6 in F Major",
    "bwv-1068": "Orchestral Suite No. 3 in D Major",
    "bwv-829": "Partita No. 5 in G Major",
    "bwv-801": "Three-Part Invention No. 15 in B Minor",
    "bwv-244": "St Matthew Passion",
    "bwv-245": "St John Passion",
    "bwv-232": "Mass in B Minor",
    "bwv-1079": "The Musical Offering",
    "bwv-1080": "The Art of Fugue",
    "bwv-668a": "Wenn wir in höchsten Nöten sein (“Vor deinem Thron”)",
}

WORK_ATTRIBUTION: dict[str, dict[str, Any]] = {
    "bwv-anh-114": {
        "composer": "Christian Petzold",
        "attribution_note": "Listed in the BWV Anhang; by Christian Petzold, not by J. S. Bach.",
    },
    "bwv-anh-120": {
        "composer": None,
        "attribution_note": "Composer attribution uncertain (Notebook for Anna Magdalena Bach).",
    },
}

# Facts about recordings stated in the handoff (album text, audit sheet, editorial brief). Nothing else is added.
RECORDING_FACTS: dict[str, dict[str, Any]] = {
    "1721143424": {
        "label": "Hyperion",
        "release_year": 1994,
        "version": "Angela Hewitt, Inventions & Sinfonias (Hyperion, 1994)",
        "sources": ["https://angelahewitt.com/discography/the-inventions/"],
        "notes": "Replaces András Schiff (Decca) for the Inventions & Sinfonias. Hewitt track-level Apple IDs "
        "not yet matched; the same Apple album already supplies BWV 903 song IDs.",
    },
    "1721145434": {
        "label": None,
        "release_year": None,
        "version": "Intended: Angela Hewitt's later Well-Tempered Clavier (Hyperion; recorded 2008, released 2009), "
        "Books I and II",
        "version_verified": False,
        "notes": "Edition and recording date of this Apple album not yet verified against the later cycle.",
    },
    "1766083236": {"release_year": 2024, "notes": "Víkingur Ólafsson, Continuum EP (2024)."},
}
OLAFSSON_989_KEY = "search:olafsson-dg-2018"
RECORDING_FACTS[OLAFSSON_989_KEY] = {
    "label": "Deutsche Grammophon",
    "release_year": 2018,
    "version": "Víkingur Ólafsson, Johann Sebastian Bach (Deutsche Grammophon, 2018)",
    "sources": ["https://us-store.deutschegrammophon.com/products/vikingur-olaffson-triad-3cd"],
    "notes": "Track list and timings from the DG catalogue; Apple Music links are a search page. Possibly the "
    "same Apple album as Ólafsson's BWV 659 (Apple album 1410551592) — verify before matching song IDs.",
}

STAGE_SLUGS = {
    1: "ground",
    2: "breath",
    3: "motion",
    4: "line",
    5: "rhetoric",
    6: "exchange",
    7: "span",
    8: "order",
    9: "transformation",
    10: "convergence",
    11: "essence",
}

# Minimal factual itinerary updates approved by the editor on 2026-10-11. Original text kept as itinerary_source.
ITINERARY_UPDATES: dict[int, tuple[str, str]] = {
    1: ("and Bach BWV511;", "and the Minuet in A minor BWV Anh.120 (composer uncertain);"),
    4: (
        "Schiff: 15 Inventions and 15 Sinfonias;",
        "Hewitt (Hyperion, 1994): 15 Inventions and 15 Sinfonias;",
    ),
    7: ("Hewitt: BWV989;", "Ólafsson (DG, 2018): BWV989, including the concluding Aria da capo;"),
}

STAGE_CONSTRAINTS: dict[int, dict[str, Any]] = {
    1: {"pinned_opening_song_ids": ["1577781357", "1577780575"]},
    2: {"max_selections": 19},
}

STAGE_NOTICES: dict[int, str] = {
    2: "Breath reconciliation pending: an approved 19-selection sequence exists but is not yet merged into this "
    "playlist. See the editorial status page.",
}

# Generic per-track prompts transcribed from the original HTML guide's trackPrompt() function.
FALLBACK_PROMPTS = [
    {
        "match": "fugue|fuga|contrapunctus",
        "prompt": "Follow one subject entry, then sing a different voice. What makes the voices belong together?",
    },
    {
        "match": "sarabande|allemande|courante|gigue|menuet|gavotte|bourr[eé]e",
        "prompt": "Feel the dance pulse; locate one point where the singing phrase leans against the meter.",
    },
    {
        "match": "aria|choral|chorale|chorus|recitative",
        "prompt": "Listen for the phrase’s breath, harmonic tension and cadence; follow the words if sung.",
    },
    {
        "match": "prelude|pr[eé]lude",
        "prompt": "Trace the bass and harmonic direction. What does the figuration make audible?",
    },
    {
        "match": "variation|var\\.",
        "prompt": "Hear what changes and what remains recognizable in the underlying pattern.",
    },
]


# --------------------------------------------------------------------------------------------- helpers


def selection_id(position: int) -> str:
    digest = hashlib.sha256(f"{COLLECTION_ID}/{SNAPSHOT_ID}/{position}".encode()).digest()
    return "s-" + base64.b32encode(digest).decode().lower()[:7]


_ARRANGEMENT = re.compile(r"\s*\((?P<text>(?:Arr\.|arr\.|Transcr\.)[^)]*)\)")


@dataclass
class ParsedTitle:
    ref: CatalogueRef
    inferred_from: str
    movement: str | None
    arrangement: str | None


def parse_title(row: Row) -> ParsedTitle:
    title = row["title"]
    ref = find_bwv(title)
    inferred = "title"
    if ref is None:
        for field, finder in (
            ("apple_music_url", find_bwv_in_slug),
            ("album_url", find_bwv_in_slug),
            ("album", find_bwv),
        ):
            ref = finder(row[field])
            if ref is not None:
                inferred = field
                break
    if ref is None:
        raise ValueError(f"position {row['position']}: cannot identify a catalogue number in {title!r}")

    arr_m = _ARRANGEMENT.search(title)
    arrangement = arr_m.group("text") if arr_m else None

    if inferred != "title":
        movement: str | None = title
    else:
        rest = _ARRANGEMENT.sub("", title[ref.span[1] :]).strip()
        if ": " in rest or rest.startswith(":"):
            movement = rest.split(":", 1)[1].strip() or None
        elif ref.sub and re.match(r"(Prelude|Fugue)\b", title):
            movement = title.split()[0]
        elif ref.sub:
            movement = f"No. {ref.sub}"
        else:
            movement = None
    return ParsedTitle(ref, inferred, movement, arrangement)


def derive_work_title(row: Row, parsed: ParsedTitle) -> str:
    wid = parsed.ref.work_id
    if wid in WORK_TITLES:
        return WORK_TITLES[wid]
    num = int(re.sub(r"\D", "", parsed.ref.number) or 0)
    pre = row["title"][: parsed.ref.span[0]].rstrip(' ,("').strip()
    if 846 <= num <= 893:
        book = "I" if num <= 869 else "II"
        return f"The Well-Tempered Clavier, Book {book}: " + pre.replace("Prelude", "Prelude and Fugue", 1)
    return pre


def recording_key(row: Row) -> str:
    link = parse_apple_url(row["album_url"])
    if link.album_id:
        return link.album_id
    if link.kind == "search" and "Olafsson" in row["album_url"]:
        return OLAFSSON_989_KEY
    raise ValueError(f"position {row['position']}: no album identity in {row['album_url']!r}")


# Readable IDs for recordings whose automatic slug is clumsy. Keys are Apple album IDs (or placeholders).
RECORDING_IDS: dict[str, str] = {
    "1852229971": "hewitt-plays-bach-and-more",
    "1410551592": "olafsson-johann-sebastian-bach",
    OLAFSSON_989_KEY: "olafsson-dg-2018",
    "1721143424": "hewitt-inventions-sinfonias-1994",
    "1721145434": "hewitt-wtc",
    "429782087": "perahia-piano-concertos",
    "73238424": "hunt-lieberson-cantatas-82-199",
    "1721142200": "hewitt-toccatas",
    "1721137911": "hewitt-italian-concerto-french-overture-duets",
    "1023324548": "fleisher-two-hands",
    "1577776877": "trifonov-art-of-life",
    "354034192": "perahia-english-suites-1-3-6",
    "158519795": "perahia-english-suites-2-4-5",
    "328344829": "perahia-partitas-1-5-6",
    "378454353": "perahia-partitas-2-3-4",
    "1724251065": "suzuki-brandenburg-orchestral-suites",
    "1724260101": "suzuki-cantatas-vol-25",
    "1727101422": "suzuki-cantatas-vol-37",
    "1724258470": "suzuki-cantatas-vol-42",
    "207672419": "herreweghe-weinen-klagen-cantatas",
    "1707369107": "herreweghe-cantatas-for-bass",
    "1572120521": "herreweghe-st-john-passion",
    "251240562": "herreweghe-st-matthew-passion",
    "337944523": "perahia-goldberg-variations",
    "1697993912": "hewitt-art-of-fugue",
    "1440762426": "perahia-french-suites",
    "597604194": "perahia-songs-without-words",
}

_ALBUM_STOP = {"bach", "j", "s", "johann", "sebastian", "js", "the", "of", "and", "for"}


def recording_slug(principal: str, album: str) -> str:
    lead = re.split(r"\s*[/;]\s*", principal)[0]
    surname = slugify(lead).split("-")[-1]
    words = [w for w in slugify(album).split("-") if w and w not in _ALBUM_STOP]
    return "-".join([surname, *words[:4]]) if words else surname


# --------------------------------------------------------------------------------------------- HTML guide


@dataclass
class GuideData:
    stages: list[dict[str, Any]]
    notes: dict[str, str]
    deep_focus: dict[str, dict[str, str]]
    header_lead: str
    epigraph: str
    how_to_listen: list[str]


def _js_const(script: str, name: str) -> Any:
    m = re.search(rf"const {name}=(.*?);(?:const |let )", script, re.S)
    if not m:
        raise ValueError(f"constant {name} not found in guide HTML")
    return json.loads(m.group(1))


def read_guide_html(path: Path) -> GuideData:
    html = path.read_text(encoding="utf-8")
    script = re.search(r"<script>(.*?)</script>", html, re.S)
    assert script
    js = script.group(1)
    header = re.search(r"<header>.*?<blockquote>(.*?)</blockquote><p>(.*?)</p></header>", html, re.S)
    vision = re.search(r'<section class="panel intro" id="vision">(.*?)</section>', html, re.S)
    assert header and vision
    paras = [re.sub(r"<[^>]+>", "", p).strip() for p in re.findall(r"<p>(.*?)</p>", vision.group(1), re.S)]
    return GuideData(
        stages=_js_const(js, "STAGES"),
        notes=_js_const(js, "NOTES"),
        deep_focus=_js_const(js, "DEEP_FOCUS"),
        epigraph=header.group(1).strip().strip("“”"),
        header_lead=header.group(2).strip(),
        how_to_listen=paras,
    )


def read_student_guide(path: Path) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = defaultdict(list)
    current = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            current = line[2:].strip()
            continue
        if current and line.strip() and not line.startswith("#"):
            sections[current].append(line.strip().removeprefix("- "))
    return sections


# --------------------------------------------------------------------------------------------- migration


@dataclass
class Migrated:
    files: dict[Path, Any]  # relative path -> YAML-able data
    headers: dict[Path, str]


def migrate(root: Path) -> Migrated:
    rows = read_master_csv(root / MASTER_CSV)
    guide = read_guide_html(root / GUIDE_HTML)
    student = read_student_guide(root / STUDENT_GUIDE)

    works: dict[str, dict[str, Any]] = {}
    rec_rows: dict[str, list[Row]] = defaultdict(list)
    parsed_rows: list[tuple[Row, ParsedTitle]] = []
    for row in rows:
        parsed = parse_title(row)
        parsed_rows.append((row, parsed))
        wid = parsed.ref.work_id
        if wid not in works:
            attribution = WORK_ATTRIBUTION.get(wid, {"composer": BACH})
            works[wid] = {
                "id": wid,
                "catalogue": parsed.ref.label,
                "title": derive_work_title(row, parsed),
                **attribution,
            }
        rec_rows[recording_key(row)].append(row)

    # Recordings: one per Apple album (or per search placeholder), in first-appearance order.
    recordings: dict[str, dict[str, Any]] = {}
    rec_id_by_key: dict[str, str] = {}
    used_slugs: set[str] = set()
    for key, rrows in rec_rows.items():
        principal = Counter(r["principal_artist"] for r in rrows).most_common(1)[0][0]
        with_ids = [r["album"] for r in rrows if r["apple_song_id"]] or [r["album"] for r in rrows]
        album = Counter(with_ids).most_common(1)[0][0]
        slug = RECORDING_IDS.get(key) or recording_slug(principal, album)
        if slug in used_slugs:
            slug = f"{slug}-{key}"
        used_slugs.add(slug)
        rec_id_by_key[key] = slug
        facts = RECORDING_FACTS.get(key, {})
        is_search = key.startswith("search:")
        recordings[slug] = {
            "id": slug,
            "principal_artist": principal,
            "album_title": album,
            "apple_album_id": None if is_search else key,
            "label": facts.get("label"),
            "release_year": facts.get("release_year"),
            "version": facts.get("version"),
            "verification": "needs_verification"
            if is_search or facts.get("version_verified") is False
            else "snapshot_matched",
            **({"sources": facts["sources"]} if "sources" in facts else {}),
            **({"notes": facts["notes"]} if "notes" in facts else {}),
        }

    # Selections, grouped by stage file.
    stage_files: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row, parsed in parsed_rows:
        pos = int(row["position"])
        rid = rec_id_by_key[recording_key(row)]
        rec = recordings[rid]
        link = parse_apple_url(row["apple_music_url"])
        sel: dict[str, Any] = {
            "id": selection_id(pos),
            "work": parsed.ref.work_id,
            "movement": parsed.movement,
        }
        if parsed.arrangement:
            sel["arrangement"] = parsed.arrangement
        sel["recording"] = rid
        sel["title"] = row["title"]
        sel["credits"] = row["artists"]
        if row["principal_artist"] != rec["principal_artist"]:
            sel["principal_artist"] = row["principal_artist"]
        if row["album"] != rec["album_title"]:
            sel["album_as_listed"] = row["album"]
        sel["duration"] = int(row["seconds"]) if row["seconds"] else None
        if row["status"] == STATUS_REPLACEMENT_APPROX:
            sel["duration_status"] = "approximate"
        sel["apple_music"] = {
            "song_id": row["apple_song_id"] or None,
            "url": row["apple_music_url"],
            "album_url": row["album_url"],
        }
        if row["status"] == STATUS_KEEP:
            sel["status"] = "keep"
        elif row["status"] in (STATUS_REPLACEMENT_ALBUM, STATUS_REPLACEMENT_APPROX):
            sel["status"] = "replacement_selected"
        else:
            raise ValueError(f"position {pos}: unknown status {row['status']!r}")
        sel["verification"] = "snapshot_matched" if row["apple_song_id"] else "needs_verification"
        if link.kind not in ("song", "album-track"):
            sel["link_kind"] = link.kind
        if row["editorial_note"]:
            sel["editorial_note"] = row["editorial_note"]
        src: dict[str, Any] = {"snapshot": SNAPSHOT_ID, "position": pos}
        if parsed.inferred_from != "title":
            src["work_inferred_from"] = parsed.inferred_from
        sel["source"] = src
        stage_files[int(row["stage_number"])].append(sel)

    pos_to_sel = {int(r["position"]): selection_id(int(r["position"])) for r in rows}

    # Stages.
    stages = []
    for st in guide.stages:
        n = st["n"]
        entry: dict[str, Any] = {
            "id": STAGE_SLUGS[n],
            "number": n,
            "name": st["name"],
            "principle": st["principle"],
            "question": st["question"],
            "direction": st["direction"],
            "at_the_piano": st["piano"],
            "itinerary": st["itinerary"],
        }
        if n in ITINERARY_UPDATES:
            old, new = ITINERARY_UPDATES[n]
            assert old in st["itinerary"], (n, old)
            entry["itinerary"] = st["itinerary"].replace(old, new)
            entry["itinerary_source"] = st["itinerary"]
        if n in STAGE_NOTICES:
            entry["editorial_notice"] = STAGE_NOTICES[n]
        if n in STAGE_CONSTRAINTS:
            entry["constraints"] = STAGE_CONSTRAINTS[n]
        stages.append(entry)

    # Work-level focus notes, re-keyed from the HTML's "BWV n" keys to work IDs.
    work_focus: dict[str, str] = {}
    orphaned: list[dict[str, str]] = []
    for key, text in guide.notes.items():
        wid = "bwv-anh-114" if key == "BWV 114" else slugify(key)
        if wid in works:
            work_focus[wid] = text
        else:
            orphaned.append(
                {"source_key": key, "text": text, "reason": "Work not present in the 669-row snapshot."}
            )

    deep_focus = {
        pos_to_sel[int(pos)]: {"source_position": int(pos), **entry}
        for pos, entry in guide.deep_focus.items()
    }

    collection = {
        "id": COLLECTION_ID,
        "title": "Bach: Cantabile & Harmony",
        "subtitle": "Eleven hearing stages",
        "composers": [BACH],
        "volume_principle": "Cantabile — making the musical line sing — is this volume's way into Bach's "
        "musical relationships. It is specific to this Bach volume, not a rule for the Atlas.",
        "epigraph": guide.epigraph,
        "lead": guide.header_lead,
        "how_to_listen": guide.how_to_listen,
        "vision": student["The vision"],
        "how_to_use": student["How to use the guide"],
        "beyond_the_sequence": student["Listening beyond the sequence"],
        "guide": {
            "title": "Bach Listening Guide",
            "subtitle": "Cantabile & Harmony · Eleven Hearing Stages",
            "stages_heading": "The eleven stages",
        },
        "public_playlist_url": "https://music.apple.com/us/playlist/bach/pl.u-kv9lRpvs7v0a9Yb",
        "public_playlist_note": "Public reference only; not proof that this data and the live playlist are identical.",
        "fallback_prompts": FALLBACK_PROMPTS,
        "stage_files": [f"selections/{n:02d}-{STAGE_SLUGS[n]}.yaml" for n in sorted(stage_files)],
    }

    base = Path("data")
    cdir = base / "collections" / COLLECTION_ID
    files: dict[Path, Any] = {
        base / "atlas.yaml": {
            "title": "The Listening Atlas",
            "method": "Listen to what the music is doing; let expressive understanding arise from audible "
            "musical relationships.",
            "collections": [COLLECTION_ID],
        },
        base / "works" / "bach.yaml": {"works": list(works.values())},
        base / "recordings.yaml": {"recordings": list(recordings.values())},
        cdir / "collection.yaml": collection,
        cdir / "stages.yaml": {"stages": stages},
        cdir / "notes" / "work-focus.yaml": {"work_focus": work_focus, "orphaned": orphaned},
        cdir / "notes" / "deep-focus.yaml": {"deep_focus": deep_focus},
        cdir / "retired.yaml": {"retired": []},
        cdir / "issues.yaml": {"issues": build_issues(pos_to_sel)},
        cdir / "proposals" / "breath-19.yaml": build_breath_proposal(pos_to_sel),
    }
    for n, sels in sorted(stage_files.items()):
        files[cdir / f"selections/{n:02d}-{STAGE_SLUGS[n]}.yaml"] = {
            "stage": STAGE_SLUGS[n],
            "selections": sels,
        }

    headers = {
        cdir / f"selections/{n:02d}-{STAGE_SLUGS[n]}.yaml": (
            f"Stage {n} · {STAGE_SLUGS[n].title()} — playlist order is the order of this list.\n"
            "To move a selection, move its whole block. Never reuse or renumber `id` values."
        )
        for n in stage_files
    }
    headers[cdir / "proposals" / "breath-19.yaml"] = (
        "PROPOSED PATCH — NOT APPLIED. Approved 19-selection Breath sequence (editorial/BREATH_19_APPROVED.md).\n"
        "Check with `atlas proposal check breath-19`; apply only after song IDs are verified."
    )
    return Migrated(files, headers)


def write(root: Path, migrated: Migrated) -> list[Path]:
    for rel, data in migrated.files.items():
        yamlio.dump(data, root / rel, header=migrated.headers.get(rel))
    return sorted(migrated.files)


# --------------------------------------------------------------------------------------------- editorial registry


def build_issues(sel: dict[int, str]) -> list[dict[str, Any]]:
    def ids(*positions: int) -> list[str]:
        return [sel[p] for p in positions]

    return [
        {
            "id": "ED-001",
            "stage": "ground",
            "title": "BWV 924 vs BWV 939 as first Hewitt prelude",
            "status": "open",
            "detail": "A prior discussion floated BWV 939 as the first Hewitt prelude; the snapshot has BWV 924 at "
            "position 3 and BWV 939 at position 15 (numerical order). Not reordered.",
            "selections": ids(3, 15),
            "action": "Editor to confirm intended order.",
        },
        {
            "id": "ED-002",
            "stage": "ground",
            "title": "BWV Anh. 120 duration missing",
            "status": "open",
            "detail": "Song ID 1577780575 is approved; duration is blank in the snapshot.",
            "selections": ids(2),
            "action": "Verify duration from Apple Music.",
        },
        {
            "id": "ED-003",
            "stage": "breath",
            "title": "Approved 19-selection Breath sequence not merged",
            "status": "open",
            "detail": "Snapshot has 15 Breath selections. The approved sequence replaces Fleisher's BWV 208 with "
            "Hewitt's Mary Howe transcription and adds BWV 147/X, BWV 199, BWV 21/III and BWV 127/III. "
            "Four new items lack song IDs; BWV 127/III has a user-supplied URL.",
            "selections": ids(25),
            "proposal": "proposals/breath-19.yaml",
            "action": "Verify song IDs, then apply the proposal.",
        },
        {
            "id": "ED-004",
            "stage": "line",
            "title": "Hewitt Inventions & Sinfonias: 30 track IDs unresolved",
            "status": "open",
            "detail": "Positions 195–224 link only to Apple album 1721143424 (which also supplies BWV 903 song IDs). "
            "Durations are blank; the notes' reference to retained Schiff timings is not reflected in the data.",
            "selections": ids(*range(195, 225)),
            "action": "Match each Hewitt track on album 1721143424; add song IDs and durations.",
        },
        {
            "id": "ED-005",
            "stage": "line",
            "title": "Invention No. 1 labelled BWV 772a",
            "status": "open",
            "detail": "Apple labels the track BWV 772a; confirm the intended version of Invention No. 1.",
            "selections": ids(195),
            "action": "Editor to confirm.",
        },
        {
            "id": "ED-006",
            "stage": "span",
            "title": "Ólafsson BWV 989: 12 track IDs unresolved; durations approximate",
            "status": "open",
            "detail": "Links are an Apple Music search page. Order Aria → Variations I–X → Aria da capo is correct. "
            "Ólafsson's BWV 659 (position 30) is on Apple album 1410551592, likely the same DG 2018 album.",
            "selections": ids(*range(317, 329)),
            "action": "Match each track (check album 1410551592); replace approximate durations.",
        },
        {
            "id": "ED-007",
            "stage": "span",
            "title": "BWV 582: does the track include the fugue?",
            "status": "open",
            "detail": "Track title says Passacaglia only.",
            "selections": ids(329),
            "action": "Listen and confirm coverage.",
        },
        {
            "id": "ED-008",
            "stage": "order",
            "title": "Confirm Hewitt WTC edition is the later (2008/2009) cycle",
            "status": "open",
            "detail": "Apple album 1721145434 holds all 96 tracks in order; edition/recording date not verified.",
            "selections": ids(370),
            "action": "Verify album edition against Hyperion's later WTC release.",
        },
        {
            "id": "ED-009",
            "stage": "convergence",
            "title": "“Erbarme dich” comes from a different Apple album",
            "status": "open",
            "detail": "Position 576 is on album 276069994 (“Erbarme Dich – Old SOTW”), not the St Matthew Passion "
            "album 251240562; its song ID is in the same range, suggesting the same performance.",
            "selections": ids(576),
            "action": "Confirm same performance; consider switching to the Passion album track.",
        },
        {
            "id": "ED-010",
            "stage": "essence",
            "title": "Musical Offering order vs “recorded order”",
            "status": "open",
            "detail": "The guide calls for the recorded order; the snapshot begins with Canon 1 à 2 and places "
            "Ricercar à 3 seventh. Album track order not verified offline.",
            "selections": ids(*range(633, 649)),
            "action": "Compare with Apple album 1724249803 track order; do not reorder without approval.",
        },
        {
            "id": "ED-011",
            "stage": None,
            "title": "Student guide and HTML itineraries describe the earlier 668-track playlist",
            "status": "partially_resolved",
            "detail": "Guide mentions BWV 511, Petri/Fleisher, Schiff and Hewitt BWV 989; ranges from Stage 7 on are "
            "off by one; total running time stale. Stages 1, 4 and 7 itineraries received factual updates "
            "(originals kept as itinerary_source). Stage 2 awaits ED-003.",
            "selections": [],
            "action": "Revise student guide prose after Breath is reconciled.",
        },
        {
            "id": "ED-012",
            "stage": None,
            "title": "Work notes that never displayed in the original HTML",
            "status": "resolved",
            "detail": "Title-derived grouping hid the notes for BWV 232, 1049, 1079, 1080 and Anh. 114. Notes are now "
            "keyed by work ID and display. The BWV 511 note is kept as orphaned.",
            "selections": [],
            "action": "None.",
        },
        {
            "id": "ED-013",
            "stage": None,
            "title": "HTML note text says “Replaces Angela Hewitt Decca”",
            "status": "resolved",
            "detail": "The 30 Inventions rows in the HTML misname the replaced pianist; the CSV (canonical) correctly "
            "says András Schiff. CSV text was migrated.",
            "selections": [],
            "action": "None.",
        },
        {
            "id": "ED-014",
            "stage": None,
            "title": "Source typos and credits kept verbatim",
            "status": "open",
            "detail": "“E-FlA Major” (position 58), “in in B Minor.” (224) are Apple/ source titles kept as-is. "
            "Suzuki organ BWV 582 has principal artist “Masaaki Suzuki / Bach Collegium Japan”.",
            "selections": ids(58, 224, 329),
            "action": "Decide whether to keep Apple's titles verbatim.",
        },
    ]


def build_breath_proposal(sel: dict[int, str]) -> dict[str, Any]:
    def keep(pos: int, n: int) -> dict[str, Any]:
        return {"n": n, "existing": sel[pos]}

    def new(n: int, work: str, movement: str, performers: str, **extra: Any) -> dict[str, Any]:
        return {
            "n": n,
            "new": {
                "work": work,
                "movement": movement,
                "performers": performers,
                "apple_music": {"song_id": None, "url": None},
                "verification": "needs_verification",
                **extra,
            },
        }

    return {
        "id": "breath-19",
        "stage": "breath",
        "status": "proposed",
        "source": "archive/2026-10-11-handoff/editorial/BREATH_19_APPROVED.md",
        "principle": "Cantabile reveals the truth of musical becoming.",
        "question": "What makes this phrase need to continue—and what finally allows it to rest?",
        "arc": "invocation → vocal/piano pairing → different breaths → vulnerability/longing → instability/lament → "
        "burden → suspension → sufficiency",
        "max_selections": 19,
        "retire": [
            {
                "selection": sel[25],
                "reason": "Replaced by Hewitt's Mary Howe transcription (approved in editorial discussion).",
            }
        ],
        "new_works": [
            {
                "id": "bwv-147",
                "catalogue": "BWV 147",
                "title": "Herz und Mund und Tat und Leben",
                "composer": BACH,
            },
            {
                "id": "bwv-199",
                "catalogue": "BWV 199",
                "title": "Mein Herze schwimmt im Blut",
                "composer": BACH,
            },
            {"id": "bwv-21", "catalogue": "BWV 21", "title": "Ich hatte viel Bekümmernis", "composer": BACH},
            {
                "id": "bwv-127",
                "catalogue": "BWV 127",
                "title": "Herr Jesu Christ, wahr' Mensch und Gott",
                "composer": BACH,
            },
        ],
        "sequence": [
            keep(21, 1),
            keep(22, 2),
            keep(23, 3),
            keep(24, 4),
            new(
                5,
                "bwv-208",
                "No. 9, Schafe können sicher weiden",
                "Angela Hewitt",
                arrangement="Piano transcription by Mary Howe",
                note="Replaces Leon Fleisher's Egon Petri arrangement; confirm exact track match.",
            ),
            new(
                6,
                "bwv-147",
                "X. Choral “Jesus bleibet meine Freude”",
                "Masaaki Suzuki / Bach Collegium Japan",
                note="Original chorus only; no piano transcription.",
            ),
            keep(26, 7),
            new(
                8,
                "bwv-199",
                "“Tief gebückt und voller Reue”",
                "Lorraine Hunt Lieberson",
                note="Her BWV 82 album (“Bach: Cantatas, BWV 82 & 199”, Apple album 73238424) is a likely source.",
            ),
            keep(27, 9),
            keep(28, 10),
            keep(29, 11),
            keep(30, 12),
            new(
                13,
                "bwv-21",
                "III. Aria “Seufzer, Tränen, Kummer, Not”",
                "Barbara Schlick / Philippe Herreweghe",
            ),
            keep(31, 14),
            keep(32, 15),
            keep(33, 16),
            keep(34, 17),
            {
                "n": 18,
                "new": {
                    "work": "bwv-127",
                    "movement": "III. Aria “Die Seele ruht in Jesu Händen”",
                    "performers": "Masaaki Suzuki / Bach Collegium Japan",
                    "apple_music": {
                        "song_id": "1727109118",
                        "url": "https://classical.music.apple.com/us/album/1727108827?i=1727109118&l=en-US",
                    },
                    "verification": "user_supplied",
                    "note": "URL supplied by the editor; confirm the track.",
                },
            },
            keep(35, 19),
        ],
    }
