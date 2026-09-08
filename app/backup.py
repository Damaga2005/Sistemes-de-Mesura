"""Copia de seguridad y restauracion de las SQLite escribibles (stdlib)."""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app import migrate as _migrate
from app import paths as _paths

WRITABLE_DBS = ("student.sqlite", "questions.sqlite", "exam_sessions.sqlite")
_DB_MIGRATE_NAME = {
    "student.sqlite": "student",
    "questions.sqlite": "questions",
    "exam_sessions.sqlite": "exam_sessions",
}


def _app_version() -> str:
    txt = (_paths.package_dir() / "pyproject.toml").read_text(encoding="utf-8")
    for line in txt.splitlines():
        if line.strip().startswith("version"):
            return line.split("=", 1)[1].strip().strip('"')
    return "0.0.0"


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _user_version(p: Path) -> int:
    con = sqlite3.connect(p)
    try:
        return con.execute("PRAGMA user_version").fetchone()[0]
    finally:
        con.close()


def _online_copy(src: Path, dst: Path) -> None:
    src_con = sqlite3.connect(src)
    dst_con = sqlite3.connect(dst)
    try:
        with dst_con:
            src_con.backup(dst_con)
    finally:
        src_con.close()
        dst_con.close()


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def make_backup(out_dir: Path | None = None) -> Path:
    root = Path(out_dir) if out_dir else _paths.backup_dir()
    root.mkdir(parents=True, exist_ok=True)
    ts = _timestamp()
    snap = root / ts
    # ponytail: two make_backup() calls in the same second collide on the
    # timestamp dir; disambiguate with a counter suffix. Sub-second timestamps
    # if this ever needs to be sortable to the millisecond.
    n = 1
    while True:
        try:
            snap.mkdir(exist_ok=False)
            break
        except FileExistsError:
            snap = root / ("%s-%d" % (ts, n))
            n += 1
    files = []
    for name in WRITABLE_DBS:
        src = _paths.data_dir() / name
        if not src.is_file():
            continue
        dst = snap / name
        _online_copy(src, dst)
        files.append({"name": name, "bytes": dst.stat().st_size,
                      "sha256": _sha256(dst), "user_version": _user_version(dst)})
    (snap / "manifest.json").write_text(json.dumps(
        {"timestamp": snap.name, "app_version": _app_version(), "files": files},
        indent=2), encoding="utf-8")
    return snap


def list_backups() -> list[dict]:
    root = _paths.backup_dir()
    if not root.is_dir():
        return []
    out = []
    for d in sorted(root.iterdir(), reverse=True):
        m = d / "manifest.json"
        if d.is_dir() and m.is_file():
            data = json.loads(m.read_text(encoding="utf-8"))
            data["path"] = str(d)
            out.append(data)
    return out


def restore(timestamp: str) -> Path:
    snap = _paths.backup_dir() / timestamp
    if not (snap / "manifest.json").is_file():
        raise FileNotFoundError("snapshot inexistente: %s" % timestamp)
    for name in WRITABLE_DBS:
        f = snap / name
        if not f.is_file():
            continue
        target = _migrate.TARGETS[_DB_MIGRATE_NAME[name]]
        if _user_version(f) > target:
            raise RuntimeError(
                "%s en el snapshot tiene user_version newer que %d" % (name, target))
    pre = make_backup(_paths.backup_dir())
    pre = pre.rename(pre.with_name(pre.name + "-pre-restore"))
    for name in WRITABLE_DBS:
        f = snap / name
        if f.is_file():
            shutil.copyfile(f, _paths.data_dir() / name)
    return pre
