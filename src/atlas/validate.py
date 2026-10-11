"""Validation of canonical atlas data: schemas first, then cross-references and editorial rules."""

from __future__ import annotations

import json
import re
import unicodedata
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema

from . import yamlio
from .catalogue import parse_apple_url
from .model import Atlas, Collection, Selection, load_atlas

ERROR, WARNING, INFO = "error", "warning", "info"


@dataclass(frozen=True)
class Finding:
    level: str
    code: str
    message: str
    where: str = ""

    def format(self) -> str:
        loc = f" [{self.where}]" if self.where else ""
        return f"{self.level.upper():7} {self.code}: {self.message}{loc}"


@dataclass
class Report:
    findings: list[Finding]

    def by_level(self, level: str) -> list[Finding]:
        return [f for f in self.findings if f.level == level]

    @property
    def errors(self) -> list[Finding]:
        return self.by_level(ERROR)

    @property
    def warnings(self) -> list[Finding]:
        return self.by_level(WARNING)

    def ok(self, strict: bool = False) -> bool:
        return not self.errors and not (strict and self.warnings)


# ------------------------------------------------------------------------------------------- schemas


SCHEMA_FOR = {
    "atlas.yaml": "atlas",
    "recordings.yaml": "recordings",
    "collection.yaml": "collection",
    "stages.yaml": "stages",
    "issues.yaml": "issues",
    "retired.yaml": "retired",
    "work-focus.yaml": "notes",
    "deep-focus.yaml": "notes",
}


def _schema_name(path: Path) -> str | None:
    if path.parent.name == "works":
        return "works"
    if path.parent.name == "selections":
        return "selections"
    if path.parent.name == "proposals":
        return "proposal"
    return SCHEMA_FOR.get(path.name)


def check_schemas(data_dir: Path, schema_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    cache: dict[str, Any] = {}
    for path in sorted(data_dir.rglob("*.yaml")):
        name = _schema_name(path)
        rel = str(path.relative_to(data_dir.parent))
        if name is None:
            findings.append(Finding(WARNING, "SCHEMA-UNKNOWN-FILE", "no schema applies to this file", rel))
            continue
        if name not in cache:
            cache[name] = json.loads((schema_dir / f"{name}.schema.json").read_text(encoding="utf-8"))
        try:
            doc = yamlio.load(path)
        except Exception as exc:
            findings.append(Finding(ERROR, "YAML-SYNTAX", str(exc).splitlines()[0], rel))
            continue
        validator = jsonschema.Draft202012Validator(cache[name])
        for err in sorted(validator.iter_errors(doc), key=lambda e: list(map(str, e.absolute_path))):
            ptr = "/".join(str(p) for p in err.absolute_path)
            findings.append(Finding(ERROR, "SCHEMA", f"{ptr or '(root)'}: {err.message}", rel))
    return findings


# ------------------------------------------------------------------------------------------- references & rules


def _norm(text: str | None) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _where(s: Selection) -> str:
    return f"{s.file}#{s.index + 1} {s.id}"


def check_atlas(atlas: Atlas) -> list[Finding]:
    f: list[Finding] = [Finding(ERROR, "LOAD", e) for e in atlas.load_errors]
    f += [
        Finding(ERROR, "DUPLICATE-WORK-ID", f"work ID {w!r} defined more than once")
        for w in atlas.duplicate_work_ids
    ]
    f += [
        Finding(ERROR, "DUPLICATE-RECORDING-ID", f"recording ID {r!r} defined more than once")
        for r in atlas.duplicate_recording_ids
    ]
    for c in atlas.collections:
        f += check_collection(atlas, c)
    return f


def check_collection(atlas: Atlas, c: Collection) -> list[Finding]:
    f: list[Finding] = [Finding(ERROR, "LOAD", e) for e in c.load_errors]
    f += _check_stages(c)
    sels = c.selections()

    # Duplicate selection IDs (active, and active vs retired).
    counts = Counter(s.id for s in sels)
    retired_ids = {str((r.get("selection") or {}).get("id")) for r in c.retired}
    for s in sels:
        if counts[s.id] > 1:
            f.append(
                Finding(
                    ERROR,
                    "DUPLICATE-SELECTION-ID",
                    f"selection ID {s.id} is used {counts[s.id]} times",
                    _where(s),
                )
            )
        if s.id in retired_ids:
            f.append(
                Finding(
                    ERROR,
                    "RETIRED-ID-REUSED",
                    f"{s.id} belongs to a retired selection; mint a new ID",
                    _where(s),
                )
            )
    src_counts = Counter(
        (s.raw.get("source") or {}).get("snapshot", "") + f":{s.source_position}"
        for s in sels
        if s.source_position
    )
    for key, n in src_counts.items():
        if n > 1:
            f.append(Finding(ERROR, "DUPLICATE-SOURCE-ROW", f"{n} selections claim source row {key}"))

    for s in sels:
        f += _check_selection(atlas, s)

    f += _check_duplicates(sels)

    # Notes and issues must point at real things.
    known = set(counts) | retired_ids
    for sid in c.deep_focus:
        if sid not in counts:
            f.append(
                Finding(
                    ERROR,
                    "DANGLING-NOTE",
                    f"deep-focus note for unknown selection {sid}",
                    "notes/deep-focus.yaml",
                )
            )
    for wid in c.work_focus:
        if wid not in atlas.works:
            f.append(
                Finding(
                    ERROR, "DANGLING-NOTE", f"work-focus note for unknown work {wid}", "notes/work-focus.yaml"
                )
            )
    for issue in c.issues:
        for sid in issue.get("selections", []):
            if sid not in known:
                f.append(
                    Finding(
                        ERROR,
                        "DANGLING-ISSUE-REF",
                        f"{issue.get('id')} references unknown selection {sid}",
                        "issues.yaml",
                    )
                )

    unresolved = [s for s in sels if not s.song_id]
    if unresolved:
        f.append(
            Finding(
                WARNING,
                "UNRESOLVED-SONG-IDS",
                f"{len(unresolved)} selections have no Apple song ID (run `atlas audit` for the list)",
            )
        )
    no_dur = sum(1 for s in sels if s.duration is None)
    if no_dur:
        f.append(Finding(INFO, "MISSING-DURATIONS", f"{no_dur} selections have no duration"))
    approx = sum(1 for s in sels if s.duration_status == "approximate")
    if approx:
        f.append(Finding(INFO, "APPROXIMATE-DURATIONS", f"{approx} selections have approximate durations"))
    open_issues = sum(1 for i in c.issues if i.get("status") in ("open", "partially_resolved"))
    if open_issues:
        f.append(
            Finding(
                INFO, "OPEN-EDITORIAL-ISSUES", f"{open_issues} open editorial issues in {c.id}/issues.yaml"
            )
        )
    return f


def _check_stages(c: Collection) -> list[Finding]:
    f: list[Finding] = []
    numbers = [st.number for st in c.stages]
    if any(not isinstance(n, int) or n < 1 for n in numbers):
        f.append(
            Finding(
                ERROR,
                "STAGE-NUMBER-INVALID",
                f"stage numbers must be positive integers: {numbers}",
                "stages.yaml",
            )
        )
        return f
    dupes = [n for n, k in Counter(numbers).items() if k > 1]
    if dupes:
        f.append(Finding(ERROR, "STAGE-NUMBER-DUPLICATE", f"duplicate stage numbers {dupes}", "stages.yaml"))
    if sorted(numbers) != list(range(1, len(numbers) + 1)):
        f.append(
            Finding(
                ERROR,
                "STAGE-NUMBER-GAP",
                f"stage numbers must run 1..{len(numbers)}: {sorted(numbers)}",
                "stages.yaml",
            )
        )
    if numbers != sorted(numbers):
        f.append(
            Finding(
                ERROR, "STAGE-ORDER", "stages.yaml must list stages in ascending number order", "stages.yaml"
            )
        )

    stage_ids = [st.id for st in c.stages]
    file_stages: list[str] = []
    for rel in c.meta.get("stage_files", []) or []:
        try:
            file_stages.append(str((yamlio.load(c.path / rel) or {}).get("stage")))
        except Exception:
            continue
    if file_stages != stage_ids:
        f.append(
            Finding(
                ERROR,
                "STAGE-FILE-ORDER",
                f"collection.yaml stage_files order {file_stages} must match stages.yaml order {stage_ids}",
                "collection.yaml",
            )
        )
    for rel in c.meta.get("stage_files", []) or []:
        m = re.match(r"selections/(\d+)-", rel)
        st = next((s for s in c.stages if rel.endswith(f"-{s.id}.yaml")), None)
        if m and st and int(m.group(1)) != st.number:
            f.append(
                Finding(
                    ERROR,
                    "STAGE-FILE-NUMBER",
                    f"{rel} is numbered {int(m.group(1))} but stage {st.id!r} is number {st.number}",
                )
            )

    for st in c.stages:
        if not st.selections:
            f.append(Finding(WARNING, "EMPTY-STAGE", f"stage {st.id!r} has no selections"))
        mx = st.constraints.get("max_selections")
        if mx is not None and len(st.selections) > mx:
            f.append(
                Finding(
                    ERROR,
                    "STAGE-TOO-LONG",
                    f"stage {st.id!r} has {len(st.selections)} selections; editorial maximum is {mx}",
                )
            )
        pinned = st.constraints.get("pinned_opening_song_ids") or []
        actual = [s.song_id for s in st.selections[: len(pinned)]]
        if pinned and actual != pinned:
            f.append(
                Finding(
                    ERROR,
                    "PINNED-OPENING",
                    f"stage {st.id!r} must open with song IDs {pinned} in that order; found {actual}",
                )
            )
    return f


def _check_selection(atlas: Atlas, s: Selection) -> list[Finding]:
    f: list[Finding] = []
    w = _where(s)
    if s.work not in atlas.works:
        f.append(Finding(ERROR, "MISSING-WORK", f"work {s.work!r} is not defined in data/works/", w))
    if s.recording not in atlas.recordings:
        f.append(
            Finding(
                ERROR, "MISSING-RECORDING", f"recording {s.recording!r} is not defined in recordings.yaml", w
            )
        )

    if not s.url:
        f.append(
            Finding(
                ERROR, "MISSING-URL", "apple_music.url is empty; use an album or search link if unmatched", w
            )
        )
    else:
        link = parse_apple_url(s.url)
        if link.kind == "unknown":
            f.append(Finding(ERROR, "BAD-URL", f"not a recognised https Apple Music URL: {s.url}", w))
        elif link.kind == "playlist":
            f.append(Finding(ERROR, "BAD-URL", "selection URL points to a playlist, not a track", w))
        elif link.song_id:
            if s.song_id and s.song_id != link.song_id:
                f.append(
                    Finding(
                        ERROR,
                        "SONG-ID-MISMATCH",
                        f"song_id {s.song_id} does not match the ID in its URL ({link.song_id})",
                        w,
                    )
                )
            if not s.song_id:
                f.append(
                    Finding(
                        ERROR,
                        "SONG-ID-NOT-RECORDED",
                        f"URL contains song ID {link.song_id} but apple_music.song_id is null",
                        w,
                    )
                )
        else:
            declared = s.link_kind
            if declared != link.kind:
                f.append(
                    Finding(
                        ERROR,
                        "LINK-KIND",
                        f"URL is a {link.kind} link; set link_kind: {link.kind} so it is not mistaken for a "
                        "track",
                        w,
                    )
                )
            if s.song_id:
                f.append(
                    Finding(
                        ERROR,
                        "SONG-ID-MISMATCH",
                        f"song_id {s.song_id} set but URL is a {link.kind} link without that ID",
                        w,
                    )
                )
    if s.album_url and parse_apple_url(s.album_url).kind == "unknown":
        f.append(
            Finding(ERROR, "BAD-URL", f"album_url is not a recognised Apple Music URL: {s.album_url}", w)
        )

    if s.verification in ("verified", "snapshot_matched", "user_supplied") and not s.song_id:
        f.append(
            Finding(
                ERROR,
                "VERIFICATION-INCONSISTENT",
                f"verification is {s.verification!r} but song_id is null; use needs_verification",
                w,
            )
        )
    if s.verification == "needs_verification" and s.song_id and s.status == "keep" and not s.editorial_note:
        f.append(
            Finding(
                INFO, "VERIFICATION-NOTE", "needs_verification without an editorial_note explaining why", w
            )
        )
    if s.duration_status == "approximate" and s.duration is None:
        f.append(Finding(ERROR, "DURATION", "duration_status is approximate but duration is null", w))
    return f


def _check_duplicates(sels: list[Selection]) -> list[Finding]:
    """Invariant: within one collection's playlist, each recorded track appears at most once. No exceptions.

    A recorded track is identified by its Apple song ID and, independently, by work + movement + arrangement
    within one recording. Titles alone never identify a recording.
    """
    f: list[Finding] = []
    songs: dict[str, list[Selection]] = defaultdict(list)
    for s in sels:
        if s.song_id:
            songs[s.song_id].append(s)
    for sid, group in songs.items():
        for b in group[1:]:
            f.append(
                Finding(
                    ERROR,
                    "DUPLICATE-SONG",
                    f"Apple song {sid} is already in this playlist as {group[0].id} ({group[0].file}); "
                    "each recording may appear only once",
                    _where(b),
                )
            )

    moves: dict[tuple[str, str, str], list[Selection]] = defaultdict(list)
    for s in sels:
        moves[(s.work, _norm(s.movement), _norm(s.arrangement))].append(s)
    for (work, mv, _arr), group in moves.items():
        for b in group[1:]:
            a = group[0]
            if a.song_id and a.song_id == b.song_id:
                continue  # already reported as DUPLICATE-SONG
            label = f"{work} {mv or '(whole work)'}"
            if a.recording == b.recording:
                f.append(
                    Finding(
                        ERROR,
                        "DUPLICATE-MOVEMENT",
                        f"{label} from recording {a.recording} is already in this playlist as {a.id}; "
                        "each recording may appear only once",
                        _where(b),
                    )
                )
            else:
                # Allowed: a different performance of the same music. Reported so a re-release of the same
                # performance under another album (cf. ED-009) can be spotted.
                f.append(
                    Finding(
                        INFO,
                        "REPEATED-MOVEMENT",
                        f"{label} also appears as {a.id} in another recording ({a.recording}); confirm these "
                        "are different performances",
                        _where(b),
                    )
                )
    return f


# ------------------------------------------------------------------------------------------- network (opt-in)


def check_links_online(atlas: Atlas, timeout: float = 10.0, workers: int = 8) -> list[Finding]:
    """Opt-in HTTP check that each URL resolves. Not run in CI: it depends on the network and Apple's servers."""
    urls: dict[str, str] = {}
    for c in atlas.collections:
        for s in c.selections():
            if s.url:
                urls.setdefault(s.url, _where(s))

    def probe(url: str) -> tuple[str, int | str]:
        req = urllib.request.Request(
            url, method="GET", headers={"User-Agent": "the-listening-atlas link check"}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return url, int(resp.status)
        except urllib.error.HTTPError as exc:
            return url, exc.code
        except Exception as exc:
            return url, type(exc).__name__

    out: list[Finding] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for url, status in pool.map(probe, sorted(urls)):
            if status != 200:
                out.append(Finding(WARNING, "LINK-UNREACHABLE", f"{url} → {status}", urls[url]))
    return out


def run(root: Path, *, online: bool = False) -> Report:
    data_dir = root / "data"
    findings = check_schemas(data_dir, root / "schemas")
    atlas = load_atlas(data_dir)
    findings += check_atlas(atlas)
    if online:
        findings += check_links_online(atlas)
    order = {ERROR: 0, WARNING: 1, INFO: 2}
    findings.sort(key=lambda x: (order[x.level], x.code, x.where, x.message))
    return Report(findings)
