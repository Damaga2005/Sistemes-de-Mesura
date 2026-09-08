"""Migraciones SQLite forward-only por fichero (PRAGMA user_version)."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from app import paths as _paths

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
TARGETS: dict[str, int] = {
    "student": 1, "questions": 1, "exam_sessions": 1, "knowledge": 1,
}
_NAME_RE = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")

_DB_FILES = {
    "student": lambda: _paths.data_dir() / "student.sqlite",
    "questions": lambda: _paths.data_dir() / "questions.sqlite",
    "exam_sessions": lambda: _paths.data_dir() / "exam_sessions.sqlite",
    "knowledge": lambda: _paths.package_dir() / "data" / "processed" / "knowledge.sqlite",
}


def _scripts(db_name: str) -> list[tuple[int, Path]]:
    d = MIGRATIONS_DIR / db_name
    if not d.is_dir():
        return []
    found: list[tuple[int, Path]] = []
    for p in sorted(d.iterdir()):
        m = _NAME_RE.match(p.name)
        if not m:
            raise RuntimeError("nombre de migracion invalido: %s" % p.name)
        found.append((int(m.group(1)), p))
    for i, (num, p) in enumerate(found, start=1):
        if num != i:
            raise RuntimeError(
                "gap/duplicado en la secuencia de %s: se esperaba %03d, hay %s"
                % (db_name, i, p.name))
    return found


def migrate(con: sqlite3.Connection, db_name: str) -> int:
    target = TARGETS[db_name]                      # KeyError si desconocido
    current = con.execute("PRAGMA user_version").fetchone()[0]
    if current > target:
        raise RuntimeError(
            "%s: user_version %d es newer que el objetivo %d "
            "(snapshot de codigo mas reciente)" % (db_name, current, target))
    for num, path in _scripts(db_name):
        if num <= current:
            continue
        sql = path.read_text(encoding="utf-8")
        # cada migracion en su propia transaccion: el bump de user_version
        # confirma junto con las sentencias del script y revierte con ellas.
        try:
            con.executescript(
                "BEGIN;\n" + sql + "\nPRAGMA user_version = %d;\nCOMMIT;" % num)
        except Exception:
            con.rollback()
            raise
        current = num
    if current < target:                           # marcador sin script (001)
        con.execute("PRAGMA user_version = %d" % target)
        current = target
    return current


def status() -> dict[str, tuple[int, int]]:
    out: dict[str, tuple[int, int]] = {}
    for name, locate in _DB_FILES.items():
        p = locate()
        if not p.is_file():
            continue
        con = sqlite3.connect(p)
        try:
            cur = con.execute("PRAGMA user_version").fetchone()[0]
        finally:
            con.close()
        out[name] = (cur, TARGETS[name])
    return out
