"""CLI unica `sistemes`. Cada subcomando delega en codigo ya probado."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app import paths as _paths
from app.env import load_env


def _version() -> str:
    txt = (_paths.package_dir() / "pyproject.toml").read_text(encoding="utf-8")
    for line in txt.splitlines():
        if line.strip().startswith("version"):
            return line.split("=", 1)[1].strip().strip('"')
    return "0.0.0"


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="sistemes", description="Sistemes de Mesura")
    ap.add_argument("--version", action="store_true", help="imprime la version")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("init", help="crea directorios y .env inicial")
    p.add_argument("--force", action="store_true", help="reescribe el .env")

    p = sub.add_parser("serve", help="arranca el servidor web")
    p.add_argument("--host")
    p.add_argument("--port", type=int)
    p.add_argument("--data-dir")
    p.add_argument("--calendar")

    p = sub.add_parser("ingest", help="[mantenedor] regenera artefactos")
    p.add_argument("--source", required=True)
    p.add_argument("--out", default=None)

    p = sub.add_parser("check", help="verifica integridad de artefactos")
    p.add_argument("--json", action="store_true")
    p.add_argument("--fast", action="store_true")
    p.add_argument("--status", action="store_true")
    p.add_argument("--write-manifest", action="store_true")
    p.add_argument("--source", default=None)

    p = sub.add_parser("backup", help="copia de seguridad de las SQLite")
    p.add_argument("--out", default=None)
    p.add_argument("--list", action="store_true")

    p = sub.add_parser("restore", help="restaura desde un snapshot")
    p.add_argument("--from", dest="ts", required=True)
    return ap


def _cmd_init(args) -> int:
    made = _paths.ensure_dirs()
    envf = _paths.config_dir() / ".env"
    example = (_paths.package_dir() / ".env.example").read_text(encoding="utf-8")
    if args.force or not envf.is_file():
        envf.write_text(example, encoding="utf-8")
    print("init OK: " + ", ".join(str(p) for p in made))
    return 0


def _cmd_serve(args) -> int:
    from app import artifacts
    problems = artifacts.check(fast=True)
    if problems:
        print("serve abortado — check --fast fallo:", file=sys.stderr)
        for pb in problems:
            print("  - " + pb, file=sys.stderr)
        return 1
    from web import server as _web
    argv = []
    if args.host:
        argv += ["--host", args.host]
    if args.port:
        argv += ["--port", str(args.port)]
    if args.data_dir:
        argv += ["--data-dir", args.data_dir]
    if args.calendar:
        argv += ["--calendar", args.calendar]
    rc = _web.main(argv)
    return rc if isinstance(rc, int) else 0


def _cmd_ingest(args) -> int:
    out = Path(args.out) if args.out else _paths.package_dir() / "data"
    processed = out / "processed"
    try:
        processed.mkdir(parents=True, exist_ok=True)
        probe = processed / ".writable"
        probe.write_text("x", encoding="utf-8")
        probe.unlink()
    except OSError:
        print("ingest: destino no escribible; pasa --out DIR explicito",
              file=sys.stderr)
        return 2
    from app.ingest import run as ingest_run
    from app.build_index import main as build_index_main
    ingest_run(Path(args.source), processed, out / "evaluation",
               _paths.package_dir())
    build_index_main()
    print("ingest OK: " + str(out))
    return 0


def _cmd_check(args) -> int:
    from app import artifacts
    if args.status:
        from app.migrate import status
        for name, (cur, tgt) in sorted(status().items()):
            print("%-16s %d -> %d" % (name, cur, tgt))
        return 0
    if args.write_manifest:
        print("manifest: " + str(artifacts.write_manifest()))
        return 0
    problems = artifacts.check(
        fast=args.fast, source=Path(args.source) if args.source else None)
    if args.json:
        import json as _json
        print(_json.dumps({"ok": not problems, "problems": problems}))
    else:
        print("check OK" if not problems else "check FALLO:")
        for pb in problems:
            print("  - " + pb)
    return 0 if not problems else 1


def _cmd_backup(args) -> int:
    from app import backup
    if args.list:
        for b in backup.list_backups():
            print("%s  (%d ficheros)" % (b["timestamp"], len(b["files"])))
        return 0
    snap = backup.make_backup(Path(args.out) if args.out else None)
    print("backup OK: " + str(snap))
    return 0


def _cmd_restore(args) -> int:
    from app import backup
    pre = backup.restore(args.ts)
    print("restore OK (estado previo en %s)" % pre)
    return 0


_DISPATCH = {
    "init": _cmd_init, "serve": _cmd_serve, "ingest": _cmd_ingest,
    "check": _cmd_check, "backup": _cmd_backup, "restore": _cmd_restore,
}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    load_env()
    load_env(_paths.config_dir() / ".env")
    from app import logsetup
    logsetup.configure()
    ap = _build_parser()
    args = ap.parse_args(argv)
    if args.version:
        print(_version())
        return 0
    if not args.cmd:
        ap.print_help()
        return 2
    try:
        return _DISPATCH[args.cmd](args)
    except Exception:                              # noqa: BLE001
        logsetup.exception("subcomando fallo: %s" % args.cmd)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
