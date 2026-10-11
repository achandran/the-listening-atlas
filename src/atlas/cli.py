"""`atlas` command-line interface. Run `uv run atlas --help`."""

from __future__ import annotations

import argparse
import contextlib
import functools
import http.server
import json
import secrets
import sys
from pathlib import Path

from . import yamlio
from .model import Atlas, Collection, load_atlas

EXPORT_FORMATS = ("all", "csv", "legacy", "song-ids", "report")


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


def cmd_migrate(args: argparse.Namespace) -> int:
    from . import migrate

    root = find_root()
    if (root / "data" / "atlas.yaml").exists() and not args.force:
        print(
            "data/ already exists. After migration the YAML is hand-edited; --force would overwrite those edits."
        )
        return 1
    written = migrate.write(root, migrate.migrate(root))
    print(f"wrote {len(written)} files under data/")
    return 0


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
        if args.format == "csv":
            files = [f for f in files if f.path.name == "playlist-full.csv" or f.path.parent.name == "stages"]
        elif args.format == "legacy":
            files = [f for f in files if f.path.name.startswith("legacy-")]
        elif args.format == "song-ids":
            files = [f for f in files if f.path.suffix == ".txt"]
        elif args.format == "report":
            files = [f for f in files if f.path.name == "match-report.md"]
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


def cmd_audit(args: argparse.Namespace) -> int:
    from . import audit

    root = find_root()
    atlas = _atlas()
    if args.check:
        stale = []
        for c in atlas.collections:
            d = root / "reports" / c.id
            for name, text in (
                ("migration-report.md", audit.migration_report(root, atlas, c)),
                ("editorial-discrepancies.md", audit.editorial_report(root, atlas, c)),
            ):
                path = d / name
                if not path.exists() or path.read_text(encoding="utf-8") != text:
                    stale.append(path)
        for p in stale:
            print(f"out of date: {p.relative_to(root)}")
        if stale:
            print("Run `uv run atlas audit` and commit the regenerated reports.")
            return 1
        print("reports are up to date")
        return 0
    for p in audit.write_reports(root, atlas):
        print(p.relative_to(root))
    return 0


def cmd_proposal(args: argparse.Namespace) -> int:
    from .proposal import apply_proposal, check_proposal

    root = find_root()
    atlas = _atlas()
    c = atlas.collection(args.collection) if args.collection else atlas.collections[0]
    path = c.path / "proposals" / f"{args.name}.yaml"
    if not path.exists():
        print(f"no proposal at {path.relative_to(root)}")
        return 1
    if args.action == "check":
        res = check_proposal(atlas, c, yamlio.load(path))
        print("\n".join(res.markdown()))
        return 0 if not res.errors else 1
    res, files = apply_proposal(root, atlas, c, path, write=args.write)
    print("\n".join(res.markdown()))
    if not res.ready:
        print("\nNot applied: resolve the items above first.")
        return 1
    verb = "wrote" if args.write else "would write"
    for p in files:
        print(f"{verb} {p.relative_to(root)}")
    if not args.write:
        print("\nDry run. Re-run with --write to apply, then `atlas validate` and `atlas audit`.")
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


def cmd_sync(args: argparse.Namespace) -> int:
    from .sync import apple_music as am

    atlas = _atlas()
    c = atlas.collection(args.collection) if args.collection else atlas.collections[0]
    desired, unresolved = am.desired_song_ids(c)
    try:
        if args.action == "plan":
            if args.current:
                current = [
                    line.strip() for line in Path(args.current).read_text().splitlines() if line.strip()
                ]
            elif args.from_catalog:
                current = am.AppleMusicClient.from_env(need_user=False).catalog_playlist_song_ids(
                    args.from_catalog
                )
            elif args.from_library:
                current = am.AppleMusicClient.from_env(need_user=True).library_playlist_song_ids(
                    args.from_library
                )
            else:
                current = []
                print("(no current playlist given: planning against an empty playlist)\n")
            p = am.plan(desired, current, unresolved)
            print(p.summary())
            if args.json:
                Path(args.json).write_text(
                    json.dumps(
                        {
                            "to_add": p.to_add,
                            "to_remove": p.to_remove,
                            "moved": p.moved,
                            "unresolved": [{"selection": s, "title": t} for s, t in p.unresolved],
                        },
                        indent=2,
                        ensure_ascii=False,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                print(f"\nplan written to {args.json}")
            return 0
        # apply: only ever creates a NEW playlist.
        if unresolved and not args.skip_unresolved:
            print(
                f"{len(unresolved)} selections have no exact song ID. Resolve them, or pass --skip-unresolved to "
                "create a playlist that omits them."
            )
            return 1
        expected = f"CREATE {args.create_new}"
        if args.confirm != expected:
            print(
                f"Refusing to call Apple Music. To create a new library playlist with {len(desired)} tracks, re-run "
                f'with --confirm "{expected}". No existing playlist is modified.'
            )
            return 1
        client = am.AppleMusicClient.from_env(need_user=True)
        pid = client.create_playlist(
            args.create_new, f"{c.title} — generated by The Listening Atlas", desired
        )
        print(f"created library playlist {pid} with {len(desired)} tracks")
        return 0
    except am.SyncDisabled as exc:
        print(exc)
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

    p = sub.add_parser("export", help="write CSV/text exports (deterministic)")
    p.add_argument("--format", choices=EXPORT_FORMATS, default="all")
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

    p = sub.add_parser("audit", help="regenerate migration and editorial reports under reports/")
    p.add_argument("--check", action="store_true", help="fail if committed reports are out of date")
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("proposal", help="check or apply an editorial proposal")
    p.add_argument("action", choices=("check", "apply"))
    p.add_argument("name", help="proposal file name without .yaml, e.g. breath-19")
    p.add_argument("--write", action="store_true", help="apply for real (default is a dry run)")
    p.add_argument("--collection")
    p.set_defaults(func=cmd_proposal)

    p = sub.add_parser("new-id", help="mint unused selection IDs for new selections")
    p.add_argument("-n", type=int, default=1)
    p.set_defaults(func=cmd_new_id)

    p = sub.add_parser("sync", help="Apple Music sync (phase two design; disabled by default)")
    p.add_argument("action", choices=("plan", "apply"))
    p.add_argument("--collection")
    p.add_argument("--current", help="file with one Apple song ID per line (current playlist order)")
    p.add_argument("--from-catalog", metavar="PLAYLIST_ID", help="read a public pl.… playlist (needs token)")
    p.add_argument("--from-library", metavar="PLAYLIST_ID", help="read a library p.… playlist (needs tokens)")
    p.add_argument("--json", help="write the plan as JSON")
    p.add_argument("--create-new", metavar="NAME", help="apply: name of the NEW library playlist to create")
    p.add_argument("--confirm", help='apply: must equal "CREATE <NAME>"')
    p.add_argument("--skip-unresolved", action="store_true")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("migrate", help="(one-time) import the archived handoff into data/")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_migrate)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "sync" and args.action == "apply" and not args.create_new:
        print("sync apply only supports --create-new NAME (existing playlists are never modified)")
        return 1
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
