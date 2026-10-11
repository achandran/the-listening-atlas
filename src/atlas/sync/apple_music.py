"""Apple Music synchronisation — PHASE TWO DESIGN, NOT ACTIVE BY DEFAULT.

What this module does today
* ``plan``: compares the canonical playlist (exact Apple *song IDs* only) with a list of song IDs from an
  existing playlist and explains additions, removals, order changes and unmatched selections. Pure; no network.
* ``AppleMusicClient``: a thin, read-mostly client. Credentials come only from environment variables.

Known Apple Music API limits (as documented for the library playlist endpoints)
* A library playlist can be created, and tracks can be appended to it.
* There is no endpoint to remove tracks from, or reorder tracks within, an existing library playlist.
Therefore a plan that needs removals or reordering cannot be applied in place; the only automatic option is
to create a *new* playlist. This module never modifies an existing playlist.

Nothing in this file has been exercised against the live API in this repository. Treat it as a reviewed
design with tests for the planning logic, not as a working integration.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from ..model import Collection

API = "https://api.music.apple.com"
ENV_DEVELOPER_TOKEN = "APPLE_MUSIC_DEVELOPER_TOKEN"
ENV_USER_TOKEN = "APPLE_MUSIC_USER_TOKEN"
ENV_STOREFRONT = "APPLE_MUSIC_STOREFRONT"
ENV_ENABLE = "ATLAS_ENABLE_APPLE_SYNC"


class SyncDisabled(RuntimeError):
    pass


@dataclass
class SyncPlan:
    desired: list[str]
    current: list[str]
    unresolved: list[tuple[str, str]]  # (selection id, title) with no exact song ID
    to_add: list[str] = field(default_factory=list)
    to_remove: list[str] = field(default_factory=list)
    moved: list[str] = field(default_factory=list)
    duplicates_in_current: list[str] = field(default_factory=list)
    duplicates_in_desired: list[str] = field(default_factory=list)

    @property
    def in_sync(self) -> bool:
        return self.desired == self.current and not self.unresolved

    @property
    def append_only(self) -> bool:
        """True if the current playlist is an exact prefix of the desired one (appending would suffice)."""
        return self.current == self.desired[: len(self.current)]

    @property
    def feasible_in_place(self) -> bool:
        return self.append_only and not self.duplicates_in_current

    def summary(self) -> str:
        lines = [
            f"Desired tracks with exact song IDs: {len(self.desired)}",
            f"Current playlist tracks:            {len(self.current)}",
            f"Unresolved selections (excluded):   {len(self.unresolved)}",
            f"To add:    {len(self.to_add)}",
            f"To remove: {len(self.to_remove)}",
            f"Moved (order differs): {len(self.moved)}",
        ]
        if self.duplicates_in_current:
            lines.append(f"Duplicates in current playlist: {len(self.duplicates_in_current)}")
        if self.duplicates_in_desired:
            lines.append(f"Duplicates in canonical playlist: {len(self.duplicates_in_desired)}")
        if self.in_sync:
            lines.append("Result: already in sync.")
        elif self.desired == self.current:
            lines.append(
                f"Result: every matched track is in place and in order; {len(self.unresolved)} selections cannot "
                "be synced until their exact song IDs are resolved."
            )
        elif self.feasible_in_place:
            lines.append(
                "Result: could be applied by appending tracks to the existing playlist (not automated)."
            )
        else:
            lines.append(
                "Result: cannot be applied in place — Apple Music's API cannot remove or reorder tracks in an "
                "existing playlist. Options: create a new playlist (`atlas sync apply --create-new`), or edit the "
                "live playlist by hand using this plan."
            )
        return "\n".join(lines)


def desired_song_ids(c: Collection) -> tuple[list[str], list[tuple[str, str]]]:
    ids, unresolved = [], []
    for s in c.selections():
        if s.song_id and s.verification in ("verified", "snapshot_matched", "user_supplied"):
            ids.append(s.song_id)
        else:
            unresolved.append((s.id, s.title))
    return ids, unresolved


def _lcs(a: list[str], b: list[str]) -> set[int]:
    """Indices into ``b`` that form a longest common subsequence with ``a``."""
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            dp[i][j] = dp[i + 1][j + 1] + 1 if a[i] == b[j] else max(dp[i + 1][j], dp[i][j + 1])
    keep, i, j = set(), 0, 0
    while i < n and j < m:
        if a[i] == b[j]:
            keep.add(j)
            i, j = i + 1, j + 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            i += 1
        else:
            j += 1
    return keep


def plan(desired: list[str], current: list[str], unresolved: list[tuple[str, str]] | None = None) -> SyncPlan:
    p = SyncPlan(list(desired), list(current), list(unresolved or []))
    dset, cset = set(desired), set(current)
    p.to_add = [x for x in desired if x not in cset]
    p.to_remove = [x for x in current if x not in dset]
    seen: set[str] = set()
    p.duplicates_in_current = sorted({x for x in current if x in seen or seen.add(x)})  # type: ignore[func-returns-value]
    seen = set()
    p.duplicates_in_desired = sorted({x for x in desired if x in seen or seen.add(x)})  # type: ignore[func-returns-value]
    common_desired = [x for x in desired if x in cset]
    common_current = [x for x in current if x in dset]
    keep = _lcs(common_current, common_desired)
    p.moved = [x for j, x in enumerate(common_desired) if j not in keep]
    return p


# ------------------------------------------------------------------------------------------- client


def _require_enabled() -> None:
    if os.environ.get(ENV_ENABLE) != "1":
        raise SyncDisabled(
            f"Apple Music sync is disabled. Set {ENV_ENABLE}=1 to enable network access (see docs/apple-music-sync.md)."
        )


@dataclass
class AppleMusicClient:
    developer_token: str
    user_token: str | None
    storefront: str = "us"

    @classmethod
    def from_env(cls, need_user: bool) -> AppleMusicClient:
        _require_enabled()
        dev = os.environ.get(ENV_DEVELOPER_TOKEN)
        user = os.environ.get(ENV_USER_TOKEN)
        if not dev:
            raise SyncDisabled(f"{ENV_DEVELOPER_TOKEN} is not set")
        if need_user and not user:
            raise SyncDisabled(f"{ENV_USER_TOKEN} is not set (required for library access)")
        return cls(dev, user, os.environ.get(ENV_STOREFRONT, "us"))

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.developer_token}", "Content-Type": "application/json"}
        if self.user_token:
            headers["Music-User-Token"] = self.user_token
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(API + path, data=data, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
        return json.loads(raw) if raw else {}

    def catalog_playlist_song_ids(self, playlist_id: str) -> list[str]:
        """Read-only: song IDs of a public catalog/shared playlist (e.g. pl.u-…)."""
        path = f"/v1/catalog/{self.storefront}/playlists/{urllib.parse.quote(playlist_id)}/tracks?limit=100"
        return self._paginate(path, library=False)

    def library_playlist_song_ids(self, library_playlist_id: str) -> list[str]:
        """Read-only: catalog song IDs of a playlist in the user's library (p.…)."""
        path = f"/v1/me/library/playlists/{urllib.parse.quote(library_playlist_id)}/tracks?limit=100"
        return self._paginate(path, library=True)

    def _paginate(self, path: str, library: bool) -> list[str]:
        out: list[str] = []
        next_path: str | None = path
        while next_path:
            page = self._request("GET", next_path)
            for item in page.get("data", []):
                if library:
                    cid = (item.get("attributes", {}).get("playParams") or {}).get("catalogId")
                    out.append(str(cid) if cid else f"library:{item.get('id')}")
                else:
                    out.append(str(item.get("id")))
            next_path = page.get("next")
        return out

    def create_playlist(self, name: str, description: str, song_ids: list[str]) -> str:
        """Create a NEW library playlist. Never touches existing playlists."""
        body = {
            "attributes": {"name": name, "description": description},
            "relationships": {"tracks": {"data": [{"id": sid, "type": "songs"} for sid in song_ids]}},
        }
        res = self._request("POST", "/v1/me/library/playlists", body)
        return str(res["data"][0]["id"])
