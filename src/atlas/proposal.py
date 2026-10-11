"""Editorial proposals: a complete replacement sequence for one stage, checked and applied explicitly.

A proposal is never applied implicitly. ``check`` reports what is missing; ``apply`` refuses to run until
every new selection has a recording, an exact Apple title/credits and a song ID — nothing is guessed.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from . import yamlio
from .model import Atlas, Collection

REQUIRED_FOR_APPLY = ("title", "credits", "recording")


def new_selection_id(proposal_id: str, n: int) -> str:
    digest = hashlib.sha256(f"proposal/{proposal_id}/{n}".encode()).digest()
    return "s-" + base64.b32encode(digest).decode().lower()[:7]


@dataclass
class ProposalCheck:
    proposal_id: str
    stage: str
    status: str
    errors: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    kept: int = 0
    new: int = 0
    retire: int = 0
    current_count: int = 0
    resulting_count: int = 0
    playlist_before: int = 0
    playlist_after: int = 0

    @property
    def ready(self) -> bool:
        return not self.errors and not self.pending

    def markdown(self) -> list[str]:
        out = [
            f"### Proposal `{self.proposal_id}` → stage `{self.stage}` ({self.status})",
            "",
            f"- Stage now: {self.current_count} selections → proposed: {self.resulting_count} "
            f"({self.kept} kept, {self.new} new, {self.retire} retired)",
            f"- Whole playlist: {self.playlist_before} → {self.playlist_after}",
            f"- Ready to apply: **{'yes' if self.ready else 'no'}**",
        ]
        if self.errors:
            out += ["", "Errors:", *[f"- {e}" for e in self.errors]]
        if self.pending:
            out += ["", "Pending before it can be applied:", *[f"- {p}" for p in self.pending]]
        if self.notes:
            out += ["", "Editorial notes:", *[f"- {n}" for n in self.notes]]
        return out


def check_proposal(atlas: Atlas, c: Collection, doc: dict[str, Any]) -> ProposalCheck:
    pid, stage_id = str(doc.get("id")), str(doc.get("stage"))
    res = ProposalCheck(pid, stage_id, str(doc.get("status", "proposed")))
    try:
        st = c.stage(stage_id)
    except KeyError:
        res.errors.append(f"stage {stage_id!r} does not exist")
        return res
    by_id = {s.id: s for s in c.selections()}
    current_ids = [s.id for s in st.selections]
    retire_ids = [str(r.get("selection")) for r in doc.get("retire", []) or []]
    new_work_ids = {str(w.get("id")) for w in doc.get("new_works", []) or []}
    seq = doc.get("sequence", []) or []

    res.current_count = len(current_ids)
    res.resulting_count = len(seq)
    res.playlist_before = len(by_id)
    res.playlist_after = len(by_id) - len(current_ids) + len(seq)
    res.retire = len(retire_ids)

    for i, item in enumerate(seq, start=1):
        if item.get("n") != i:
            res.errors.append(f"sequence item {i} is numbered {item.get('n')}")
    used: list[str] = []
    for item in seq:
        n = item.get("n")
        if "existing" in item:
            sid = str(item["existing"])
            res.kept += 1
            used.append(sid)
            if sid not in by_id:
                res.errors.append(f"#{n}: selection {sid} does not exist")
            elif by_id[sid].stage != stage_id:
                res.errors.append(f"#{n}: {sid} currently belongs to stage {by_id[sid].stage!r}")
            if sid in retire_ids:
                res.errors.append(f"#{n}: {sid} is both kept and retired")
        else:
            res.new += 1
            new = item.get("new") or {}
            label = f"#{n} {new.get('work')} {new.get('movement') or ''}".strip()
            if new.get("work") not in atlas.works and new.get("work") not in new_work_ids:
                res.errors.append(f"{label}: unknown work {new.get('work')!r}")
            missing = [k for k in REQUIRED_FOR_APPLY if not new.get(k)]
            if new.get("recording") and new["recording"] not in atlas.recordings:
                missing.append(f"recording {new['recording']!r} in recordings.yaml")
            am = new.get("apple_music") or {}
            if not am.get("song_id"):
                missing.append("apple_music.song_id")
            if not am.get("url"):
                missing.append("apple_music.url")
            if missing:
                res.pending.append(f"{label} ({new.get('performers', '')}): needs {', '.join(missing)}")
            elif new.get("verification") == "user_supplied":
                res.pending.append(
                    f"{label}: song ID is user-supplied; set verification: verified once confirmed"
                )
    # Invariant: each recording at most once per playlist.
    remaining_songs = {s.song_id: s.id for s in by_id.values() if s.song_id and s.id not in retire_ids}
    for item in seq:
        song = ((item.get("new") or {}).get("apple_music") or {}).get("song_id")
        if song and song in remaining_songs:
            res.errors.append(
                f"#{item.get('n')}: Apple song {song} is already in the playlist as "
                f"{remaining_songs[song]}; each recording may appear only once"
            )
        elif song:
            remaining_songs[song] = f"proposal #{item.get('n')}"
    dropped = [sid for sid in current_ids if sid not in used and sid not in retire_ids]
    for sid in dropped:
        res.errors.append(f"{sid} ({by_id[sid].title}) would be dropped without a `retire` entry")
    for sid in retire_ids:
        if sid not in current_ids:
            res.errors.append(f"retire: {sid} is not in stage {stage_id!r}")
        elif sid in c.deep_focus:
            res.notes.append(
                f"{sid} ({by_id[sid].title}) has a close-listening study. Applying keeps it with the retired "
                "record; copy it to the replacement in notes/deep-focus.yaml if it still applies."
            )
    mx = doc.get("max_selections") or st.constraints.get("max_selections")
    if mx and len(seq) > mx:
        res.errors.append(f"sequence has {len(seq)} selections; maximum is {mx}")
    return res


def apply_proposal(
    root: Path,
    atlas: Atlas,
    c: Collection,
    proposal_path: Path,
    *,
    today: date | None = None,
    write: bool = False,
) -> tuple[ProposalCheck, dict[Path, Any]]:
    """Return the files that applying would write. Writes them only when ``write`` is true and the check passes."""
    doc = yamlio.load(proposal_path)
    res = check_proposal(atlas, c, doc)
    if not res.ready:
        return res, {}
    today = today or date.today()
    st = c.stage(res.stage)
    by_id = {s.id: s for s in st.selections}
    stage_file = c.path / st.selections[0].file

    new_selections = []
    for item in doc["sequence"]:
        if "existing" in item:
            new_selections.append(by_id[item["existing"]].raw)
            continue
        n = item["new"]
        sel: dict[str, Any] = {
            "id": new_selection_id(res.proposal_id, item["n"]),
            "work": n["work"],
            "movement": n.get("movement"),
        }
        if n.get("arrangement"):
            sel["arrangement"] = n["arrangement"]
        sel |= {
            "recording": n["recording"],
            "title": n["title"],
            "credits": n["credits"],
            "duration": n.get("duration"),
            "apple_music": {
                "song_id": n["apple_music"]["song_id"],
                "url": n["apple_music"]["url"],
                "album_url": n["apple_music"].get("album_url"),
            },
            "status": "keep",
            "verification": n.get("verification", "needs_verification"),
        }
        if n.get("note"):
            sel["editorial_note"] = n["note"]
        new_selections.append(sel)

    retired_doc = yamlio.load(c.path / "retired.yaml") or {"retired": []}
    deep_path = c.path / "notes" / "deep-focus.yaml"
    deep_doc = yamlio.load(deep_path)
    for r in doc.get("retire", []) or []:
        entry: dict[str, Any] = {
            "selection": by_id[r["selection"]].raw,
            "former_stage": res.stage,
            "retired_on": today.isoformat(),
            "reason": r["reason"],
            "proposal": res.proposal_id,
        }
        if r["selection"] in deep_doc["deep_focus"]:
            entry["deep_focus"] = deep_doc["deep_focus"].pop(r["selection"])
        retired_doc["retired"].append(entry)

    works_path = root / "data" / "works" / "bach.yaml"
    works_doc = yamlio.load(works_path)
    have = {w["id"] for w in works_doc["works"]}
    works_doc["works"] += [w for w in doc.get("new_works", []) or [] if w["id"] not in have]

    doc["status"] = "applied"
    files: dict[Path, Any] = {
        stage_file: {"stage": res.stage, "selections": new_selections},
        c.path / "retired.yaml": retired_doc,
        deep_path: deep_doc,
        works_path: works_doc,
        proposal_path: doc,
    }
    if write:
        for path, data in files.items():
            header = _existing_header(path)
            yamlio.dump(data, path, header=header)
    return res, files


def _existing_header(path: Path) -> str | None:
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            break
        lines.append(line[2:] if line.startswith("# ") else "")
    return "\n".join(lines) or None
