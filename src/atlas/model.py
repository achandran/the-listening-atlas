"""Loading canonical YAML into an in-memory atlas.

Loading is deliberately forgiving: structural problems are recorded as validation findings by
:mod:`atlas.validate` rather than raised here, so that one bad file does not hide every other problem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import yamlio


@dataclass
class Work:
    id: str
    catalogue: str
    title: str
    composer: str | None
    attribution_note: str | None = None


@dataclass
class Recording:
    id: str
    principal_artist: str
    album_title: str | None
    apple_album_id: str | None
    label: str | None
    release_year: int | None
    version: str | None
    verification: str
    notes: str | None = None
    sources: list[str] = field(default_factory=list)


@dataclass
class Selection:
    id: str
    work: str
    movement: str | None
    recording: str
    title: str
    credits: str
    duration: int | None
    song_id: str | None
    url: str | None
    album_url: str | None
    status: str
    verification: str
    raw: dict[str, Any]
    stage: str = ""
    file: str = ""
    index: int = 0  # 0-based index inside the stage file
    arrangement: str | None = None
    principal_artist: str | None = None
    album_as_listed: str | None = None
    duration_status: str | None = None
    link_kind: str | None = None
    editorial_note: str | None = None
    source_position: int | None = None

    @classmethod
    def from_yaml(cls, d: dict[str, Any], stage: str, file: str, index: int) -> Selection:
        am = d.get("apple_music") or {}
        src = d.get("source") or {}
        return cls(
            id=str(d.get("id", "")),
            work=str(d.get("work", "")),
            movement=d.get("movement"),
            recording=str(d.get("recording", "")),
            title=str(d.get("title", "")),
            credits=str(d.get("credits", "")),
            duration=d.get("duration"),
            song_id=am.get("song_id"),
            url=am.get("url"),
            album_url=am.get("album_url"),
            status=str(d.get("status", "")),
            verification=str(d.get("verification", "")),
            raw=d,
            stage=stage,
            file=file,
            index=index,
            arrangement=d.get("arrangement"),
            principal_artist=d.get("principal_artist"),
            album_as_listed=d.get("album_as_listed"),
            duration_status=d.get("duration_status"),
            link_kind=d.get("link_kind"),
            editorial_note=d.get("editorial_note"),
            source_position=src.get("position"),
        )


@dataclass
class Stage:
    id: str
    number: int
    name: str
    principle: str
    question: str
    direction: str
    at_the_piano: str
    itinerary: str
    itinerary_source: str | None = None
    editorial_notice: str | None = None
    constraints: dict[str, Any] = field(default_factory=dict)
    selections: list[Selection] = field(default_factory=list)


@dataclass
class Collection:
    id: str
    path: Path
    meta: dict[str, Any]
    stages: list[Stage]
    work_focus: dict[str, str]
    orphaned_notes: list[dict[str, Any]]
    deep_focus: dict[str, dict[str, Any]]
    issues: list[dict[str, Any]]
    retired: list[dict[str, Any]]
    load_errors: list[str] = field(default_factory=list)

    @property
    def title(self) -> str:
        return str(self.meta.get("title", self.id))

    def selections(self) -> list[Selection]:
        return [s for st in self.stages for s in st.selections]

    def positions(self) -> dict[str, int]:
        """1-based playlist position of every active selection (computed, never stored)."""
        return {s.id: i for i, s in enumerate(self.selections(), start=1)}

    def stage(self, stage_id: str) -> Stage:
        for st in self.stages:
            if st.id == stage_id:
                return st
        raise KeyError(stage_id)


@dataclass
class Atlas:
    root: Path
    meta: dict[str, Any]
    works: dict[str, Work]
    recordings: dict[str, Recording]
    collections: list[Collection]
    load_errors: list[str] = field(default_factory=list)
    duplicate_work_ids: list[str] = field(default_factory=list)
    duplicate_recording_ids: list[str] = field(default_factory=list)

    def collection(self, cid: str) -> Collection:
        for c in self.collections:
            if c.id == cid:
                return c
        raise KeyError(cid)


def _load(path: Path, errors: list[str]) -> Any:
    try:
        return yamlio.load(path)
    except FileNotFoundError:
        errors.append(f"{path}: file not found")
    except Exception as exc:  # YAML syntax errors etc.
        errors.append(f"{path}: cannot parse YAML: {exc}")
    return None


def load_atlas(data_dir: Path) -> Atlas:
    errors: list[str] = []
    meta = _load(data_dir / "atlas.yaml", errors) or {}

    works: dict[str, Work] = {}
    dup_works: list[str] = []
    for wf in sorted((data_dir / "works").glob("*.yaml")):
        for w in (_load(wf, errors) or {}).get("works", []) or []:
            if w.get("id") in works:
                dup_works.append(str(w.get("id")))
            works[str(w.get("id"))] = Work(
                id=str(w.get("id")),
                catalogue=str(w.get("catalogue", "")),
                title=str(w.get("title", "")),
                composer=w.get("composer"),
                attribution_note=w.get("attribution_note"),
            )

    recordings: dict[str, Recording] = {}
    dup_recs: list[str] = []
    for r in (_load(data_dir / "recordings.yaml", errors) or {}).get("recordings", []) or []:
        if r.get("id") in recordings:
            dup_recs.append(str(r.get("id")))
        recordings[str(r.get("id"))] = Recording(
            id=str(r.get("id")),
            principal_artist=str(r.get("principal_artist", "")),
            album_title=r.get("album_title"),
            apple_album_id=r.get("apple_album_id"),
            label=r.get("label"),
            release_year=r.get("release_year"),
            version=r.get("version"),
            verification=str(r.get("verification", "")),
            notes=r.get("notes"),
            sources=list(r.get("sources") or []),
        )

    collections = [load_collection(data_dir / "collections" / cid) for cid in meta.get("collections", [])]
    return Atlas(data_dir.parent, meta, works, recordings, collections, errors, dup_works, dup_recs)


def load_collection(cdir: Path) -> Collection:
    errors: list[str] = []
    meta = _load(cdir / "collection.yaml", errors) or {}
    stages_raw = (_load(cdir / "stages.yaml", errors) or {}).get("stages", []) or []
    stages: dict[str, Stage] = {}
    ordered: list[Stage] = []
    for s in stages_raw:
        st = Stage(
            id=str(s.get("id", "")),
            number=s.get("number"),
            name=str(s.get("name", "")),
            principle=str(s.get("principle", "")),
            question=str(s.get("question", "")),
            direction=str(s.get("direction", "")),
            at_the_piano=str(s.get("at_the_piano", "")),
            itinerary=str(s.get("itinerary", "")),
            itinerary_source=s.get("itinerary_source"),
            editorial_notice=s.get("editorial_notice"),
            constraints=dict(s.get("constraints") or {}),
        )
        stages[st.id] = st
        ordered.append(st)

    for rel in meta.get("stage_files", []) or []:
        data = _load(cdir / rel, errors)
        if not data:
            continue
        sid = str(data.get("stage", ""))
        if sid not in stages:
            errors.append(f"{cdir / rel}: stage {sid!r} is not defined in stages.yaml")
            continue
        for i, d in enumerate(data.get("selections", []) or []):
            stages[sid].selections.append(Selection.from_yaml(d, sid, rel, i))

    notes = _load(cdir / "notes" / "work-focus.yaml", errors) or {}
    deep = (_load(cdir / "notes" / "deep-focus.yaml", errors) or {}).get("deep_focus", {}) or {}
    issues = (_load(cdir / "issues.yaml", errors) or {}).get("issues", []) or []
    retired = (_load(cdir / "retired.yaml", errors) or {}).get("retired", []) or []
    return Collection(
        id=str(meta.get("id", cdir.name)),
        path=cdir,
        meta=meta,
        stages=ordered,
        work_focus=dict(notes.get("work_focus") or {}),
        orphaned_notes=list(notes.get("orphaned") or []),
        deep_focus=dict(deep),
        issues=list(issues),
        retired=list(retired),
        load_errors=errors,
    )
