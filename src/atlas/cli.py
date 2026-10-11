"""`atlas` command-line interface. Run `uv run atlas --help`."""

from __future__ import annotations

import argparse
import contextlib
import functools
import http.server
import secrets
import sys
from pathlib import Path

from .model import Atlas, Collection, load_atlas


def find_root(start: Path | None = None) -> Path:
    here = (start or Path.cwd()).resolve()
    for p in (here, *here.parents):
        if (p / "schemas").is_dir() and (p / "pyproject.toml").exists():
            return p
    return here


def _atlas() -> Atlas:
    return load_atlas(find_root() / "data")


def _collections(atlas: Atlas, cid: str | None) -> list[Collection]:
    return [atlas.collection(cid)] if cid else atlas.collections


# ------------------------------------------------------------------------------------------- commands


def cmd_validate(args: argparse.Namespace) -> int:
    from . import validate

    report = validate.run(find_root(), online=args.check_links)
    for f in report.findings:
        if args.verbose or f.level != "info":
            print(f.format())
    print(
        f"\n{len(report.errors)} errors, {len(report.warnings)} warnings, {len(report.by_level('info'))} info"
    )
    if report.ok(strict=args.strict):
        print("OK" + (" (strict)" if args.strict else ""))
        return 0
    return 1


def cmd_export(args: argparse.Namespace) -> int:
    from .export import build_exports, write_exports

    atlas = _atlas()
    out = Path(args.out)
    total = 0
    for c in _collections(atlas, args.collection):
        files = build_exports(atlas, c)
        for p in write_exports(files, out):
            print(p)
        total += len(files)
    print(f"{total} files written to {out}/")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    from .site import build_site

    atlas = _atlas()
    files = build_site(atlas, Path(args.out), base_url=args.base_url)
    print(f"built {len(files)} files into {args.out}/")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    directory = Path(args.dir)
    if not directory.exists():
        print(f"{directory}/ does not exist; run `atlas build` first")
        return 1
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as httpd:
        print(f"Serving {directory}/ at http://127.0.0.1:{args.port}/  (Ctrl-C to stop)")
        with contextlib.suppress(KeyboardInterrupt):
            httpd.serve_forever()
    return 0


def cmd_new_id(args: argparse.Namespace) -> int:
    atlas = _atlas()
    used = {s.id for c in atlas.collections for s in c.selections()}
    used |= {str((r.get("selection") or {}).get("id")) for c in atlas.collections for r in c.retired}
    alphabet = "abcdefghijklmnopqrstuvwxyz234567"
    for _ in range(args.n):
        while True:
            sid = "s-" + "".join(secrets.choice(alphabet) for _ in range(7))
            if sid not in used:
                used.add(sid)
                print(sid)
                break
    return 0


def cmd_music(args: argparse.Namespace) -> int:
    from . import music

    atlas = _atlas()
    c = atlas.collection(args.collection) if args.collection else atlas.collections[0]
    try:
        name = args.playlist or music.playlist_name(c)
        p = music.plan(name, c.selections(), music.read_playlist(name))
        print(p.summary())
        if args.action == "check":
            return 0 if p.in_sync else 1
        if not p.remove:
            return 0
        if not args.write:
            print(
                f"\nDry run. Re-run with --write to remove these {len(p.remove)} tracks from the playlist "
                "(they stay in the library)."
            )
            return 0
        removed, left = music.remove_tracks(name, p.remove)
        print(f"\nremoved {removed} tracks; the playlist now has {left}")
        return 0
    except music.MusicAppError as exc:
        print(f"Music app: {exc}")
        return 2


# ------------------------------------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atlas", description="The Listening Atlas — data, exports and website"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="validate canonical data (schemas, references, editorial rules)")
    p.add_argument(
        "--strict", action="store_true", help="treat warnings (e.g. unresolved song IDs) as errors"
    )
    p.add_argument(
        "--check-links", action="store_true", help="also fetch every Apple Music URL (network; slow)"
    )
    p.add_argument("-v", "--verbose", action="store_true", help="show info-level findings")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("export", help="write the student guide (Markdown, deterministic)")
    p.add_argument("--out", default="exports")
    p.add_argument("--collection")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("build", help="build the static website")
    p.add_argument("--out", default="_site")
    p.add_argument("--base-url", default="", help="absolute URL prefix used only for the 404 page")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("serve", help="preview the built website locally")
    p.add_argument("--dir", default="_site")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("new-id", help="mint unused selection IDs for new selections")
    p.add_argument("-n", type=int, default=1)
    p.set_defaults(func=cmd_new_id)

    p = sub.add_parser("music", help="compare the Music app playlist with the data (macOS); remove extras")
    p.add_argument("action", choices=("check", "apply"))
    p.add_argument("--collection")
    p.add_argument(
        "--playlist", help="Music app playlist name (default: library_playlist in collection.yaml)"
    )
    p.add_argument("--write", action="store_true", help="apply: remove extra tracks (default is a dry run)")
    p.set_defaults(func=cmd_music)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
