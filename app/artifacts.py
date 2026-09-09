"""Verificacion de integridad de artefactos empaquetados (stdlib)."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from app import migrate as _migrate
from app import paths as _paths
from app.env import parse_env

MANIFEST_NAME = "ARTIFACT-MANIFEST.json"

PACKAGED_ARTIFACTS: tuple[str, ...] = (
    "data/processed/knowledge.sqlite",
    "data/generated/questions.sqlite",
    "data/evaluation/eval.sqlite",
    "data/index",
    "data/source_manifest.json",
)

# label -> (db relpath, count query, expected). Numeros congelados en
# docs/PHASE_8_FINAL_CERTIFICATION.md (formulas 2896) y verificados contra
# los artefactos vivos en el momento de implementar la Task 6.
SENTINELS: dict[str, tuple[str, str, int]] = {
    "formulas": ("data/processed/knowledge.sqlite",
                 "SELECT COUNT(*) FROM formulas", 2896),
    "chunks": ("data/processed/knowledge.sqlite",
               "SELECT COUNT(*) FROM chunks", 1903),
    "documents": ("data/processed/knowledge.sqlite",
                  "SELECT COUNT(*) FROM documents", 71),
    "vf_questions": ("data/evaluation/eval.sqlite",
                     "SELECT COUNT(*) FROM questions", 500),
}

# ponytail: para knowledge basta con exigir `formulas`; la profundidad real
# (conteos por tabla) la cubren los SENTINELS. Subir el set si algun consumidor
# necesita garantias de esquema mas estrictas.
_EXPECTED_TABLES: dict[str, set[str]] = {
    "data/processed/knowledge.sqlite": {"formulas"},
    "data/generated/questions.sqlite": {"exams", "questions"},
    "data/evaluation/eval.sqlite": {"questions"},
}
_DB_MIGRATE_NAME = {
    "data/processed/knowledge.sqlite": "knowledge",
}


def _iter_files(relpath: str) -> list[str]:
    root = _paths.package_dir() / relpath
    if root.is_dir():
        return sorted(
            (p.relative_to(_paths.package_dir()).as_posix())
            for p in root.rglob("*") if p.is_file())
    return [relpath]


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _app_version() -> str:
    try:
        txt = (_paths.package_dir() / "pyproject.toml").read_text(encoding="utf-8")
    except OSError:
        return "0.0.0"
    for line in txt.splitlines():
        if line.strip().startswith("version"):
            return line.split("=", 1)[1].strip().strip('"')
    return "0.0.0"


def write_manifest() -> Path:
    files: dict[str, str] = {}
    for art in PACKAGED_ARTIFACTS:
        for rel in _iter_files(art):
            files[rel] = _sha256(_paths.package_dir() / rel)
    out = _paths.package_dir() / "data" / MANIFEST_NAME
    out.write_text(json.dumps(
        {"generated_for_version": _app_version(), "files": files},
        indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def _check_hashes() -> list[str]:
    mpath = _paths.package_dir() / "data" / MANIFEST_NAME
    if not mpath.is_file():
        return ["falta %s (ejecuta `sistemes check --write-manifest`)" % MANIFEST_NAME]
    manifest = json.loads(mpath.read_text(encoding="utf-8"))["files"]
    problems = []
    for rel, want in sorted(manifest.items()):
        p = _paths.package_dir() / rel
        if not p.is_file():
            problems.append("artefacto ausente: %s" % rel)
        elif _sha256(p) != want:
            problems.append("sha256 no coincide: %s" % rel)
    return problems


def _check_schema() -> list[str]:
    problems = []
    for rel, expected in _EXPECTED_TABLES.items():
        if rel not in PACKAGED_ARTIFACTS:
            continue
        p = _paths.package_dir() / rel
        if not p.is_file():
            problems.append("BD ausente: %s" % rel)
            continue
        con = sqlite3.connect(p)
        try:
            have = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            missing = expected - have
            if missing:
                problems.append("%s: faltan tablas %s" % (rel, sorted(missing)))
            mig_name = _DB_MIGRATE_NAME.get(rel)
            if mig_name is not None:
                cur = con.execute("PRAGMA user_version").fetchone()[0]
                tgt = _migrate.TARGETS[mig_name]
                if cur != tgt:
                    problems.append(
                        "user_version %s: %d != objetivo %d" % (rel, cur, tgt))
        finally:
            con.close()
    return problems


def _check_config() -> list[str]:
    problems = []
    envf = _paths.config_dir() / ".env"
    if envf.is_file():
        try:
            parse_env(envf.read_text(encoding="utf-8"))
        except Exception as exc:                       # noqa: BLE001
            problems.append(".env no parsea: %s" % exc)
    for p in (_paths.data_dir(), _paths.index_dir(), _paths.log_dir(),
              _paths.config_dir(), _paths.backup_dir()):
        if not p.is_dir():
            problems.append("directorio ausente: %s" % p)
            continue
        probe = p / ".writable_probe"
        try:
            probe.write_text("x", encoding="utf-8")
            probe.unlink()
        except OSError:
            problems.append("directorio no escribible: %s" % p)
    return problems


def _check_sentinels() -> list[str]:
    problems = []
    for label, (rel, query, expected) in SENTINELS.items():
        if expected == 0:
            continue                                   # centinela sin fijar
        p = _paths.package_dir() / rel
        if not p.is_file():
            problems.append("centinela %s: BD ausente %s" % (label, rel))
            continue
        con = sqlite3.connect("%s?mode=ro" % p.as_uri(), uri=True)
        try:
            got = con.execute(query).fetchone()[0]
        finally:
            con.close()
        if got != expected:
            problems.append("centinela %s: %d != %d" % (label, got, expected))
    return problems


def check(fast: bool = False, source: Path | None = None) -> list[str]:
    problems = _check_schema() + _check_config()
    if fast:
        return problems
    problems += _check_hashes() + _check_sentinels()
    if source is not None:
        from app.ingest import load_manifest, verify_sources
        errs = verify_sources(load_manifest(_paths.package_dir()), Path(source))
        problems += ["fuente: " + e for e in errs]
    return problems
