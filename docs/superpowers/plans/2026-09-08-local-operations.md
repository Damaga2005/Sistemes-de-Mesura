# Operación local — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the stdlib web tutor into a cleanly installable single-user local application: `.env` config, configurable directories, schema migrations, SQLite backup/restore, a unified `sistemes` CLI, artifact-integrity checks, structured logging, health check, request limits, CSRF, and a reproducible Windows install.

**Architecture:** New small stdlib-only modules under `app/` (`env.py`, `paths.py`, `migrate.py`, `backup.py`, `artifacts.py`, `logsetup.py`, `cli.py`). Existing hardcoded paths in `app/config.py`, `web/server.py`, `app/build_index.py` are replaced by `app.paths` resolvers. The four SQLite stores gain a forward-only `PRAGMA user_version` migration hook. The raw `BaseHTTPRequestHandler` server keeps its shape; CSRF, limits, health, and logging are added in place. Packaging stays a portable zip plus a venv bootstrap — no wheel-with-data, no runtime dependencies.

**Tech Stack:** Python 3.11+ stdlib only (`argparse`, `sqlite3`, `logging`, `http.server`, `pathlib`, `hashlib`, `json`, `shutil`, `secrets`, `http.cookies`). `pytest` for tests (dev-only). PowerShell for `scripts/*.ps1`.

## Global Constraints

- **Python:** `requires-python = ">=3.11,<3.15"`. Do not use syntax newer than 3.11.
- **Zero runtime dependencies:** `[project.dependencies]` stays `[]`. Only `pytest` may be added, under `[project.optional-dependencies] dev`.
- **stdlib only** in `app/` and `web/` runtime code. No new imports outside the standard library.
- **Determinism:** IDs and hashes deterministic; re-running any command produces the same result; no timestamps baked into content hashes.
- **No silent network:** nothing in these modules makes a network call.
- **Source material is immutable:** never write under the ingest source directory. Catalan course text is never translated.
- **Docs:** any new academic claim in a doc is tagged `confirmed | inferred | unknown`. (No academic claims are expected in this plan.)
- **Commits:** small, message in Spanish, prefixed with the block (`b1: ...` … `b7: ...`). End every commit message with:
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`
- **Green bar:** `pytest tests/` passes before any task is considered done. The domain suites for F0–F11 must not change behavior.
- **Working branch:** all work lands on `master` (project convention; history is linear).

---

## File Structure

**New (`app/`):**
- `app/env.py` — `.env` parser + `load_env()`. ~40 lines.
- `app/paths.py` — `SM_HOME` + the 5 configurable dirs + `package_dir()`. ~70 lines.
- `app/migrate.py` — `PRAGMA user_version` forward-only migrator + `status()`. ~90 lines.
- `app/migrations/<db_name>/NNN_*.sql` — migration scripts. `001_baseline` is a no-op marker (schema still lives in the stores; see Task 3).
- `app/backup.py` — online `.backup()` of the 3 writable DBs + restore + list. ~120 lines.
- `app/artifacts.py` — manifest generation + integrity `check()`. ~150 lines.
- `app/logsetup.py` — rotating file handlers for `serve.log` / `error.log`. ~50 lines.
- `app/cli.py` — `argparse` dispatcher: `init serve ingest check backup restore`. ~180 lines.

**Modified:**
- `app/config.py` — `DEFAULT_*` path constants become thin wrappers over `app.paths` (kept for back-compat imports).
- `web/server.py` — `DEMO_STUDENT` → `SM_STUDENT`; `KB`/`INDEX`/`GENDB` from `app.paths`; `main()` calls `load_env` + `logsetup.configure`; CSRF cookies + check; `Content-Length` / socket-timeout limits; `/api/health`; `check --fast` gate before `serve`.
- `app/build_index.py` — `WORKSPACE`/`KB`/`INDEX_DIR` from `app.paths`.
- `app/ingest.py` — `main()` gains `--out` and a non-writable-target guard (Task 5).
- `app/student/store.py`, `app/exam/store.py`, `app/examiner/store.py`, `app/store.py` — add `migrate(con, "<db_name>")` call right after the existing `executescript(SCHEMA)` in each constructor.
- `web/static/js/csrf.js` (new) + `<script>` tag in every `web/*.html` — shared `smFetch()` that attaches `X-CSRF-Token`.
- `pyproject.toml` — version `1.0.0`, `requires-python`, `sistemes` entry point, `dev` extra.
- `scripts/package.ps1` — read version from `pyproject.toml`, bundle `install.ps1`, emit `ARTIFACT-MANIFEST.json`.
- `scripts/install.ps1` (new) — venv + `pip install .`.
- `tests/test_packaging.py` — updated expectations.
- `.env.example` — all new keys.

**New docs:**
- `CHANGELOG.md`, `docs/RELEASE_CHECKLIST.md`, `docs/PHASE_14_PACKAGING.md` (rewrite at Task 9).

---

## Task 1: `.env` loader and path resolver

**Files:**
- Create: `app/env.py`
- Create: `app/paths.py`
- Test: `tests/test_env.py`, `tests/test_paths.py`

**Interfaces:**
- Produces:
  - `app.env.load_env(path: str | Path | None = None) -> dict[str, str]` — parses one `.env` file, sets each key into `os.environ` only if absent, returns the parsed dict (even for keys that were already present). Missing file → returns `{}`, no error.
  - `app.env.parse_env(text: str) -> dict[str, str]` — pure parser, no `os.environ` side effect.
  - `app.paths.home() -> Path`
  - `app.paths.data_dir() -> Path`, `index_dir() -> Path`, `log_dir() -> Path`, `config_dir() -> Path`, `backup_dir() -> Path`
  - `app.paths.package_dir() -> Path` — repo/package root that holds the read-only `data/` artifacts.
  - `app.paths.ensure_dirs() -> list[Path]` — creates the 5 user dirs, returns them.
  - Env keys read: `SM_HOME`, `SM_DATA_DIR`, `SM_INDEX_DIR`, `SM_LOG_DIR`, `SM_CONFIG_DIR`, `SM_BACKUP_DIR`.

- [ ] **Step 1: Write `tests/test_env.py`**

```python
import os
from pathlib import Path

from app.env import load_env, parse_env


def test_parse_handles_comments_blanks_and_quotes():
    text = "\n".join([
        "# comment",
        "",
        "SM_PORT=8901",
        'SM_HOME="C:\\Users\\me\\sm"',
        "SM_STUDENT='me'",
        "  SM_LOG_LEVEL = INFO  ",
    ])
    got = parse_env(text)
    assert got == {
        "SM_PORT": "8901",
        "SM_HOME": "C:\\Users\\me\\sm",
        "SM_STUDENT": "me",
        "SM_LOG_LEVEL": "INFO",
    }


def test_parse_ignores_malformed_lines():
    assert parse_env("NOEQUALS\n=nokey\nOK=1") == {"OK": "1"}


def test_load_env_does_not_override_real_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("SM_PORT", "9999")
    f = tmp_path / ".env"
    f.write_text("SM_PORT=8901\nSM_STUDENT=me\n", encoding="utf-8")
    parsed = load_env(f)
    assert parsed["SM_PORT"] == "8901"          # returned as parsed
    assert os.environ["SM_PORT"] == "9999"      # real env wins
    assert os.environ["SM_STUDENT"] == "me"     # absent key is set


def test_load_env_missing_file_is_ok(tmp_path):
    assert load_env(tmp_path / "nope.env") == {}
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_env.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.env'`

- [ ] **Step 3: Write `app/env.py`**

```python
"""Cargador .env minimo (stdlib). Sin interpolacion, sin `export`."""
from __future__ import annotations

import os
from pathlib import Path


def parse_env(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if not key:
            continue
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        out[key] = val
    return out


def load_env(path: str | Path | None = None) -> dict[str, str]:
    """Parsea `path`, fija en os.environ solo lo ausente, devuelve lo parseado."""
    p = Path(path) if path is not None else Path(".env")
    if not p.is_file():
        return {}
    parsed = parse_env(p.read_text(encoding="utf-8"))
    for key, val in parsed.items():
        os.environ.setdefault(key, val)
    return parsed
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_env.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Write `tests/test_paths.py`**

```python
from pathlib import Path

import app.paths as paths


def test_home_defaults_under_localappdata_on_windows(monkeypatch):
    monkeypatch.delenv("SM_HOME", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\me\AppData\Local")
    monkeypatch.setattr(paths.os, "name", "nt", raising=False)
    assert paths.home() == Path(r"C:\Users\me\AppData\Local\SistemesDeMesura")


def test_home_env_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("SM_HOME", str(tmp_path / "sm"))
    assert paths.home() == tmp_path / "sm"


def test_each_dir_has_independent_override(monkeypatch, tmp_path):
    monkeypatch.setenv("SM_HOME", str(tmp_path / "sm"))
    monkeypatch.setenv("SM_LOG_DIR", str(tmp_path / "elsewhere" / "logs"))
    assert paths.data_dir() == tmp_path / "sm" / "data"
    assert paths.index_dir() == tmp_path / "sm" / "index"
    assert paths.config_dir() == tmp_path / "sm" / "config"
    assert paths.backup_dir() == tmp_path / "sm" / "backups"
    assert paths.log_dir() == tmp_path / "elsewhere" / "logs"


def test_ensure_dirs_creates_all_five(monkeypatch, tmp_path):
    monkeypatch.setenv("SM_HOME", str(tmp_path / "sm"))
    for var in ("SM_DATA_DIR", "SM_INDEX_DIR", "SM_LOG_DIR",
                "SM_CONFIG_DIR", "SM_BACKUP_DIR"):
        monkeypatch.delenv(var, raising=False)
    made = paths.ensure_dirs()
    assert sorted(p.name for p in made) == [
        "backups", "config", "data", "index", "logs"]
    assert all(p.is_dir() for p in made)


def test_package_dir_points_at_repo_root_with_data():
    assert (paths.package_dir() / "app").is_dir()
```

- [ ] **Step 6: Run to verify failure**

Run: `pytest tests/test_paths.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.paths'`

- [ ] **Step 7: Write `app/paths.py`**

```python
"""Resolucion de directorios configurables. SM_HOME + 5 subdirs con override."""
from __future__ import annotations

import os
from pathlib import Path

_APP_DIRNAME_WIN = "SistemesDeMesura"
_APP_DIRNAME_POSIX = "sistemes-de-mesura"


def home() -> Path:
    override = os.environ.get("SM_HOME")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / _APP_DIRNAME_WIN
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / _APP_DIRNAME_POSIX


def _sub(var: str, name: str) -> Path:
    override = os.environ.get(var)
    return Path(override).expanduser() if override else home() / name


def data_dir() -> Path:
    return _sub("SM_DATA_DIR", "data")


def index_dir() -> Path:
    return _sub("SM_INDEX_DIR", "index")


def log_dir() -> Path:
    return _sub("SM_LOG_DIR", "logs")


def config_dir() -> Path:
    return _sub("SM_CONFIG_DIR", "config")


def backup_dir() -> Path:
    return _sub("SM_BACKUP_DIR", "backups")


def package_dir() -> Path:
    """Raiz que contiene los artefactos data/ de solo lectura (repo o paquete)."""
    return Path(__file__).resolve().parent.parent


def ensure_dirs() -> list[Path]:
    made = [data_dir(), index_dir(), log_dir(), config_dir(), backup_dir()]
    for p in made:
        p.mkdir(parents=True, exist_ok=True)
    return made
```

- [ ] **Step 8: Run to verify pass**

Run: `pytest tests/test_paths.py tests/test_env.py -v`
Expected: PASS (9 tests)

- [ ] **Step 9: Full regression**

Run: `pytest tests/ -q`
Expected: PASS, same count as before + 9.

- [ ] **Step 10: Commit**

```bash
git add app/env.py app/paths.py tests/test_env.py tests/test_paths.py
git commit -m "b1: cargador .env y resolutor de directorios configurables

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 2: Wire paths + `.env` + `SM_STUDENT` into the runtime

**Files:**
- Modify: `app/config.py` (add path wrappers; keep `DEFAULT_*` names)
- Modify: `app/build_index.py:22-24` (`WORKSPACE`/`KB`/`INDEX_DIR`)
- Modify: `web/server.py` — `DEMO_STUDENT` constant (line 63) and its ~30 uses; `KB`/`INDEX`/`GENDB` (lines 60-62); `main()` (lines 1078-1103)
- Modify: `tests/test_packaging.py` (entry-point expectation stays `sistemes-web` until Task 5; add a boot test)
- Test: `tests/test_student_identity.py`

**Interfaces:**
- Consumes: `app.env.load_env`, `app.paths.*` from Task 1.
- Produces:
  - `web.server` module-level `KB`, `INDEX`, `GENDB` now computed from `app.paths` (still `str`).
  - `Bridge.__init__` gains `student: str = ""`; empty → resolved from `os.environ.get("SM_STUDENT", "me")`. Attribute `Bridge.student`.
  - `web.server.main` calls `app.env.load_env()` first thing.

- [ ] **Step 1: Write `tests/test_student_identity.py`**

```python
import importlib

import web.server as server


def test_bridge_defaults_student_to_me(monkeypatch, tmp_path):
    monkeypatch.delenv("SM_STUDENT", raising=False)
    b = server.Bridge(workdir=str(tmp_path))
    assert b.student == "me"


def test_bridge_reads_sm_student_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SM_STUDENT", "damaga")
    b = server.Bridge(workdir=str(tmp_path))
    assert b.student == "damaga"


def test_no_demo_student_constant_remains():
    src = importlib.import_module("web.server").__file__
    with open(src, encoding="utf-8") as fh:
        assert "DEMO_STUDENT" not in fh.read()
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_student_identity.py -v`
Expected: FAIL — `AttributeError: 'Bridge' object has no attribute 'student'` and the constant test fails.

- [ ] **Step 3: Add path wrappers to `app/config.py`**

Append after the existing constants:

```python
# --- F14: rutas efectivas (delegan en app.paths; los DEFAULT_* se conservan
#     como fallback para imports antiguos y ejecucion desde el checkout). ---
from app import paths as _paths  # noqa: E402


def processed_dir():
    return _paths.package_dir() / DEFAULT_PROCESSED_DIR


def eval_dir():
    return _paths.package_dir() / DEFAULT_EVAL_DIR
```

- [ ] **Step 4: Repoint `app/build_index.py`**

Replace lines 22-24:

```python
from app import paths as sm_paths  # noqa: E402

WORKSPACE = sm_paths.package_dir()
KB = WORKSPACE / "data" / "processed" / "knowledge.sqlite"
INDEX_DIR = sm_paths.index_dir()
```

Then in `main()`, ensure `INDEX_DIR.parent` exists: add `INDEX_DIR.mkdir(parents=True, exist_ok=True)` before the first write.

- [ ] **Step 5: Repoint `web/server.py` module constants**

Replace lines 60-63:

```python
from app import paths as sm_paths  # noqa: E402

KB = str(sm_paths.package_dir() / "data" / "processed" / "knowledge.sqlite")
INDEX = str(sm_paths.index_dir()) if sm_paths.index_dir().exists() \
    else str(sm_paths.package_dir() / "data" / "index")
GENDB = str(sm_paths.package_dir() / "data" / "generated" / "questions.sqlite")
```

- [ ] **Step 6: Replace `DEMO_STUDENT` with `self.student`**

In `Bridge.__init__` (around line 203) add parameter and attribute:

```python
    def __init__(self, kb=KB, index=INDEX, gen_src=GENDB,
                 workdir: str = "", sessions: dict | None = None,
                 lock=None, calendar_path=None, student: str = "") -> None:
        ...
        self.student = student or os.environ.get("SM_STUDENT", "me")
```

Add `import os` at the top if not present (it is imported inside `main()` today — hoist it to module scope).

Then replace every `DEMO_STUDENT` token in the file with `self.student`. There are ~30, all inside `Bridge` methods, so `self` is in scope. Verify with:

```bash
grep -n "DEMO_STUDENT" web/server.py   # expect: no matches
```

For the two `_token()` uses (lines ~523) the dict value becomes `{"student": self.student, "practice": None}`.

- [ ] **Step 7: `main()` loads `.env` and honors `SM_STUDENT`/`SM_HOST`/`SM_PORT`**

In `web/server.py` `main()`, before `ap = argparse.ArgumentParser(...)`:

```python
    from app.env import load_env
    load_env(os.environ.get("SM_ENV_FILE"))            # ./.env if unset
    from app import paths as sm_paths
    load_env(sm_paths.config_dir() / ".env")            # fallback lookup
```

Keep the existing `--host/--port/--data-dir/--calendar` args; their `os.environ.get` defaults now see `.env` values.

- [ ] **Step 8: Add the boot test to `tests/test_packaging.py`**

```python
def test_server_module_imports_without_hardcoded_temp_paths():
    text = (ROOT / "web" / "server.py").read_text(encoding="utf-8")
    assert "AppData\\\\Local\\\\Temp" not in text
    assert "app import paths" in text
```

- [ ] **Step 9: Run tests**

Run: `pytest tests/test_student_identity.py tests/test_packaging.py tests/web/ -q`
Expected: PASS. If a `tests/web/` test constructed `Bridge` expecting `"demo"` state, update it to `"me"` (search: `grep -rn '"demo"' tests/`).

- [ ] **Step 10: Full regression**

Run: `pytest tests/ -q`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add app/config.py app/build_index.py web/server.py tests/
git commit -m "b1: rutas desde app.paths y SM_STUDENT sustituye DEMO_STUDENT

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 3: Schema migrations (`PRAGMA user_version`, forward-only)

**Files:**
- Create: `app/migrate.py`
- Create: `app/migrations/student/001_baseline.sql`, `app/migrations/questions/001_baseline.sql`, `app/migrations/exam_sessions/001_baseline.sql`, `app/migrations/knowledge/001_baseline.sql` (each a one-line comment; see Step 3)
- Modify: `app/student/store.py:67`, `app/exam/store.py:87`, `app/examiner/store.py:46`, `app/store.py:84` — add one line after `executescript`
- Test: `tests/test_migrations.py`

**Design note (deviation from spec §4, smaller diff):** the existing `SCHEMA`/`EXAM_SCHEMA`/`KNOWLEDGE_SCHEMA` strings stay in the stores — they are already idempotent `CREATE TABLE IF NOT EXISTS`. They *are* baseline version 1. `migrate()` stamps `user_version = 1` on first contact and applies only `002+` scripts. `001_baseline.sql` files exist as markers so the numbering scheme is uniform and the next author adds `002_*.sql`.

**Interfaces:**
- Consumes: nothing from earlier tasks (pure `sqlite3`).
- Produces:
  - `app.migrate.TARGETS: dict[str, int]` — `{"student": 1, "questions": 1, "exam_sessions": 1, "knowledge": 1}`.
  - `app.migrate.migrate(con: sqlite3.Connection, db_name: str) -> int` — applies pending scripts in one transaction each, returns the resulting `user_version`. If current > target → raises `RuntimeError` (snapshot from newer code).
  - `app.migrate.status() -> dict[str, tuple[int, int]]` — `{db_name: (current, target)}` for every DB that exists on disk, resolved via `app.paths`.
  - `app.migrate.MIGRATIONS_DIR: Path`.

- [ ] **Step 1: Write `tests/test_migrations.py`**

```python
import sqlite3
import pytest

from app import migrate


def _v(con):
    return con.execute("PRAGMA user_version").fetchone()[0]


def test_fresh_db_reaches_target(tmp_path):
    con = sqlite3.connect(tmp_path / "s.sqlite")
    assert _v(con) == 0
    new = migrate.migrate(con, "student")
    assert new == migrate.TARGETS["student"] == 1
    assert _v(con) == 1


def test_migrate_is_idempotent(tmp_path):
    con = sqlite3.connect(tmp_path / "s.sqlite")
    migrate.migrate(con, "student")
    assert migrate.migrate(con, "student") == 1
    assert _v(con) == 1


def test_newer_snapshot_is_rejected(tmp_path):
    con = sqlite3.connect(tmp_path / "s.sqlite")
    con.execute("PRAGMA user_version = 99")
    with pytest.raises(RuntimeError, match="newer"):
        migrate.migrate(con, "student")


def test_unknown_db_name_raises(tmp_path):
    con = sqlite3.connect(tmp_path / "s.sqlite")
    with pytest.raises(KeyError):
        migrate.migrate(con, "does_not_exist")


def test_out_of_order_or_duplicate_script_is_caught(tmp_path, monkeypatch):
    d = tmp_path / "student"
    d.mkdir()
    (d / "001_baseline.sql").write_text("-- baseline\n", encoding="utf-8")
    (d / "003_gap.sql").write_text("SELECT 1;\n", encoding="utf-8")
    monkeypatch.setattr(migrate, "MIGRATIONS_DIR", tmp_path)
    monkeypatch.setitem(migrate.TARGETS, "student", 3)
    con = sqlite3.connect(tmp_path / "s.sqlite")
    with pytest.raises(RuntimeError, match="gap|secuencia"):
        migrate.migrate(con, "student")
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_migrations.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.migrate'`

- [ ] **Step 3: Create the baseline marker files**

Each of the four files `app/migrations/<db_name>/001_baseline.sql`:

```sql
-- 001 baseline: el esquema vive en el store (CREATE TABLE IF NOT EXISTS,
-- idempotente). Esta migracion no ejecuta DDL; solo marca user_version = 1.
-- Anade el proximo cambio de esquema como 002_<descripcion>.sql.
```

- [ ] **Step 4: Write `app/migrate.py`**

```python
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
        with con:                                  # transaccion
            con.executescript(sql)
            con.execute("PRAGMA user_version = %d" % num)
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
```

Note: the `_scripts` numbering check treats a lone `001` as valid; `migrate` promotes `user_version` to `target` even when only the marker exists.

- [ ] **Step 5: Run to verify pass**

Run: `pytest tests/test_migrations.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Hook `migrate()` into the four stores**

`app/student/store.py`, in `__init__` after line 68 (`con.commit()`):

```python
            from app.migrate import migrate as _migrate
            _migrate(con, "student")
            con.commit()
```

`app/exam/store.py` after `con.executescript(EXAM_SCHEMA)`:

```python
            from app.migrate import migrate as _migrate
            _migrate(con, "exam_sessions")
```

`app/examiner/store.py` after `con.executescript(SCHEMA)`:

```python
            from app.migrate import migrate as _migrate
            _migrate(con, "questions")
```

`app/store.py` after `con.executescript(KNOWLEDGE_SCHEMA)` (line 84):

```python
        from app.migrate import migrate as _migrate
        _migrate(con, "knowledge")
```

(Imports are function-local to avoid an import cycle at module load.)

- [ ] **Step 7: Full regression**

Run: `pytest tests/ -q`
Expected: PASS. The stores now stamp `user_version = 1` on open; behavior is otherwise unchanged.

- [ ] **Step 8: Commit**

```bash
git add app/migrate.py app/migrations/ app/store.py app/student/store.py app/exam/store.py app/examiner/store.py tests/test_migrations.py
git commit -m "b2: migraciones forward-only con PRAGMA user_version

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 4: Backup and restore

**Files:**
- Create: `app/backup.py`
- Test: `tests/test_backup_restore.py`

**Interfaces:**
- Consumes: `app.paths.data_dir/backup_dir`, `app.migrate.status`.
- Produces:
  - `app.backup.WRITABLE_DBS: tuple[str, ...]` = `("student.sqlite", "questions.sqlite", "exam_sessions.sqlite")`.
  - `app.backup.make_backup(out_dir: Path | None = None) -> Path` — creates `<out_dir or backup_dir()>/<UTC-ISO>/`, online-copies each existing writable DB into it, writes `manifest.json`, returns the snapshot dir.
  - `app.backup.list_backups() -> list[dict]` — newest first: `{"timestamp": str, "path": str, "files": [{"name","bytes","sha256","user_version"}], "app_version": str}`.
  - `app.backup.restore(timestamp: str) -> Path` — pre-backs-up current state to `<backup_dir()>/<UTC>-pre-restore/`, copies snapshot files over the live DBs, returns the pre-restore dir. Raises `RuntimeError` if a snapshot file's `user_version` exceeds `app.migrate.TARGETS`.

- [ ] **Step 1: Write `tests/test_backup_restore.py`**

```python
import sqlite3
from pathlib import Path

import pytest

from app import backup


@pytest.fixture
def sm_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SM_HOME", str(tmp_path))
    from app import paths
    paths.ensure_dirs()
    d = paths.data_dir()
    con = sqlite3.connect(d / "student.sqlite")
    con.execute("CREATE TABLE t(x)")
    con.execute("INSERT INTO t VALUES (1)")
    con.execute("PRAGMA user_version = 1")
    con.commit()
    con.close()
    return tmp_path


def test_backup_then_restore_round_trips(sm_home):
    from app import paths
    snap = backup.make_backup()
    db = paths.data_dir() / "student.sqlite"
    con = sqlite3.connect(db)
    con.execute("INSERT INTO t VALUES (2)")
    con.commit()
    con.close()
    backup.restore(snap.name)
    con = sqlite3.connect(db)
    rows = con.execute("SELECT x FROM t ORDER BY x").fetchall()
    con.close()
    assert rows == [(1,)]


def test_manifest_records_hash_and_version(sm_home):
    snap = backup.make_backup()
    manifest = snap / "manifest.json"
    assert manifest.is_file()
    listed = backup.list_backups()
    assert listed[0]["timestamp"] == snap.name
    entry = next(f for f in listed[0]["files"] if f["name"] == "student.sqlite")
    assert entry["user_version"] == 1
    assert len(entry["sha256"]) == 64


def test_restore_refuses_newer_user_version(sm_home, monkeypatch):
    snap = backup.make_backup()
    # tamper: bump the snapshot's user_version above target
    con = sqlite3.connect(snap / "student.sqlite")
    con.execute("PRAGMA user_version = 50")
    con.commit()
    con.close()
    with pytest.raises(RuntimeError, match="newer|user_version"):
        backup.restore(snap.name)
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_backup_restore.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backup'`

- [ ] **Step 3: Write `app/backup.py`**

```python
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
    snap = root / _timestamp()
    snap.mkdir(parents=True, exist_ok=False)
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
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_backup_restore.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Full regression**

Run: `pytest tests/ -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/backup.py tests/test_backup_restore.py
git commit -m "b3: backup/restore online de las SQLite escribibles

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 5: `sistemes` CLI — `init`, `serve`, `ingest`, `backup`, `restore`

**Files:**
- Create: `app/cli.py`
- Modify: `app/ingest.py` — `main()` gains `--out` + non-writable-target guard
- Modify: `pyproject.toml` — add `sistemes` entry point (keep `sistemes-web`)
- Modify: `.env.example` — full key set
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `app.env.load_env`, `app.paths`, `app.backup`, `app.migrate.status`, `web.server.main`, `app.ingest.run`, `app.build_index.main`.
- Produces:
  - `app.cli.main(argv: list[str] | None = None) -> int` — dispatch on `argv[0]` subcommand; unknown/absent → prints help, returns `2`.
  - Subcommands: `init [--force]`, `serve [--host H] [--port P] [--data-dir D] [--calendar C]`, `ingest --source DIR --out DIR`, `check [--json] [--fast] [--status] [--write-manifest] [--source DIR]` (wired in Task 6; Task 5 ships a stub that returns `0` and prints `check: pendiente`), `backup [--out DIR] [--list]`, `restore --from TS`.
  - `check` stub interface must match Task 6's real `check`, so the arg parser is defined fully here.

- [ ] **Step 1: Write `tests/test_cli.py`**

```python
import subprocess
import sys
from pathlib import Path

import pytest

from app import cli

ROOT = Path(__file__).resolve().parents[1]


def test_no_subcommand_prints_help_and_returns_2(capsys):
    assert cli.main([]) == 2
    assert "sistemes" in capsys.readouterr().out.lower()


def test_version_reads_pyproject(capsys):
    assert cli.main(["--version"]) == 0
    out = capsys.readouterr().out.strip()
    assert out == (ROOT / "VERSION_MARKER").read_text().strip() \
        if (ROOT / "VERSION_MARKER").exists() else out.count(".") >= 2


def test_init_creates_dirs_and_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SM_HOME", str(tmp_path))
    assert cli.main(["init"]) == 0
    for name in ("data", "index", "logs", "config", "backups"):
        assert (tmp_path / name).is_dir()
    assert (tmp_path / "config" / ".env").is_file()


def test_init_is_idempotent_and_force_rewrites(tmp_path, monkeypatch):
    monkeypatch.setenv("SM_HOME", str(tmp_path))
    cli.main(["init"])
    envf = tmp_path / "config" / ".env"
    envf.write_text("SM_PORT=1\n", encoding="utf-8")
    assert cli.main(["init"]) == 0
    assert envf.read_text(encoding="utf-8") == "SM_PORT=1\n"     # not touched
    assert cli.main(["init", "--force"]) == 0
    assert "SM_PORT=8901" in envf.read_text(encoding="utf-8")     # rewritten


def test_ingest_refuses_readonly_target_without_out(monkeypatch, tmp_path):
    # --source present, --out absent, default target under package dir
    rc = cli.main(["ingest", "--source", str(tmp_path)])
    assert rc == 2


def test_deprecated_alias_still_runs():
    result = subprocess.run(
        [sys.executable, "-m", "web.server", "--help"],
        cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.cli'`

- [ ] **Step 3: Write `app/cli.py`**

```python
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
    p.add_argument("--host"); p.add_argument("--port", type=int)
    p.add_argument("--data-dir"); p.add_argument("--calendar")

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
    from web.server import main as web_main
    argv = []
    if args.host: argv += ["--host", args.host]
    if args.port: argv += ["--port", str(args.port)]
    if args.data_dir: argv += ["--data-dir", args.data_dir]
    if args.calendar: argv += ["--calendar", args.calendar]
    return web_main(argv)


def _cmd_ingest(args) -> int:
    out = Path(args.out) if args.out else _paths.package_dir() / "data"
    processed = out / "processed"
    try:
        processed.mkdir(parents=True, exist_ok=True)
        probe = processed / ".writable"
        probe.write_text("x", encoding="utf-8"); probe.unlink()
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
    ap = _build_parser()
    args = ap.parse_args(argv)
    if args.version:
        print(_version())
        return 0
    if not args.cmd:
        ap.print_help()
        return 2
    return _DISPATCH[args.cmd](args)
```

Note: `_cmd_check` references `artifacts.check` / `artifacts.write_manifest` — Task 6 creates `app/artifacts.py`. For Task 5's green bar, add a temporary shim `app/artifacts.py`:

```python
"""Stub temporal (Task 5). Task 6 lo reemplaza."""
from pathlib import Path


def check(fast: bool = False, source=None) -> list[str]:
    return []


def write_manifest() -> Path:
    raise NotImplementedError("Task 6")
```

- [ ] **Step 4: Add `--out` guard to `app/ingest.py` `main()`**

Replace `main()` (lines ~400-406) so it accepts `--out` and forwards; keep `run()` untouched:

```python
def main() -> None:
    ap = argparse.ArgumentParser(description="Ingesta Fase 1 (solo lectura de fuentes)")
    ap.add_argument("--source", default=config.DEFAULT_SOURCE_DIR)
    ap.add_argument("--out", default=None,
                    help="raiz de salida (contiene processed/ y evaluation/)")
    ap.add_argument("--processed", default=None)
    ap.add_argument("--eval", default=None)
    args = ap.parse_args()
    workspace = Path(__file__).resolve().parent.parent
    out = Path(args.out) if args.out else workspace / "data"
    processed = Path(args.processed) if args.processed else out / "processed"
    eval_dir = Path(args.eval) if args.eval else out / "evaluation"
    run(Path(args.source), processed, eval_dir, workspace)
```

- [ ] **Step 5: `pyproject.toml` entry point**

Under `[project.scripts]` add (keep the existing line):

```toml
[project.scripts]
sistemes-web = "web.server:main"
sistemes = "app.cli:main"
```

- [ ] **Step 6: Rewrite `.env.example`**

```ini
# Configuracio local. No posar secrets en aquest fitxer.
SM_HOME=
SM_HOST=127.0.0.1
SM_PORT=8901
SM_STUDENT=me
SM_DATA_DIR=
SM_INDEX_DIR=
SM_LOG_DIR=
SM_CONFIG_DIR=
SM_BACKUP_DIR=
SM_LOG_LEVEL=INFO
SM_MAX_BODY_BYTES=1048576
SM_REQUEST_TIMEOUT=30
SM_TLS=0
COURSE_CALENDAR_PATH=
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash-lite
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (6 tests). Adjust `test_version_reads_pyproject` to a plain `assert out.count(".") >= 2` if the `VERSION_MARKER` branch is awkward — the intent is only "prints a dotted version".

- [ ] **Step 8: Full regression**

Run: `pytest tests/ -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add app/cli.py app/artifacts.py app/ingest.py pyproject.toml .env.example tests/test_cli.py
git commit -m "b4: CLI unica sistemes (init/serve/ingest/backup/restore) + stub check

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 6: Artifact integrity `check` + `serve` gate + `ARTIFACT-MANIFEST.json`

**Files:**
- Replace: `app/artifacts.py` (the Task 5 stub → real implementation)
- Create: `data/ARTIFACT-MANIFEST.json` (generated, committed)
- Test: `tests/test_check.py`, `tests/test_serve_gate.py`

**Interfaces:**
- Consumes: `app.paths`, `app.migrate` (`TARGETS`, connect to read `user_version`), `app.env.parse_env`.
- Produces:
  - `app.artifacts.MANIFEST_NAME = "ARTIFACT-MANIFEST.json"`.
  - `app.artifacts.PACKAGED_ARTIFACTS: tuple[str, ...]` — repo-relative POSIX paths of read-only artifacts.
  - `app.artifacts.SENTINELS: dict[str, tuple[str, str, int]]` — `{label: (db_relpath, sql_count_query, expected)}`; includes `{"formulas": ("data/processed/knowledge.sqlite", "SELECT COUNT(*) FROM formulas", 2896)}` plus chunk/document/vf-question counts filled from `docs/PHASE_8_FINAL_CERTIFICATION.md` at implementation time.
  - `app.artifacts.write_manifest() -> Path` — hashes every `PACKAGED_ARTIFACTS` entry (files, or every file under a dir), writes `data/ARTIFACT-MANIFEST.json` = `{"generated_for_version": str, "files": {relpath: sha256}}`, returns its path.
  - `app.artifacts.check(fast: bool = False, source: Path | None = None) -> list[str]` — returns a list of human-readable problems; empty list = OK.
    - full: (1) sha256 vs manifest, (2) `user_version` == `TARGETS` + expected tables present, (3) sentinel counts, (4) `.env` parses (if `config_dir()/.env` exists) + the 5 dirs exist and the writable ones are writable, (5) if `source` given, `app.ingest.verify_sources` passes.
    - `fast=True`: only (2) + (4).

- [ ] **Step 1: Write `tests/test_check.py`**

```python
import json
import sqlite3
from pathlib import Path

import pytest

from app import artifacts


@pytest.fixture
def staged(tmp_path, monkeypatch):
    """A minimal fake package dir with one artifact + manifest."""
    pkg = tmp_path / "pkg"
    (pkg / "data" / "processed").mkdir(parents=True)
    db = pkg / "data" / "processed" / "knowledge.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE formulas(x)")
    con.executemany("INSERT INTO formulas VALUES (?)", [(i,) for i in range(3)])
    con.execute("PRAGMA user_version = 1")
    con.commit(); con.close()
    monkeypatch.setattr(artifacts._paths, "package_dir", lambda: pkg)
    monkeypatch.setenv("SM_HOME", str(tmp_path / "home"))
    from app import paths
    paths.ensure_dirs()
    monkeypatch.setattr(artifacts, "PACKAGED_ARTIFACTS",
                        ("data/processed/knowledge.sqlite",))
    monkeypatch.setattr(artifacts, "SENTINELS",
                        {"formulas": ("data/processed/knowledge.sqlite",
                                      "SELECT COUNT(*) FROM formulas", 3)})
    return pkg


def test_clean_check_passes(staged):
    artifacts.write_manifest()
    assert artifacts.check() == []


def test_altered_artifact_is_detected(staged):
    artifacts.write_manifest()
    db = staged / "data" / "processed" / "knowledge.sqlite"
    con = sqlite3.connect(db); con.execute("INSERT INTO formulas VALUES (99)")
    con.commit(); con.close()
    problems = artifacts.check()
    assert any("sha256" in p or "hash" in p for p in problems)


def test_stale_user_version_is_detected(staged, monkeypatch):
    artifacts.write_manifest()
    monkeypatch.setitem(artifacts._migrate.TARGETS, "knowledge", 2)
    assert any("user_version" in p for p in artifacts.check(fast=True))


def test_broken_sentinel_is_detected(staged, monkeypatch):
    artifacts.write_manifest()
    monkeypatch.setattr(artifacts, "SENTINELS",
                        {"formulas": ("data/processed/knowledge.sqlite",
                                      "SELECT COUNT(*) FROM formulas", 999)})
    assert any("formulas" in p for p in artifacts.check())


def test_fast_is_a_subset_of_full(staged):
    artifacts.write_manifest()
    assert artifacts.check(fast=True) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_check.py -v`
Expected: FAIL — stub has no `write_manifest` / `PACKAGED_ARTIFACTS` / `_paths`.

- [ ] **Step 3: Write the real `app/artifacts.py`**

```python
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

PACKAGED_ARTIFACTS = (
    "data/processed/knowledge.sqlite",
    "data/generated/questions.sqlite",
    "data/evaluation/eval.sqlite",
    "data/index",
    "data/source_manifest.json",
)

# label -> (db relpath, count query, expected). Rellenar los ?, tomando el
# valor de docs/PHASE_8_FINAL_CERTIFICATION.md, antes de cerrar la tarea.
SENTINELS: dict[str, tuple[str, str, int]] = {
    "formulas": ("data/processed/knowledge.sqlite",
                 "SELECT COUNT(*) FROM formulas", 2896),
    "chunks": ("data/processed/knowledge.sqlite",
               "SELECT COUNT(*) FROM chunks", 0),          # <- fijar
    "documents": ("data/processed/knowledge.sqlite",
                  "SELECT COUNT(*) FROM documents", 0),      # <- fijar
    "vf_questions": ("data/evaluation/eval.sqlite",
                     "SELECT COUNT(*) FROM eval_questions", 0),  # <- fijar
}

_EXPECTED_TABLES = {
    "data/processed/knowledge.sqlite":
        {"meta", "sources", "documents", "sections", "chunks", "formulas"},
    "data/generated/questions.sqlite": set(),   # rellenar tras inspeccion
    "data/evaluation/eval.sqlite": set(),
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
    txt = (_paths.package_dir() / "pyproject.toml").read_text(encoding="utf-8")
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
        {"generated_for_version": _app_version(), "files": files}, indent=2),
        encoding="utf-8")
    return out


def _check_hashes() -> list[str]:
    mpath = _paths.package_dir() / "data" / MANIFEST_NAME
    if not mpath.is_file():
        return ["falta %s (ejecuta `sistemes check --write-manifest`)" % MANIFEST_NAME]
    manifest = json.loads(mpath.read_text(encoding="utf-8"))["files"]
    problems = []
    for rel, want in manifest.items():
        p = _paths.package_dir() / rel
        if not p.is_file():
            problems.append("artefacto ausente: %s" % rel)
        elif _sha256(p) != want:
            problems.append("sha256 no coincide: %s" % rel)
    return problems


def _check_schema() -> list[str]:
    problems = []
    for rel, mig_name in _DB_MIGRATE_NAME.items():
        p = _paths.package_dir() / rel
        if not p.is_file():
            problems.append("BD ausente: %s" % rel)
            continue
        con = sqlite3.connect(p)
        try:
            cur = con.execute("PRAGMA user_version").fetchone()[0]
            tgt = _migrate.TARGETS[mig_name]
            if cur != tgt:
                problems.append("user_version %s: %d != objetivo %d" % (rel, cur, tgt))
            have = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            missing = _EXPECTED_TABLES.get(rel, set()) - have
            if missing:
                problems.append("%s: faltan tablas %s" % (rel, sorted(missing)))
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
    for p in (_paths.data_dir(), _paths.log_dir(),
              _paths.config_dir(), _paths.backup_dir()):
        if not p.is_dir():
            problems.append("directorio ausente: %s" % p)
        else:
            probe = p / ".writable_probe"
            try:
                probe.write_text("x", encoding="utf-8"); probe.unlink()
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
        con = sqlite3.connect("file:%s?mode=ro" % p, uri=True)
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
```

- [ ] **Step 4: Fill the sentinel numbers**

Read `docs/PHASE_8_FINAL_CERTIFICATION.md` (and `PHASE_10`/`PHASE_11` certification docs) for the frozen counts. Replace every `0` placeholder in `SENTINELS` and populate `_EXPECTED_TABLES` for `questions.sqlite` / `eval.sqlite` by inspecting them:

```bash
python -c "import sqlite3;print(sorted(r[0] for r in sqlite3.connect('data/generated/questions.sqlite').execute(\"SELECT name FROM sqlite_master WHERE type='table'\")))"
python -c "import sqlite3;print(sorted(r[0] for r in sqlite3.connect('data/evaluation/eval.sqlite').execute(\"SELECT name FROM sqlite_master WHERE type='table'\")))"
python -c "import sqlite3;print(sqlite3.connect('data/processed/knowledge.sqlite').execute('SELECT COUNT(*) FROM chunks').fetchone())"
```

- [ ] **Step 5: Run `check` tests**

Run: `pytest tests/test_check.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Generate and commit the real manifest**

```bash
python -m app.cli check --write-manifest
git add data/ARTIFACT-MANIFEST.json
```

- [ ] **Step 7: Write `tests/test_serve_gate.py`**

```python
from app import cli


def test_serve_aborts_when_check_fast_reports_problems(monkeypatch, capsys):
    monkeypatch.setattr("app.artifacts.check", lambda *a, **k: ["esquema roto"])
    rc = cli.main(["serve"])
    assert rc == 1
    assert "abortado" in capsys.readouterr().err


def test_serve_starts_when_artifacts_ok(monkeypatch):
    monkeypatch.setattr("app.artifacts.check", lambda *a, **k: [])
    called = {}
    monkeypatch.setattr("web.server.main",
                        lambda argv: called.setdefault("argv", argv) or 0)
    assert cli.main(["serve", "--port", "9", "--host", "127.0.0.1"]) == 0
    assert called["argv"] == ["--host", "127.0.0.1", "--port", "9"]
```

- [ ] **Step 8: Run + full regression**

Run: `pytest tests/test_serve_gate.py tests/ -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add app/artifacts.py data/ARTIFACT-MANIFEST.json tests/test_check.py tests/test_serve_gate.py
git commit -m "b5: check de integridad de artefactos + gate de arranque en serve

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 7: Structured logging

**Files:**
- Create: `app/logsetup.py`
- Modify: `web/server.py` — `Handler.log_message` (line ~1015) writes a request line; `main()` calls `logsetup.configure`; wrap `_api()` body errors into `error.log`
- Modify: `app/cli.py` — configure logging at `main()` start; log subcommand failures
- Test: `tests/test_logsetup.py`

**Interfaces:**
- Consumes: `app.paths.log_dir`.
- Produces:
  - `app.logsetup.configure(log_dir: Path | None = None, level: str | None = None) -> None` — idempotent; attaches a `RotatingFileHandler(maxBytes=5_242_880, backupCount=5)` for logger `"sistemes.request"` → `serve.log` and `"sistemes.error"` (level `ERROR`) → `error.log`. `level` defaults to `SM_LOG_LEVEL` or `"INFO"`.
  - `app.logsetup.request(method: str, path: str, status: int, ms: float) -> None` — emits one line `method path status ms` on `"sistemes.request"`.
  - `app.logsetup.exception(msg: str) -> None` — emits on `"sistemes.error"` with `exc_info=True`.

- [ ] **Step 1: Write `tests/test_logsetup.py`**

```python
import logging
from pathlib import Path

from app import logsetup


def test_configure_writes_request_lines(tmp_path):
    logsetup.configure(tmp_path, "INFO")
    logsetup.request("GET", "/api/study/topics", 200, 12.5)
    for h in logging.getLogger("sistemes.request").handlers:
        h.flush()
    text = (tmp_path / "serve.log").read_text(encoding="utf-8")
    assert "GET /api/study/topics 200 12" in text


def test_no_student_content_helper_only_takes_scalars():
    # request() signature accepts only method/path/status/ms — enforced by call sites
    import inspect
    params = list(inspect.signature(logsetup.request).parameters)
    assert params == ["method", "path", "status", "ms"]


def test_error_log_captures_exceptions(tmp_path):
    logsetup.configure(tmp_path, "INFO")
    try:
        raise ValueError("boom")
    except ValueError:
        logsetup.exception("fallo de prueba")
    for h in logging.getLogger("sistemes.error").handlers:
        h.flush()
    text = (tmp_path / "error.log").read_text(encoding="utf-8")
    assert "fallo de prueba" in text and "ValueError" in text


def test_configure_is_idempotent(tmp_path):
    logsetup.configure(tmp_path)
    logsetup.configure(tmp_path)
    assert len(logging.getLogger("sistemes.request").handlers) == 1


def test_level_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SM_LOG_LEVEL", "WARNING")
    logsetup.configure(tmp_path)
    assert logging.getLogger("sistemes.request").level == logging.WARNING
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_logsetup.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.logsetup'`

- [ ] **Step 3: Write `app/logsetup.py`**

```python
"""Logs estructurados a fichero rotado (stdlib logging)."""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app import paths as _paths

_MAX_BYTES = 5 * 1024 * 1024
_BACKUPS = 5
_CONFIGURED = False


def _attach(name: str, filename: Path, level: int) -> None:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    for h in list(logger.handlers):
        logger.removeHandler(h)
    handler = RotatingFileHandler(
        filename, maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ"))
    logger.addHandler(handler)
    logger.propagate = False


def configure(log_dir: Path | None = None, level: str | None = None) -> None:
    global _CONFIGURED
    d = Path(log_dir) if log_dir else _paths.log_dir()
    d.mkdir(parents=True, exist_ok=True)
    lvl = getattr(logging, (level or os.environ.get("SM_LOG_LEVEL", "INFO")).upper(),
                  logging.INFO)
    _attach("sistemes.request", d / "serve.log", lvl)
    _attach("sistemes.error", d / "error.log", logging.ERROR)
    _CONFIGURED = True


def request(method: str, path: str, status: int, ms: float) -> None:
    logging.getLogger("sistemes.request").info(
        "%s %s %d %d", method, path, status, int(ms))


def exception(msg: str) -> None:
    logging.getLogger("sistemes.error").error(msg, exc_info=True)
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_logsetup.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Wire into `web/server.py`**

In `main()` after `load_env(...)`:

```python
    from app import logsetup
    logsetup.configure()
```

Replace `Handler.log_message` (currently `pass`):

```python
    def log_message(self, fmt, *args):
        pass  # el acceso se registra en _api() con tiempo y status reales
```

In `Handler._api()`, wrap the dispatch to time it and log:

```python
    def _api(self):
        import time
        t0 = time.perf_counter()
        url = urllib.parse.urlparse(self.path)
        ...
        try:
            status, payload, cookie = self.thread_bridge().route(...)
        except Exception:
            from app import logsetup
            logsetup.exception("route fallo: %s %s" % (self.command, url.path))
            status, payload, cookie = 500, {"ok": False, "code": "INTERNAL_ERROR",
                                            "message": "error intern"}, ""
        from app import logsetup
        logsetup.request(self.command, url.path, status,
                         (time.perf_counter() - t0) * 1000)
        self._send(status, payload, cookie)
```

- [ ] **Step 6: Wire into `app/cli.py`**

At the top of `main()` after `load_env(...)`:

```python
    from app import logsetup
    logsetup.configure()
```

Wrap `_DISPATCH[args.cmd](args)`:

```python
    try:
        return _DISPATCH[args.cmd](args)
    except Exception:                              # noqa: BLE001
        from app import logsetup
        logsetup.exception("subcomando fallo: %s" % args.cmd)
        raise
```

- [ ] **Step 7: Full regression**

Run: `pytest tests/ -q`
Expected: PASS. If a web test asserts on captured stdout/stderr noise, it should be unaffected (logs go to files).

- [ ] **Step 8: Commit**

```bash
git add app/logsetup.py web/server.py app/cli.py tests/test_logsetup.py
git commit -m "b6: logs estructurados rotados (serve.log / error.log)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 8: Health check, request limits, CSRF

**Files:**
- Modify: `web/server.py` — `route()` cookie header (line 672); new `/api/health` branch; `Handler.do_POST`/`_api` size + timeout guard; CSRF check helper
- Create: `web/static/js/csrf.js`
- Modify: every `web/*.html` — add `<script src="static/js/csrf.js"></script>` before the page script
- Modify: `web/static/js/*.js` — route mutating `window.fetch` calls through `smFetch`
- Test: `tests/test_health.py`, `tests/test_limits.py`, `tests/test_csrf.py`

**Interfaces:**
- Consumes: `Bridge` router from prior tasks.
- Produces:
  - `Bridge.route` issues two `Set-Cookie` headers: `sm_session` (`HttpOnly; SameSite=Strict; Path=/`, `+ Secure` when `os.environ.get("SM_TLS") == "1"`) and `sm_csrf` (`SameSite=Strict; Path=/`, not HttpOnly), both carrying the per-session token from `self.sessions[tok]`.
  - `Bridge._csrf_ok(method, path, cookie, headers) -> bool` — `True` for `GET`; for `POST /api/*` requires header `X-CSRF-Token` equal to the `sm_csrf` cookie value. `route()` returns `403 {"ok": False, "code": "CSRF", "message": "CSRF"}` when it fails. `/api/health` is exempt.
  - `route()` signature gains `headers: dict | None = None` (kept optional; `Handler` passes real headers).
  - `GET /api/health` → `200 {"status":"ok","version":<str>,"checks":{"kb":bool,"index":bool,"student_db":bool}}` or `503` with `"status":"degraded"` if any check is false. No cookie requirement, no CSRF.
  - `Handler` rejects `Content-Length > int(os.environ.get("SM_MAX_BODY_BYTES","1048576"))` with `413 {"ok":False,"code":"PAYLOAD_TOO_LARGE"}`.
  - `ThreadingHTTPServer` socket timeout set from `SM_REQUEST_TIMEOUT` (default `30`).
  - JS: `window.smFetch(path, opts)` — same contract as `window.fetch`, adds `X-CSRF-Token` from `document.cookie` for non-GET; used by every mutating call.

- [ ] **Step 1: Write `tests/test_csrf.py`**

```python
import web.server as server


def _bridge(tmp_path):
    return server.Bridge(workdir=str(tmp_path))


def test_get_needs_no_csrf(tmp_path):
    b = _bridge(tmp_path)
    status, _, _ = b.route("GET", "/api/study/topics", {}, {}, "")
    assert status == 200


def test_post_without_token_is_rejected(tmp_path):
    b = _bridge(tmp_path)
    status, payload, _ = b.route(
        "POST", "/api/practice/start", {}, {"topic": 2}, "", headers={})
    assert status == 403 and payload["code"] == "CSRF"


def test_post_with_matching_token_passes_csrf(tmp_path):
    b = _bridge(tmp_path)
    # first GET to mint the session + csrf cookie
    _, _, set_cookie = b.route("GET", "/api/session", {}, {}, "")
    tok = [c for c in set_cookie.split("\n") if c.startswith("sm_csrf=")][0]
    csrf = tok.split("=", 1)[1].split(";", 1)[0]
    sess = [c for c in set_cookie.split("\n") if c.startswith("sm_session=")][0]
    cookie = "%s; %s" % (sess.split(";", 1)[0], tok.split(";", 1)[0])
    status, payload, _ = b.route(
        "POST", "/api/practice/start", {}, {"topic": 2}, cookie,
        headers={"X-CSRF-Token": csrf})
    assert status != 403  # may be 200 or a domain error, but not CSRF
```

Note: `route()` today returns a single `Set-Cookie` string. This task changes it to `"\n".join([...])`; `Handler._send` already writes one `Set-Cookie` header — update it to split on `\n` and emit one header per line.

- [ ] **Step 2: Write `tests/test_health.py`**

```python
import web.server as server


def test_health_ok_when_artifacts_present(tmp_path):
    b = server.Bridge(workdir=str(tmp_path))
    status, payload, _ = b.route("GET", "/api/health", {}, {}, "")
    assert status == 200
    assert payload["status"] == "ok"
    assert set(payload["checks"]) == {"kb", "index", "student_db"}


def test_health_degraded_when_kb_missing(tmp_path, monkeypatch):
    b = server.Bridge(workdir=str(tmp_path))
    monkeypatch.setattr(b, "kb", str(tmp_path / "nope.sqlite"))
    status, payload, _ = b.route("GET", "/api/health", {}, {}, "")
    assert status == 503 and payload["checks"]["kb"] is False
```

- [ ] **Step 3: Write `tests/test_limits.py`**

```python
import http.client
import threading

import web.server as server


def test_oversize_body_is_rejected(monkeypatch, tmp_path, free_tcp_port):
    monkeypatch.setenv("SM_MAX_BODY_BYTES", "16")
    monkeypatch.setenv("SM_DATA_DIR", str(tmp_path))
    srv = server.ThreadingHTTPServer(("127.0.0.1", free_tcp_port), server.Handler)
    server.Handler.config = {"kw": {"workdir": str(tmp_path)},
                             "sessions": {}, "lock": threading.Lock()}
    t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", free_tcp_port, timeout=5)
        conn.request("POST", "/api/practice/start", body=b"x" * 100,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        assert resp.status == 413
    finally:
        srv.shutdown()
```

Add a `free_tcp_port` fixture to `tests/conftest.py` if not present:

```python
import socket
import pytest


@pytest.fixture
def free_tcp_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port
```

- [ ] **Step 4: Run to verify failure**

Run: `pytest tests/test_csrf.py tests/test_health.py tests/test_limits.py -v`
Expected: FAIL (routes/behaviors not implemented).

- [ ] **Step 5: Implement in `web/server.py`**

`Bridge.route()` — replace the cookie line and add the CSRF gate + session/health branches:

```python
        tok = self._token(cookie)
        with self._lock:
            csrf = self.sessions[tok].setdefault("csrf", secrets.token_hex(24))
        secure = "; Secure" if os.environ.get("SM_TLS") == "1" else ""
        set_cookie = "\n".join([
            "sm_session=%s; Path=/; SameSite=Strict; HttpOnly%s" % (tok, secure),
            "sm_csrf=%s; Path=/; SameSite=Strict%s" % (csrf, secure)])

        if method == "GET" and path == "/api/health":
            checks = {
                "kb": Path(self.kb).is_file(),
                "index": Path(self.index).exists(),
                "student_db": True}
            ok = all(checks.values())
            from app.cli import _version
            return (200 if ok else 503), {
                "status": "ok" if ok else "degraded",
                "version": _version(), "checks": checks}, set_cookie
        if method == "GET" and path == "/api/session":
            return 200, {"csrf": csrf, "student": self.student}, set_cookie

        if method == "POST" and path.startswith("/api/"):
            hdr = (headers or {}).get("X-CSRF-Token")
            if not hdr or hdr != csrf:
                return 403, {"ok": False, "code": "CSRF", "message": "CSRF"}, set_cookie
```

Change `def route(self, method, path, query=None, body=None, cookie=""):` →
`def route(self, method, path, query=None, body=None, cookie="", headers=None):`

`Handler._send` — emit one header per `Set-Cookie` line:

```python
        if cookie:
            for line in cookie.split("\n"):
                self.send_header("Set-Cookie", line)
```

`Handler._api` — size guard before reading body, and pass headers:

```python
        limit = int(os.environ.get("SM_MAX_BODY_BYTES", "1048576"))
        try:
            clen = int(self.headers.get("Content-Length", 0))
        except ValueError:
            clen = 0
        if clen > limit:
            return self._send(413, {"ok": False, "code": "PAYLOAD_TOO_LARGE",
                                    "message": "cos massa gran"}, "")
        ...
        status, payload, cookie = self.thread_bridge().route(
            self.command, url.path, query, body,
            self.headers.get("Cookie", ""), headers=dict(self.headers))
```

`main()` — socket timeout:

```python
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    srv.timeout = int(os.environ.get("SM_REQUEST_TIMEOUT", "30"))
```

- [ ] **Step 6: Write `web/static/js/csrf.js`**

```javascript
/* smFetch: adjunta X-CSRF-Token (cookie sm_csrf) a las peticiones mutantes. */
(function () {
  "use strict";
  function readCookie(name) {
    var m = document.cookie.match("(?:^|; )" + name + "=([^;]*)");
    return m ? decodeURIComponent(m[1]) : "";
  }
  window.smFetch = function (path, opts) {
    opts = opts || {};
    var method = (opts.method || "GET").toUpperCase();
    if (method !== "GET" && method !== "HEAD") {
      opts.headers = opts.headers || {};
      opts.headers["X-CSRF-Token"] = readCookie("sm_csrf");
    }
    return window.fetch(path, opts);
  };
})();
```

- [ ] **Step 7: Include the script + switch mutating calls**

In each `web/*.html`, add before the page's own `<script>`:

```html
<script src="static/js/csrf.js"></script>
```

In `web/static/js/{practice,exam,exams,learning,study}.js`, the local `api(path, opts)` helpers call `window.fetch(path, opts)` — change to `window.smFetch(path, opts)`. GET-only files (`calendar.js`, `documents.js`, `history.js`, `results.js`, `review.js`, `topic.js`) need no change.

- [ ] **Step 8: Run tests + regression**

Run: `pytest tests/test_csrf.py tests/test_health.py tests/test_limits.py tests/ -q`
Expected: PASS. Existing `tests/web/` route tests that call `b.route("POST", ...)` without headers will now get `403` — update them to pass a matching `headers={"X-CSRF-Token": ...}` after reading the cookie, or add a test helper `post(bridge, path, body)` in `tests/web/conftest.py` that does the GET-then-POST dance. Budget time for ~5-10 such updates.

- [ ] **Step 9: Commit**

```bash
git add web/server.py web/static/js/ web/*.html tests/
git commit -m "b6: health check, limites de tamano/timeout y CSRF double-submit

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 9: Packaging — install.ps1, package.ps1, version 1.0.0, CHANGELOG, checklist

**Files:**
- Modify: `pyproject.toml` — `version = "1.0.0"`, `requires-python = ">=3.11,<3.15"`, `dev` extra
- Create: `scripts/install.ps1`
- Modify: `scripts/package.ps1` — read version from `pyproject.toml`, bundle `install.ps1` + `ARTIFACT-MANIFEST.json`
- Create: `CHANGELOG.md`, `docs/RELEASE_CHECKLIST.md`
- Rewrite: `docs/PHASE_14_PACKAGING.md`
- Modify: `tests/test_packaging.py`
- Modify: `DECISION_LOG.md` — append D169–D178

**Interfaces:**
- Consumes: `app.cli` entry point from Task 5, `app.artifacts.write_manifest` from Task 6.
- Produces: no new Python API.

- [ ] **Step 1: Update `tests/test_packaging.py`**

Replace the file body:

```python
"""Contrato F14 de arranque reproducible y configuracion portable."""

import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_declares_sistemes_cli_and_python_floor():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["version"] == "1.0.0"
    assert data["project"]["requires-python"] == ">=3.11,<3.15"
    scripts = data["project"]["scripts"]
    assert scripts["sistemes"] == "app.cli:main"
    assert scripts["sistemes-web"] == "web.server:main"          # alias conservado
    assert data["project"].get("dependencies", []) == []


def test_sistemes_cli_help_runs_without_installation():
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "--help"],
        cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0
    for word in ("init", "serve", "ingest", "check", "backup", "restore"):
        assert word in result.stdout


def test_env_example_has_all_keys_and_no_secret_value():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    for key in ("SM_HOME", "SM_STUDENT", "SM_DATA_DIR", "SM_INDEX_DIR",
                "SM_LOG_DIR", "SM_CONFIG_DIR", "SM_BACKUP_DIR",
                "SM_MAX_BODY_BYTES", "SM_REQUEST_TIMEOUT", "GEMINI_API_KEY="):
        assert key in text
    assert "GEMINI_API_KEY=sk-" not in text


def test_packaging_scripts_present_and_safe():
    package = (ROOT / "scripts" / "package.ps1").read_text(encoding="utf-8")
    install = (ROOT / "scripts" / "install.ps1").read_text(encoding="utf-8")
    assert "Compress-Archive" in package
    assert "Get-FileHash" in package
    assert "ARTIFACT-MANIFEST.json" in package
    assert "0.13.0" not in package                       # version no cableada
    assert "pip install" in install
    assert "GEMINI_API_KEY" not in package


def test_changelog_and_checklist_exist():
    assert (ROOT / "CHANGELOG.md").is_file()
    assert "1.0.0" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert (ROOT / "docs" / "RELEASE_CHECKLIST.md").is_file()
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_packaging.py -v`
Expected: FAIL (version still `0.13.0`, no `sistemes` script, no `install.ps1`, no CHANGELOG).

- [ ] **Step 3: Edit `pyproject.toml`**

```toml
[project]
name = "sistemes-de-mesura"
version = "1.0.0"
description = "Tutor verificable i entorn d'estudi per a Sistemes de Mesura"
requires-python = ">=3.11,<3.15"
dependencies = []

[project.optional-dependencies]
dev = ["pytest"]

[project.scripts]
sistemes-web = "web.server:main"
sistemes = "app.cli:main"

[tool.setuptools.packages.find]
include = ["app*", "web*"]

[tool.setuptools.package-data]
web = ["*.html", "static/css/*.css", "static/js/*.js"]
app = ["migrations/*/*.sql"]
```

- [ ] **Step 4: Write `scripts/install.ps1`**

```powershell
param(
    [switch]$Dev
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$pyv = & python -c "import sys;print('%d.%d'%sys.version_info[:2])"
$maj, $min = $pyv.Split(".")
if ([int]$maj -ne 3 -or [int]$min -lt 11 -or [int]$min -ge 15) {
    throw "Se requiere Python >=3.11,<3.15 (encontrado $pyv)"
}

$venv = Join-Path $root ".venv"
if (-not (Test-Path $venv)) { & python -m venv $venv }
$py = Join-Path $venv "Scripts\python.exe"
& $py -m pip install --no-input --upgrade pip
if ($Dev) { & $py -m pip install --no-input -e "$root[dev]" }
else { & $py -m pip install --no-input $root }

$sistemes = Join-Path $venv "Scripts\sistemes.exe"
Write-Output ("CLI: " + $sistemes)
if ($Dev) {
    & $py -m pytest (Join-Path $root "tests") -q
    & $sistemes check
}
```

- [ ] **Step 5: Extend `scripts/package.ps1`**

Replace the hardcoded `$version = "0.13.0"` line with a read from `pyproject.toml`:

```powershell
$pyproject = Get-Content -LiteralPath (Join-Path $repo "pyproject.toml") -Raw
$version = [regex]::Match($pyproject, 'version\s*=\s*"([^"]+)"').Groups[1].Value
```

In the `foreach ($item in @(...))` list add `"CHANGELOG.md"`. After staging, before building the zip, copy the installer and regenerate the artifact manifest:

```powershell
Copy-Item -LiteralPath (Join-Path $repo "scripts\install.ps1") `
    -Destination (Join-Path $stage "scripts\install.ps1") -Force
& python -c "import sys; sys.path.insert(0, r'$stage'); from app.artifacts import write_manifest; print(write_manifest())"
```

(The `data/ARTIFACT-MANIFEST.json` committed in Task 6 already ships via the `data` copy; this line refreshes it against the staged tree.)

- [ ] **Step 6: Write `CHANGELOG.md`**

```markdown
# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.1.0/).

## [1.0.0] - 2026-09-08

### Added
- CLI unica `sistemes` (`init`, `serve`, `ingest`, `check`, `backup`, `restore`).
- Cargador `.env` y directorios configurables (`SM_HOME` + datos/index/logs/config/backups).
- Migraciones de esquema SQLite forward-only (`PRAGMA user_version`).
- Copia de seguridad y restauracion online de las SQLite escribibles.
- Verificacion de integridad de artefactos (`sistemes check`) y gate de arranque en `serve`.
- Logs estructurados rotados (`serve.log`, `error.log`).
- Health check `GET /api/health`, limites de tamano de cuerpo y timeout de peticion.
- Proteccion CSRF (double-submit cookie) en la API.
- Instalacion reproducible: `scripts/install.ps1` (venv + `pip install .`).

### Changed
- Identidad de estudiante desde `SM_STUDENT` (default `me`); se elimina `DEMO_STUDENT`.
- Version oficial `1.0.0`, leida de `pyproject.toml` por el packaging.

### Notes
- Alcance: uso local mono-usuario. Sin autenticacion, sin despliegue multiusuario.
```

- [ ] **Step 7: Write `docs/RELEASE_CHECKLIST.md`**

```markdown
# Release checklist

1. `pytest tests/ -q` en verde (dos pasadas consecutivas).
2. `python -m app.cli check` en verde; `python -m app.cli check --status` sin desajustes.
3. `CHANGELOG.md`: entrada nueva con la version y la fecha.
4. `pyproject.toml`: `version` subida.
5. `pwsh scripts/package.ps1` genera el zip; anotar `ARTIFACT` y `SHA256`.
6. Probar en carpeta limpia: `scripts/install.ps1`, luego
   `sistemes init && sistemes check && sistemes serve`.
7. `git tag v<version>` y push.
```

- [ ] **Step 8: Rewrite `docs/PHASE_14_PACKAGING.md`**

Summarize the delivered state: the `sistemes` CLI, the five directories, `.env`, migrations, backup/restore, `check`, logging, health, limits, CSRF, `install.ps1`, version `1.0.0`. List the limit: no bundled Python runtime, no MSI; requires Python 3.11+ on the target. Mark academic claims — none expected.

- [ ] **Step 9: Append to `DECISION_LOG.md`**

Add the `## Operación local (F14 ampliada)` section with D169–D178 exactly as listed in `docs/superpowers/specs/2026-09-08-local-operations-design.md` §14.

- [ ] **Step 10: Run full regression twice**

Run: `pytest tests/ -q` (twice)
Expected: PASS both times, identical counts.

- [ ] **Step 11: Exit-criterion dry run (manual, document result)**

On a clean checkout copy with only Python 3.11+:
```
pwsh scripts/install.ps1
.venv\Scripts\sistemes init
.venv\Scripts\sistemes check          # expect: check OK, exit 0
.venv\Scripts\sistemes serve --port 8901   # expect: web responds at 127.0.0.1:8901
.venv\Scripts\sistemes backup
.venv\Scripts\sistemes restore --from <timestamp>   # expect: restore OK
# corrupt one byte of data/processed/knowledge.sqlite in the copy
.venv\Scripts\sistemes check          # expect: check FALLO, exit 1
```
Record the transcript in `docs/PHASE_14_PACKAGING.md` under "Verificación".

- [ ] **Step 12: Commit**

```bash
git add pyproject.toml scripts/ CHANGELOG.md docs/ tests/test_packaging.py DECISION_LOG.md
git commit -m "b7: packaging 1.0.0 — install.ps1, package.ps1 versionado, CHANGELOG, checklist

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**

| Spec §  | Requirement | Task |
|---|---|---|
| 2.1 | `.env` loader, lookup order, real-env precedence | Task 1, Task 2 (wiring), Task 5 (`config_dir` lookup) |
| 2.2 | `SM_STUDENT` replaces `DEMO_STUDENT` | Task 2 |
| 3 | `app/paths.py`, 5 dirs, overrides, kill hardcoded paths | Task 1, Task 2 |
| 3.1 / 3.2 | packaged read-only vs writable split | Task 2 (paths), Task 6 (`PACKAGED_ARTIFACTS`) |
| 4 | `PRAGMA user_version` forward-only migrator, baseline, store hook, knowledge stamp, no down | Task 3 |
| 5 | backup/restore CLI, online `.backup()`, manifest, pre-restore, refuse newer version, `--list`, KB excluded | Task 4, Task 5 (CLI verbs) |
| 6 | CSRF double-submit, `SameSite=Strict`, `Secure` on `SM_TLS`, GET exempt, in-memory session kept | Task 8 |
| 7 | `sistemes` CLI init/ingest/serve/check/backup/restore, maintainer `ingest`, deprecated alias | Task 5 (+ Task 6 real `check`) |
| 8 | `check`: hashes, schema, sentinels, config, source; `--fast`; manifest generation | Task 6 |
| 9.1 | `logsetup`, serve.log/error.log, rotation, level from env, no student content | Task 7 |
| 9.2 | `/api/health` 200/503 with checks, no auth/CSRF | Task 8 |
| 9.3 | `SM_MAX_BODY_BYTES` → 413, `SM_REQUEST_TIMEOUT` socket timeout | Task 8 |
| 10 | pyproject `1.0.0` + `requires-python` + `sistemes` script + `dev` extra; `install.ps1`; `package.ps1` version read + bundle; artifacts in zip not wheel; `CHANGELOG.md`; `RELEASE_CHECKLIST.md` | Task 9 |
| 11 | all 12 test files | Tasks 1,3,4,5,6,7,8,9 (each writes its own) |
| 12 | exit criterion dry run | Task 9 Step 11 |
| 13 | block order B1–B7 | Tasks 2/1→3→4→5→6→7-8→9 |
| 14 | D169–D178 to DECISION_LOG | Task 9 Step 9 |

No uncovered requirement.

**Placeholder scan:** `app/artifacts.py` ships `SENTINELS` with `0` placeholders **by design** — Task 6 Step 4 is an explicit step to fill them from the certification docs, and `_check_sentinels` skips any `expected == 0` entry so the bar stays green until they're set. `_EXPECTED_TABLES` for `questions.sqlite`/`eval.sqlite` are filled in the same step. No other placeholders.

**Type consistency:** `check(fast: bool, source: Path | None) -> list[str]` — identical signature in the Task 5 stub, Task 6 real module, and both call sites (`cli._cmd_check`, `cli._cmd_serve`). `make_backup(out_dir: Path | None) -> Path` consistent between `app/backup.py` and `cli._cmd_backup`. `migrate(con, db_name) -> int` consistent across `app/migrate.py`, the four store hooks, and `test_migrations.py`. `_version()` defined in both `app/cli.py` and referenced from `web/server.py` Task 8 (`from app.cli import _version`) — same function. `route(..., headers=None)` extended once in Task 8; `Handler._api` passes `headers=dict(self.headers)`.

**Note on `_check_config` in `--fast`:** `check(fast=True)` runs `_check_schema() + _check_config()`. `_check_config` probes writability of `data/log/config/backup` dirs; on a fresh install `serve` runs after `sistemes init` (which calls `ensure_dirs`), so the dirs exist. If `serve` is run before `init`, the gate fails with a clear "directorio ausente" message — acceptable and correct.

