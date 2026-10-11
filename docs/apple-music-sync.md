# Apple Music synchronisation (phase two — designed, not active)

**Status:** The planning logic is implemented and tested. The network client exists, but it is **disabled by
default and has not been run against the live Apple Music API**. Nothing in this repository has ever
modified the live playlist, and nothing will without explicit approval.

## What the API allows

The Apple Music API's library-playlist endpoints let an authorised app:

- read a user's library playlists and their tracks,
- create a new library playlist (optionally with tracks), and
- append tracks to a library playlist.

As documented, they do **not** provide endpoints to remove tracks from a playlist or to reorder them.
Consequences:

- A plan that only appends tracks to the end could be applied to an existing playlist.
- A plan that removes, replaces or reorders tracks (for example the Breath reconciliation, or moving a
  prelude) **cannot be applied in place**. The options are to create a new playlist, or to edit the live
  playlist by hand following the plan.

`atlas sync` therefore only ever **creates a new playlist**. It never edits an existing one. Re-check
Apple's current documentation before relying on any of this.

## Commands

```sh
# Offline plan: compare canonical order with a list of song IDs (one per line).
uv run atlas sync plan --current current-ids.txt --json plan.json

# Read-only plans that use the network (need ATLAS_ENABLE_APPLE_SYNC=1 and tokens):
uv run atlas sync plan --from-catalog pl.u-kv9lRpvs7v0a9Yb      # public playlist; developer token only
uv run atlas sync plan --from-library p.XXXXXXXX                 # your library playlist; + user token

# Create a NEW library playlist (never modifies an existing one):
uv run atlas sync apply --create-new "Bach: Cantabile & Harmony (draft)" \
    --confirm "CREATE Bach: Cantabile & Harmony (draft)"
```

The plan reports tracks to add, tracks to remove, tracks whose order differs, duplicates on either side, and
selections excluded because they have no exact song ID. Matching uses **exact Apple song IDs only**; it never
matches by title.

## Safety design

| Guard | Behaviour |
|---|---|
| Disabled by default | Any network call requires `ATLAS_ENABLE_APPLE_SYNC=1`. |
| Credentials | Read only from `APPLE_MUSIC_DEVELOPER_TOKEN` and `APPLE_MUSIC_USER_TOKEN` (optional `APPLE_MUSIC_STOREFRONT`). Never from files in the repo; `.env` and `*.p8` are git-ignored. |
| Dry run first | `sync plan` makes no changes. |
| Unresolved items | `apply` refuses while any selection lacks a song ID, unless `--skip-unresolved` is given. |
| Typed confirmation | `apply` requires `--confirm "CREATE <name>"`, matching exactly. |
| No destructive operations | No remove/reorder/overwrite code paths exist. |

## Getting tokens (when you decide to activate it)

1. An Apple Developer account with a MusicKit identifier and private key (`.p8`). Keep the key outside the
   repository.
2. Generate a developer token (a signed JWT) from that key.
3. Obtain a Music User Token by authorising with MusicKit JS or a native MusicKit app as the playlist owner.
4. Export the tokens in your shell only for the session in which you run the command.

## Before the first real run

- Resolve all `needs_verification` selections (`uv run atlas validate --strict` must pass), or accept a
  playlist without them.
- Run `sync plan` against the live playlist and review it with the editor.
- Create the new playlist under a clearly draft name, compare it, and only then decide what to do with the
  original by hand.
