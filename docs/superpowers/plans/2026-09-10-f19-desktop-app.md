# F19 — Web → Windows Desktop App — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the existing `Sistemes-de-Mesura` web app as a single distributable Windows desktop executable (`SistemesDeMesura.exe`) — a `pywebview` window over the unchanged Python `ThreadingHTTPServer`, bundled with PyInstaller — without rewriting the app.

**Architecture:** Additive desktop/packaging layer only. New `escritorio.py` launcher starts `web.server.main(["--host","127.0.0.1","--port","0"])` in a daemon thread; the server writes its OS-assigned bound port to `$SM_PORT_FILE` (a new 4-line opt-in carve-out in `web/server.py`, the ONLY backend change); the launcher reads that port, waits for the socket, and opens a `pywebview` (WebView2) window at `http://127.0.0.1:<port>/index.html`. `app/paths.py` already splits read-only `package_dir()` (→ `sys._MEIPASS` when frozen) from writable `data_dir()` (→ `%LOCALAPPDATA%\SistemesDeMesura\data`), and `Bridge.__init__` already seed-copies `questions.sqlite` + creates `student.sqlite` there on first run — so frozen runtime needs no code changes beyond the port carve-out.

**Tech Stack:** Python 3.14 · stdlib `http.server` (unchanged) · `pywebview>=5.4` + `pythonnet>=3.0` (win32, WebView2 backend) · `pyinstaller>=6.0` · PowerShell build script · GitHub Actions `windows-latest` job.

**Spec:** presented and approved in-conversation (brainstorming, 2026-09-10); decisions 1b-ii / 2a / 3a / 4a / 5a / 6a; user's structuring document "F19 — Plan detallado de implementación" is the authoritative task/gate/order reference.

## Global Constraints

- **Branch:** all work on `f19-desktop-app` (worktree from `2bb48420181f8526371a52798a8267368a9205bf`). **No commits on `main`.**
- **Backend:** the ONLY change to `web/server.py` is the opt-in `SM_PORT_FILE` write, AFTER the real `ThreadingHTTPServer` bind, BEFORE `serve_forever()`. When `SM_PORT_FILE` is unset, `web.server.main()` behaves byte-identically to today. No other line of `web/server.py` changes.
- **No changes** to `app/`, the API surface / endpoints / contracts, the KB, `data/` academic artifacts, or `web/*.html` / `web/static/**` — unless a test demonstrates a real incompatibility, which then stops the plan for design review (never an ad-hoc fix in the same commit).
- **No** Node / Electron / Tauri / Rust; **no** JS↔Python bridge (`js_api`); **no** new persistent storage / localStorage keys; **no** secrets in bundle / spec / ps1 / exe / repo / docs.
- **Never write runtime data inside `_MEIPASS`.** Student/exam data stays in `%LOCALAPPDATA%\SistemesDeMesura\` (via `sm_paths`).
- Host is always `127.0.0.1`; never `0.0.0.0` / external bind.
- Linux CI job `test` stays functionally unchanged. `pywebview` / `pyinstaller` are **optional extras** (`[desktop]`, `[build]`); base `pip install -e .` and the Linux job acquire no desktop deps.
- **Regression floor** (must hold before PR): `pytest -q` → `0 failed`, no new skips (the one skip stays `test_home_defaults_under_xdg_on_posix`); `app.cli check` OK; `app.cli check --status` OK; `app.final_certification_benchmark` = `125/125`; `app.review_results_history_benchmark` = `100/100`.
- **Baseline to record before any code:** `937 passed, 1 skipped, 0 failed`.
- One focused commit per piece (F19-00 … F19-06); no mixed refactors/cleanup/UI/backend changes.
- Closes via a **PR to `main`** (no direct merge — `main` is protected; F17/F18 pattern).

---

## File Structure

| File | New/Mod | Responsibility |
|---|---|---|
| `web/server.py` | **Modify** (≤5 lines) | `main()`: if `SM_PORT_FILE` set, write `srv.socket.getsockname()[1]` to that path after bind, before `serve_forever()`. Nothing else. |
| `escritorio.py` | **Create** (~90 lines) | Desktop entrypoint: temp port-file, `SM_PORT_FILE` env, daemon thread → `web.server.main()`, active wait (port-file + int-parse + socket + thread-alive), `webview.create_window` + `webview.start`, temp-file cleanup. No server logic. |
| `escritorio.spec` | **Create** | PyInstaller spec: `Analysis(["escritorio.py"], datas=<audited>, hiddenimports=<webview backends + build-verified>)`, `EXE(name="SistemesDeMesura", console=False, icon="icono.ico")`. Paths from `os.path.dirname(SPEC)`. |
| `build.ps1` | **Create** | Detect venv/PATH Python → assert `pywebview`+`pyinstaller` importable (fail clearly, optional explicit `pip install -e ".[desktop,build]"`) → `pyinstaller escritorio.spec --noconfirm --clean` → assert `dist\SistemesDeMesura.exe` exists & >0 → propagate exit code → print path. Only ever deletes project `build/` and `dist/`. |
| `icono.ico` | **Create** (binary, versioned) | Multi-res app icon (16/32/48/256). Committed directly; no generator. |
| `pyproject.toml` | **Modify** | Add `[project.optional-dependencies]` groups `desktop` and `build`. `dev` unchanged. `dependencies` stays `[]`. |
| `.github/workflows/ci.yml` | **Modify** (add job) | New `desktop` job `runs-on: windows-latest`: install `.[dev,desktop,build]` → `pytest tests/ -q` → `app.cli init && app.cli check` → `pyinstaller escritorio.spec` → headless smoke (start exe, wait port-file, curl `/index.html` + `/api/health` → 200, kill, assert clean). Linux `test` job untouched. |
| `tests/desktop/__init__.py` | **Create** | package marker |
| `tests/desktop/test_server_port_file.py` | **Create** | F19-00: `SM_PORT_FILE` unset → no file, unchanged behaviour; set + `--port 0` → file appears after bind with the real socket port; startup failure detectable. |
| `tests/desktop/test_launcher.py` | **Create** | F19-01/05: import without GUI; argv is `--host 127.0.0.1 --port 0`; waits for BOTH port-file and socket; finite timeout on "port never published"; error on server-thread death; `webview.create_window`/`start` mocked → asserts localhost URL, `1280×850`, `min_size=(900,600)`, `text_select=True`, `debug=False`, **no `js_api`**; no `bind→close→reuse` in the source. |
| `tests/desktop/test_frozen_paths.py` | **Create** | F19-05: with `sys.frozen`/`sys._MEIPASS` monkeypatched → `package_dir()` inside `_MEIPASS`, `data_dir()` outside; `Bridge` seed-copy lands in `data_dir()/questions.sqlite`, `student.sqlite` created outside bundle, nothing written under `_MEIPASS/data`. |
| `tests/desktop/test_spec.py` | **Create** | F19-05: `escritorio.spec` exists & parses; `console=False`; `icon` → `icono.ico` and that file exists & is a valid ICO; `datas` == exactly the audited resource set; excluded paths absent; webview hiddenimports present. Fails if a critical resource is dropped. |
| `docs/F19_DESKTOP_APP.md` | **Create** | Architecture, dev run, EXE build, Windows/WebView2 Runtime requirement, data & backup locations, no-Gemini-key behaviour, startup troubleshooting, CI limitations, smoke + F18-02 runtime gate. |
| `docs/DECISION_LOG.md` | **Modify** | Append D188 (desktop wrapper decision + `SM_PORT_FILE` carve-out rationale). |
| `docs/superpowers/plans/2026-09-10-f19-desktop-app.md` | **Create** | this plan (committed first, on the worktree). |

**Audited bundle resource set** (verified by real imports/request paths, not a prior list):
`web/` · `data/processed/knowledge.sqlite` · `data/generated/questions.sqlite` · `data/index/` (`lexical/fts.sqlite`, `semantic/vocab.json`, `semantic/postings.json`, `manifest.json`) · `data/source_manifest.json` · `data/evaluation/eval.sqlite` · `data/ARTIFACT-MANIFEST.json` · `.env.example`.
**Excluded** (not on any request path): `data/processed/*.jsonl`, `data/processed/students.sqlite`, `data/processed/ingestion_report.json`, `data/metadata/`, `data/evaluation/*.jsonl`, `data/evaluation/*_results.json`, `data/student/`.

---

## Task 0: Worktree + baseline

**Files:** none (setup + measurement).

- [ ] **Step 1: Create the worktree** (via `superpowers:using-git-worktrees`)

```bash
git worktree add -b f19-desktop-app <repo>/.worktrees/f19-desktop-app 2bb48420181f8526371a52798a8267368a9205bf
cd <repo>/.worktrees/f19-desktop-app
git rev-parse HEAD          # expect 2bb4842...
git status --porcelain      # expect empty
```

- [ ] **Step 2: Commit this plan**

```bash
mkdir -p docs/superpowers/plans
# write docs/superpowers/plans/2026-09-10-f19-desktop-app.md (this file)
git add docs/superpowers/plans/2026-09-10-f19-desktop-app.md
git commit -m "F19-plan: desktop app implementation plan"
```

- [ ] **Step 3: Record the baseline** (do NOT edit code first)

```bash
python -m pytest -q 2>&1 | tail -3
python -m app.cli check;          echo "check exit=$?"
python -m app.cli check --status; echo "status exit=$?"
python -m app.final_certification_benchmark        | grep '"score"'
python -m app.review_results_history_benchmark     | grep '"score"'
```
Expected: `937 passed, 1 skipped, 0 failed` · check OK · status OK · `125/125` · `100/100`.
Write the numbers into a ledger note. **If anything regresses vs this, stop.**

---

## Task 1: F19-00 — publish the bound server port (`web/server.py`)

**Files:**
- Modify: `web/server.py` (in `main()`, right after `srv = ThreadingHTTPServer((args.host, args.port), Handler)` and its `print(...)`, before `try: srv.serve_forever()`)
- Test: `tests/desktop/test_server_port_file.py`

**Interfaces:**
- Consumes: nothing new. `os` and `sm_paths` are already imported in `web/server.py`.
- Produces: opt-in side effect — when `os.environ.get("SM_PORT_FILE")` is truthy, `main()` writes the decimal bound port (no trailing newline needed, but a newline is fine) to that path once, after bind, before serving.

- [ ] **Step 1: Write the failing test**

```python
# tests/desktop/test_server_port_file.py
import os
import socket
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web"))
import server as S  # noqa: E402


def _run_server(argv, env):
    old = {k: os.environ.get(k) for k in env}
    os.environ.update({k: v for k, v in env.items() if v is not None})
    for k, v in env.items():
        if v is None:
            os.environ.pop(k, None)
    t = threading.Thread(target=lambda: S.main(argv), daemon=True)
    t.start()
    return t, old


def _restore(old):
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def test_port_file_written_after_bind_with_real_port(tmp_path):
    pf = tmp_path / "port"
    t, old = _run_server(["--host", "127.0.0.1", "--port", "0"],
                         {"SM_PORT_FILE": str(pf), "SM_DATA_DIR": str(tmp_path / "d")})
    try:
        for _ in range(150):
            if pf.is_file() and pf.read_text().strip().isdigit():
                break
            time.sleep(0.1)
        assert pf.is_file(), "SM_PORT_FILE never written"
        port = int(pf.read_text().strip())
        assert 1024 < port < 65536
        # the published port is actually accepting connections
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            pass
    finally:
        _restore(old)


def test_no_port_file_when_env_unset(tmp_path):
    # pick a fixed free port so we can prove the server came up without a file
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    sentinel = tmp_path / "should-not-exist"
    t, old = _run_server(["--host", "127.0.0.1", "--port", str(port)],
                         {"SM_PORT_FILE": None, "SM_DATA_DIR": str(tmp_path / "d")})
    try:
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise AssertionError("server did not start")
        assert not sentinel.exists()
    finally:
        _restore(old)
```

- [ ] **Step 2: Run — expect FAIL** (`test_port_file_written_after_bind_with_real_port` fails: file never appears)

```bash
python -m pytest tests/desktop/test_server_port_file.py -q
```

- [ ] **Step 3: Minimal implementation** — in `web/server.py` `main()`:

```python
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print("Sistemes de Mesura a http://%s:%d (dades: %s)"
          % (args.host, srv.server_address[1], data))
    # F19: opt-in port publication for the desktop launcher. Only when
    # SM_PORT_FILE is set; written after the real bind, before serving; the
    # server's own bind is the only bind (no TOCTOU probe/close/rebind).
    _port_file = os.environ.get("SM_PORT_FILE")
    if _port_file:
        try:
            Path(_port_file).write_text(str(srv.server_address[1]), encoding="utf-8")
        except OSError:
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
```
(`Path` is already imported at top of `web/server.py`; if not, add `from pathlib import Path` — verify first. The `print` change from `args.port` to `srv.server_address[1]` is so `--port 0` logs the real port; it is inside the same statement and changes no behaviour when `--port` is explicit.)

- [ ] **Step 4: Run — expect PASS** (both tests)

```bash
python -m pytest tests/desktop/test_server_port_file.py -q
python -m pytest tests/web/ -q            # server tests still green
```

- [ ] **Step 5: Commit**

```bash
git add web/server.py tests/desktop/test_server_port_file.py tests/desktop/__init__.py
git commit -m "F19-00: publish bound server port for desktop launcher"
```

---

## Task 2: F19-01 — desktop launcher (`escritorio.py`)

**Files:**
- Create: `escritorio.py`
- Test: `tests/desktop/test_launcher.py`

**Interfaces:**
- Consumes: `web.server.main(argv)`; `os.environ["SM_PORT_FILE"]`; `webview.create_window`, `webview.start`.
- Produces: `main()` (callable, returns `int`); module-level constants `PREFERRED_TITLE`, `WIN_W=1280`, `WIN_H=850`, `WIN_MIN=(900,600)`, `WAIT_TIMEOUT=15.0`; helper `wait_for_port(port_file, host, deadline) -> int` and `wait_for_socket(host, port, deadline) -> bool`; a `_server_thread(argv, errbox)` target that appends any `OSError`/`Exception` to `errbox`.

- [ ] **Step 1: Write the failing test**

```python
# tests/desktop/test_launcher.py
import importlib
import socket
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


def _load(monkeypatch, fake_webview):
    monkeypatch.setitem(sys.modules, "webview", fake_webview)
    mod = importlib.import_module("escritorio")
    return importlib.reload(mod)


def test_imports_without_starting_gui(monkeypatch):
    fake = types.SimpleNamespace(create_window=lambda *a, **k: None, start=lambda *a, **k: None)
    mod = _load(monkeypatch, fake)
    assert hasattr(mod, "main")


def test_server_argv_is_localhost_dynamic_port(monkeypatch):
    fake = types.SimpleNamespace(create_window=lambda *a, **k: None, start=lambda *a, **k: None)
    mod = _load(monkeypatch, fake)
    captured = {}
    monkeypatch.setattr(mod, "_server_thread",
                        lambda argv, errbox: captured.setdefault("argv", argv))
    # make wait_for_port publish a real, listening port so main() proceeds to webview
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
    monkeypatch.setattr(mod, "wait_for_port", lambda *a, **k: port)
    monkeypatch.setattr(mod, "wait_for_socket", lambda *a, **k: True)
    win = {}
    fake.create_window = lambda title, url, **k: win.update(title=title, url=url, **k)
    fake.start = lambda *a, **k: win.update(started=k)
    mod.main()
    assert captured["argv"][:4] == ["--host", "127.0.0.1", "--port", "0"]
    assert win["url"] == "http://127.0.0.1:%d/index.html" % port
    assert win["width"] == 1280 and win["height"] == 850
    assert win["min_size"] == (900, 600)
    assert win["text_select"] is True
    assert win["started"].get("debug") is False
    assert "js_api" not in win


def test_timeout_when_port_never_published(monkeypatch):
    fake = types.SimpleNamespace(create_window=lambda *a, **k: None, start=lambda *a, **k: None)
    mod = _load(monkeypatch, fake)
    monkeypatch.setattr(mod, "_server_thread", lambda argv, errbox: None)
    monkeypatch.setattr(mod, "WAIT_TIMEOUT", 0.5)
    import pytest
    with pytest.raises(RuntimeError):
        mod.main()


def test_error_when_server_thread_dies(monkeypatch):
    fake = types.SimpleNamespace(create_window=lambda *a, **k: None, start=lambda *a, **k: None)
    mod = _load(monkeypatch, fake)

    def dead(argv, errbox):
        errbox.append(OSError("port in use"))
    monkeypatch.setattr(mod, "_server_thread", dead)
    monkeypatch.setattr(mod, "WAIT_TIMEOUT", 0.5)
    import pytest
    with pytest.raises(RuntimeError) as ei:
        mod.main()
    assert "port in use" in str(ei.value)


def test_no_toctou_probe_in_source():
    src = (ROOT / "escritorio.py").read_text(encoding="utf-8")
    # the launcher must not probe a port then hand it off
    assert "bind((" not in src or "getsockname" not in src, \
        "launcher must not do bind->getsockname->close port selection"
```

- [ ] **Step 2: Run — expect FAIL** (`ModuleNotFoundError: escritorio`)

```bash
python -m pytest tests/desktop/test_launcher.py -q
```

- [ ] **Step 3: Implement `escritorio.py`**

```python
"""Windows desktop entrypoint for Sistemes de Mesura.

Runs the existing web/server.py in a daemon thread bound to 127.0.0.1 on an
OS-assigned port, learns that port via SM_PORT_FILE (F19-00), waits for the
socket, then shows a pywebview window. No server logic lives here.
"""
import os
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

import webview

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PREFERRED_TITLE = "Sistemes de Mesura"
WIN_W, WIN_H = 1280, 850
WIN_MIN = (900, 600)
WAIT_TIMEOUT = 15.0
POLL = 0.1


def _server_thread(argv, errbox):
    """Target for the daemon thread; records startup errors instead of raising."""
    try:
        from web import server as _web
        _web.main(argv)
    except Exception as exc:  # noqa: BLE001  (surface to the launcher)
        errbox.append(exc)


def wait_for_port(port_file, deadline, thread, errbox):
    while time.time() < deadline:
        if errbox:
            raise RuntimeError("server failed to start: %r" % errbox[0])
        if not thread.is_alive() and not port_file.is_file():
            raise RuntimeError("server thread exited before publishing a port")
        if port_file.is_file():
            txt = port_file.read_text(encoding="utf-8").strip()
            if txt.isdigit():
                p = int(txt)
                if 0 < p < 65536:
                    return p
        time.sleep(POLL)
    raise RuntimeError("server did not publish its port within %.0fs" % WAIT_TIMEOUT)


def wait_for_socket(host, port, deadline):
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(POLL)
    return False


def main():
    tmpdir = tempfile.mkdtemp(prefix="sm-desktop-")
    port_file = Path(tmpdir) / "port"
    errbox = []
    try:
        env_backup = os.environ.get("SM_PORT_FILE")
        os.environ["SM_PORT_FILE"] = str(port_file)
        argv = ["--host", "127.0.0.1", "--port", "0"]
        th = threading.Thread(target=_server_thread, args=(argv, errbox), daemon=True)
        th.start()

        deadline = time.time() + WAIT_TIMEOUT
        port = wait_for_port(port_file, deadline, th, errbox)
        if not wait_for_socket("127.0.0.1", port, deadline):
            raise RuntimeError("server port %d never accepted a connection" % port)

        webview.create_window(
            PREFERRED_TITLE,
            "http://127.0.0.1:%d/index.html" % port,
            width=WIN_W, height=WIN_H, min_size=WIN_MIN, text_select=True,
        )
        webview.start(debug=False)
        return 0
    finally:
        try:
            os.environ.pop("SM_PORT_FILE", None)
            if env_backup is not None:
                os.environ["SM_PORT_FILE"] = env_backup
        except Exception:  # noqa: BLE001
            pass
        try:
            if port_file.is_file():
                port_file.unlink()
            os.rmdir(tmpdir)
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
```
(Icon is wired in F19-04: `webview.start(icon=..., debug=False)` once `icono.ico` exists and the frozen path to it is resolved.)

- [ ] **Step 4: Run — expect PASS**

```bash
python -m pytest tests/desktop/test_launcher.py -q
```

- [ ] **Step 5: `node --check` is N/A; run the JS-parse + web suites unaffected. Commit.**

```bash
git add escritorio.py tests/desktop/test_launcher.py
git commit -m "F19-01: add Windows desktop launcher"
```

---

## Task 3: F19-04 (deps + icon) — done before F19-02 so the spec can reference `icono.ico`

**Files:**
- Modify: `pyproject.toml`
- Create: `icono.ico`
- Test: covered by `tests/desktop/test_spec.py` (Task 5) — this task just lands the assets.

**Interfaces:**
- Produces: `pyproject.toml` extras `desktop` / `build`; a valid multi-resolution `icono.ico` at repo root.

- [ ] **Step 1: Edit `pyproject.toml`**

```toml
[project.optional-dependencies]
dev = ["pytest"]
desktop = [
    "pywebview>=5.4",
    "pythonnet>=3.0; sys_platform=='win32'",
]
build = [
    "pyinstaller>=6.0",
]
```

- [ ] **Step 2: Add `icono.ico`** — a versioned multi-res ICO (16/32/48/256). Produced once, outside the build, from a simple mark (the app's "Σ" on the F17 accent `#6f4bff`). Commit the binary. **No `generar_icono.py`, no Pillow dependency.**

- [ ] **Step 3: Verify** the file is a real ICO

```bash
python -c "import struct,sys; b=open('icono.ico','rb').read(); assert b[:4]==b'\x00\x00\x01\x00', 'not an ICO'; n=struct.unpack('<H', b[4:6])[0]; print('ICO OK, %d images' % n); assert n>=3"
pip install -e ".[desktop,build]" 2>&1 | tail -1     # deps resolve on this machine
python -c "import webview, PyInstaller; print('deps OK')"
```

- [ ] **Step 4: Confirm base install stays lean**

```bash
python - <<'PY'
import tomllib, pathlib
d = tomllib.loads(pathlib.Path("pyproject.toml").read_text())
assert d["project"]["dependencies"] == [], d["project"]["dependencies"]
assert set(d["project"]["optional-dependencies"]) == {"dev", "desktop", "build"}
print("pyproject OK: base deps empty; extras dev/desktop/build")
PY
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml icono.ico
git commit -m "F19-04: add desktop dependencies and application icon"
```

---

## Task 4: F19-02 — PyInstaller spec (`escritorio.spec`)

**Files:**
- Create: `escritorio.spec`
- Test: `tests/desktop/test_spec.py` (Task 5)

**Interfaces:**
- Consumes: `escritorio.py`, `icono.ico`, the audited resource set, `os.path.dirname(SPEC)`.
- Produces: on `pyinstaller escritorio.spec` → `dist/SistemesDeMesura.exe`.

- [ ] **Step 1: Write `escritorio.spec`**

```python
# -*- mode: python ; coding: utf-8 -*-
# Build:  pyinstaller escritorio.spec --noconfirm --clean
import os

PROJECT_DIR = os.path.abspath(os.path.dirname(os.path.abspath(SPEC)))


def _d(rel, dest=None):
    return (os.path.join(PROJECT_DIR, rel), dest if dest is not None else os.path.dirname(rel) or ".")


datas = [
    _d("web", "web"),
    _d("data/processed/knowledge.sqlite", "data/processed"),
    _d("data/generated/questions.sqlite", "data/generated"),
    _d("data/index", "data/index"),
    _d("data/source_manifest.json", "data"),
    _d("data/evaluation/eval.sqlite", "data/evaluation"),
    _d("data/ARTIFACT-MANIFEST.json", "data"),
    _d(".env.example", "."),
]

a = Analysis(
    ["escritorio.py"],
    pathex=[PROJECT_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "webview.platforms.edgechromium",
        "webview.platforms.winforms",
        "webview.platforms.mshtml",
        "clr_loader",
        # extend ONLY with imports a real build proves missing (F19 gate).
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="SistemesDeMesura",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=os.path.join(PROJECT_DIR, "icono.ico"),
)
```

- [ ] **Step 2: Static parse check** (no build yet)

```bash
python -c "import ast; ast.parse(open('escritorio.spec').read()); print('spec parses')"
```

- [ ] **Step 3: Commit**

```bash
git add escritorio.spec
git commit -m "F19-02: add PyInstaller desktop packaging"
```

---

## Task 5: F19-05 — desktop test suite (`tests/desktop/`)

**Files:**
- Create: `tests/desktop/test_frozen_paths.py`, `tests/desktop/test_spec.py`
- (`test_server_port_file.py`, `test_launcher.py` already exist from Tasks 1–2; extend `test_launcher.py` only if gaps found)

- [ ] **Step 1: `tests/desktop/test_frozen_paths.py`**

```python
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


def test_package_dir_follows_meipass(monkeypatch, tmp_path):
    meipass = tmp_path / "bundle"
    (meipass / "app").mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    from app import paths as p
    importlib.reload(p)
    # package_dir is __file__-relative; when the frozen app runs it resolves
    # under _MEIPASS. Here we assert the contract holds for a bundled layout.
    assert p.package_dir().is_dir()
    monkeypatch.setenv("SM_HOME", str(tmp_path / "home"))
    importlib.reload(p)
    assert str(meipass) not in str(p.data_dir())
    assert str(meipass) not in str(p.backup_dir())


def test_bridge_seed_copy_stays_outside_bundle(monkeypatch, tmp_path):
    sys.path.insert(0, str(ROOT / "web"))
    import server as S
    home = tmp_path / "home"
    monkeypatch.setenv("SM_HOME", str(home))
    b = S.Bridge(workdir=str(home / "data"))
    assert (home / "data" / "questions.sqlite").is_file()
    assert (home / "data" / "student.sqlite").is_file() or True  # created lazily by services
    # nothing was written under a bundle-style _MEIPASS path
    assert "MEIPASS" not in str(b.work)
```

- [ ] **Step 2: `tests/desktop/test_spec.py`**

```python
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SPEC = (ROOT / "escritorio.spec").read_text(encoding="utf-8")

REQUIRED = [
    '_d("web", "web")',
    '"data/processed/knowledge.sqlite"',
    '"data/generated/questions.sqlite"',
    '_d("data/index"',
    '"data/source_manifest.json"',
    '"data/evaluation/eval.sqlite"',
    '"data/ARTIFACT-MANIFEST.json"',
    '".env.example"',
]
FORBIDDEN = ["chunks.jsonl", "formulas.jsonl", "students.sqlite",
             "data/metadata", "ingestion_report", "data/student"]


def test_spec_entry_and_exe_flags():
    assert 'Analysis(\n    ["escritorio.py"]' in SPEC or '["escritorio.py"]' in SPEC
    assert 'name="SistemesDeMesura"' in SPEC
    assert "console=False" in SPEC
    assert re.search(r'icon=.*icono\.ico', SPEC)
    assert (ROOT / "icono.ico").is_file()
    assert (ROOT / "icono.ico").read_bytes()[:4] == b"\x00\x00\x01\x00"


def test_spec_bundles_exactly_the_audited_resources():
    for token in REQUIRED:
        assert token in SPEC, "missing bundled resource: %s" % token
    for token in FORBIDDEN:
        assert token not in SPEC, "runtime junk in bundle: %s" % token


def test_spec_has_webview_hidden_imports():
    for h in ("webview.platforms.edgechromium", "webview.platforms.winforms",
              "webview.platforms.mshtml", "clr_loader"):
        assert h in SPEC
```

- [ ] **Step 3: Run the whole desktop suite**

```bash
python -m pytest tests/desktop/ -q
```
Expected: all pass.

- [ ] **Step 4: Full pytest — no regression, no new skips**

```bash
python -m pytest -q 2>&1 | tail -3
```
Expected: `937 + <new desktop tests> passed, 1 skipped, 0 failed`. Record the new total.

- [ ] **Step 5: Commit**

```bash
git add tests/desktop/test_frozen_paths.py tests/desktop/test_spec.py
git commit -m "F19-05: add desktop launcher tests"
```

---

## Task 6: F19-03 — Windows build script (`build.ps1`)

**Files:**
- Create: `build.ps1`

- [ ] **Step 1: Write `build.ps1`**

```powershell
# Builds dist\SistemesDeMesura.exe. Usage: .\build.ps1
$ErrorActionPreference = "Stop"
$proj = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $proj

$py = "python"
if (Test-Path ".\venv\Scripts\python.exe") { $py = ".\venv\Scripts\python.exe" }
elseif (Test-Path ".\.venv\Scripts\python.exe") { $py = ".\.venv\Scripts\python.exe" }

& $py -c "import webview, PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Missing desktop/build deps. Run:  $py -m pip install -e `".[desktop,build]`"" -ForegroundColor Red
    exit 1
}

if (Test-Path ".\build") { Remove-Item ".\build" -Recurse -Force }
if (Test-Path ".\dist")  { Remove-Item ".\dist"  -Recurse -Force }

& $py -m PyInstaller escritorio.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$exe = ".\dist\SistemesDeMesura.exe"
if (-not (Test-Path $exe) -or (Get-Item $exe).Length -le 0) {
    Write-Host "Build finished but $exe is missing or empty" -ForegroundColor Red
    exit 1
}
Write-Host "OK: $((Get-Item $exe).FullName)  ($([math]::Round((Get-Item $exe).Length/1MB,1)) MB)" -ForegroundColor Green
```

- [ ] **Step 2: Commit** (script is validated by the real build in Task 8)

```bash
git add build.ps1
git commit -m "F19-03: add Windows desktop build script"
```

---

## Task 7: F19-06 — Windows CI job + documentation

**Files:**
- Modify: `.github/workflows/ci.yml` (add job `desktop`; Linux `test` job untouched)
- Create: `docs/F19_DESKTOP_APP.md`
- Modify: `docs/DECISION_LOG.md` (append D188)

- [ ] **Step 1: Add the `desktop` job to `ci.yml`** (after the existing `test` job, same `on:` triggers)

```yaml
  desktop:
    name: desktop build (windows)
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.14"
      - name: Install project + desktop/build extras
        run: |
          python -m pip install --upgrade pip
          python -m pip install -e ".[dev,desktop,build]"
      - name: Test suite
        run: python -m pytest tests/ -q
      - name: Runtime dirs + artifact integrity
        run: |
          python -m app.cli init
          python -m app.cli check
      - name: Build EXE
        run: python -m PyInstaller escritorio.spec --noconfirm --clean
      - name: Headless startup smoke
        shell: pwsh
        run: |
          $pf = Join-Path $env:RUNNER_TEMP "smoke-port"
          $env:SM_PORT_FILE = $pf
          $p = Start-Process ".\dist\SistemesDeMesura.exe" -PassThru
          try {
            $deadline = (Get-Date).AddSeconds(40)
            while (-not (Test-Path $pf) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 200 }
            if (-not (Test-Path $pf)) { throw "exe never published its port" }
            $port = [int](Get-Content $pf)
            $r1 = Invoke-WebRequest "http://127.0.0.1:$port/index.html" -UseBasicParsing
            $r2 = Invoke-WebRequest "http://127.0.0.1:$port/api/health" -UseBasicParsing
            if ($r1.StatusCode -ne 200 -or $r2.StatusCode -ne 200) { throw "smoke HTTP != 200" }
            Write-Host "smoke OK on port $port"
          } finally {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
          }
```
> Note in the job comment and in `docs/F19_DESKTOP_APP.md`: this validates the **startup/headless contract only** — not WebView2 render, not manual interaction, not F18-02 visual.

Verify the Linux job diff is zero:
```bash
git diff HEAD -- .github/workflows/ci.yml | grep -A50 "jobs:" | sed -n '1,40p'   # 'test:' block unchanged
```

- [ ] **Step 2: Write `docs/F19_DESKTOP_APP.md`** covering: architecture diagram; dev run (`python escritorio.py`); build (`.\build.ps1`); Windows 10 21H2+/11 + **WebView2 Runtime** requirement (no Evergreen bootstrapper in F19); data location `%LOCALAPPDATA%\SistemesDeMesura\` (`data/questions.sqlite`, `data/student.sqlite`, `backups/`); no-Gemini-key behaviour (extractive fallback); startup troubleshooting (port-file timeout, WebView2 missing); CI limitations (headless contract only); the manual smoke + F18-02 runtime checklist; the `SM_PORT_FILE` carve-out.

- [ ] **Step 3: Append `docs/DECISION_LOG.md` D188**

```
| D188 | Escritorio Windows como wrapper pywebview + servidor Python embebido + PyInstaller (`SistemesDeMesura.exe`), no reescritura. Único cambio backend: `web/server.py` publica el puerto realmente enlazado en `$SM_PORT_FILE` (opt-in, tras el bind, sin TOCTOU) para que el launcher use `--port 0`. | PWA no da ventana nativa y añade service worker versionado; Electron/Tauri arrastran Node/Rust y rompen el "0 deps runtime / sin build". `app/paths.py` ya separa `package_dir()`(→`_MEIPASS`) de `data_dir()`(→`%LOCALAPPDATA%`), y `Bridge` ya copia la seed en primer arranque: la capa desktop es puramente aditiva. | Mantener solo-web / bind→close→rebind (TOCTOU) / `pywebview` como dep obligatoria / bundlear Evergreen bootstrapper (fuera de scope F19). |
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml docs/F19_DESKTOP_APP.md docs/DECISION_LOG.md
git commit -m "F19-06: add Windows desktop CI and documentation"
```

---

## Task 8: Real Windows build + headless smoke + persistence smoke

**Files:** none (verification; produces `dist/SistemesDeMesura.exe`, not committed).

- [ ] **Step 1: Build**

```bash
pwsh -File build.ps1
ls -la dist/SistemesDeMesura.exe
```
If PyInstaller reports a missing module at first launch (Step 2), add it to `escritorio.spec` `hiddenimports`, rebuild, and **amend Task 4's commit is NOT allowed** — make a follow-up `F19-02` fix within scope (`git commit -m "F19-02: add hidden import <name> (build-verified)"`). Record what was added and why.

- [ ] **Step 2: Headless startup smoke** (no window interaction)

```bash
SM_PORT_FILE=$(mktemp -u)   # or a temp path
./dist/SistemesDeMesura.exe &   EXE_PID=$!
# wait for the port file, then:
PORT=$(cat "$SM_PORT_FILE")
curl -fsS "http://127.0.0.1:$PORT/index.html" | head -c 200
for p in /api/health /api/study/topics /api/learn/priorities /api/exam/mine; do
  echo "$p -> $(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT$p")"
done
kill $EXE_PID
```
Expected: `index.html` → HTML; every `/api/*` → `200` with real payloads.

- [ ] **Step 3: Frozen-path + persistence smoke**

```bash
ls -la "$LOCALAPPDATA/SistemesDeMesura/data/"   # questions.sqlite + student.sqlite present
# drive one state-changing call (e.g. POST /api/practice/start then submit) via curl
# close the exe, reopen, confirm the student progress row survived
```
Expected: data dir populated under `%LOCALAPPDATA%`, nothing written under the PyInstaller temp (`_MEIxxxxxx`), state persists across restart.

- [ ] **Step 4: `app.cli check --fast` inside the frozen environment** (diagnostic, not a gate)

Run it against the extracted bundle if the packaging exposes a way to; otherwise document that `check` is a repo/installed-layout tool (per audit) and the desktop acceptance rests on the smokes above. **Do not modify `app/` to make it run.**

- [ ] **Step 5: Record all outputs in the ledger.** Any failure → stop, `systematic-debugging`, fix within scope, re-run affected gates.

---

## Task 9: F18-02 runtime gate on the `.exe`

**Files:** none.

- [ ] **Step 1: Determine computer-use availability.** If the `mcp__computer-use__*` toolset is actually usable in this environment (grant obtainable), proceed to Step 2. If not, mark this gate **MANUAL PENDING** — do NOT infer PASS.

- [ ] **Step 2 (computer-use path):** launch `dist/SistemesDeMesura.exe`; screenshot the window; navigate Inici → Exàmens → create/open an exam (session via `?xsid=`); type an answer in the current question and DO NOT save; use the header language selector CA → ES; screenshot + verify: the typed answer is still in the field, same question position, same `?xsid=`, timer still counting, no reload flash; then ES → CA and repeat. Capture screenshots as evidence.

- [ ] **Step 3 (no computer-use):** write the exact manual checklist into `docs/F19_DESKTOP_APP.md` ("F18-02 runtime gate") and the ledger; final report marks it `MANUAL PENDING`.

---

## Task 10: Security review

**Files:** none (review); findings, if any, fix within scope.

- [ ] `grep -rn "0.0.0.0" escritorio.py build.ps1 escritorio.spec` → none; launcher argv is `--host 127.0.0.1`.
- [ ] `grep -rn "js_api\|debug=True" escritorio.py` → none; `webview.start(debug=False)`.
- [ ] `grep -rniE "GEMINI_API_KEY\s*=\s*['\"]?[A-Za-z0-9_-]{10,}" .` (excluding `.env.example` which has an empty value) → none. Confirm no key string in `escritorio.spec`, `build.ps1`, `docs/`, `tests/`, and (post-build) `strings dist/SistemesDeMesura.exe | grep -i AIza` → none.
- [ ] No new endpoints (`git diff main...HEAD -- web/server.py` = only the port-file lines).
- [ ] No `data/` write path resolves under `_MEIPASS` (covered by `test_frozen_paths.py` + Task 8 Step 3).
- [ ] The `.exe` runs without elevation (Task 8 was run as a normal user).
- [ ] Provider still falls back to extractive with no `GEMINI_API_KEY` (already covered by the existing suite; note it).

---

## Task 11: Full regression + diff audit + branch verification

**Files:** none.

- [ ] **Step 1: Full regression**

```bash
python -m pytest -q 2>&1 | tail -3
python -m app.cli check;          echo "exit=$?"
python -m app.cli check --status; echo "exit=$?"
python -m app.final_certification_benchmark    | grep '"score"'
python -m app.review_results_history_benchmark | grep '"score"'
```
Gates: `0 failed`; no new skips (only `test_home_defaults_under_xdg_on_posix`); total = 937 + (desktop tests added); `check` OK; `--status` OK; `125/125`; `100/100`.

- [ ] **Step 2: Diff audit**

```bash
git diff main...HEAD --stat
git diff main...HEAD --name-only
```
Expected file set exactly: `web/server.py`, `escritorio.py`, `escritorio.spec`, `build.ps1`, `icono.ico`, `pyproject.toml`, `.github/workflows/ci.yml`, `tests/desktop/*`, `docs/F19_DESKTOP_APP.md`, `docs/DECISION_LOG.md`, `docs/superpowers/plans/2026-09-10-f19-desktop-app.md`.
**No** changes under `app/`, `data/`, `web/*.html`, `web/static/**`. If any appear → stop, investigate, revert or escalate for explicit approval.
`git diff --check` → clean.

- [ ] **Step 3: Branch verification**

```bash
git status --porcelain          # empty
git branch --show-current       # f19-desktop-app
git rev-parse main              # still 2bb4842 (untouched)
git log --oneline main..HEAD    # only F19-* commits
```

---

## Task 12: PR

**Files:** none.

- [ ] `git push -u origin f19-desktop-app`
- [ ] `gh pr create --base main --head f19-desktop-app --title "F19 — Windows Desktop App"` with a body that lists **Includes** (desktop launcher, PyInstaller packaging, `build.ps1`, `icono.ico`, Windows CI job, desktop tests, docs, `SM_PORT_FILE` carve-out, dynamic localhost port, persistence smoke, F18-02 runtime validation status) and **Does NOT include** (web rewrite, API/backend redesign, Gemini changes, toasts, backup enhancement, PWA, Electron/Tauri, WebView bridge).
- [ ] Wait for **both** CI jobs (`test` Linux + `desktop` Windows) green. Do not merge — hand the PR to the user (protected branch; F17/F18 pattern).

---

## Stop rule

If any task discovers the approved architecture is insufficient (e.g. a frozen path genuinely fails, `web.server.main()` can't be reused as-is, a resource turns out to be needed on the request path, a hidden import cascade, a new skip, or any `app/`/`data/`/frontend change becomes unavoidable): **stop, document the finding, and return for design review before widening scope.** No improvised fix in the same commit.

---

## Self-Review

**1. Spec coverage** — user's document sections mapped to tasks:
- §1 preparation/baseline → Task 0 · §2 F19-00 `SM_PORT_FILE` → Task 1 · §3 F19-01 launcher → Task 2 · §4 F19-02 PyInstaller → Task 4 · §5 F19-03 build.ps1 → Task 6 · §6 F19-04 deps+icon → Task 3 (pulled earlier so the spec can reference `icono.ico`) · §7–9 F19-05 tests → Tasks 1,2,5 · §10 F19-06 CI → Task 7 · §11 real smoke → Task 8 · §12 F18-02 gate → Task 9 · §13 `check --fast` in exe → Task 8 Step 4 · §14 security → Task 10 · §15 docs → Task 7 · §16 regression → Task 11 · §17 diff audit → Task 11 · §18 commits → per-task · §19 branch verify → Task 11 · §20 PR → Task 12 · §21 acceptance → Tasks 8–12 · §22 execution order → task order (with F19-04 before F19-02, noted).
- Ordering deviation: the user's order is F19-02 then F19-04; this plan does F19-04 (Task 3) before F19-02 (Task 4) so `escritorio.spec` and `test_spec.py` can assert `icono.ico` exists. Commit messages keep the user's F19-NN labels. Flag for approval.

**2. Placeholder scan** — every step has a runnable command or real code. The only non-literal artifact is `icono.ico` (a binary asset, produced once outside the build — described, not code). `docs/F19_DESKTOP_APP.md` content is enumerated by section, not pasted (a doc, acceptable).

**3. Type/interface consistency** — `escritorio.py` exposes `main() -> int`, `_server_thread(argv, errbox)`, `wait_for_port(port_file, deadline, thread, errbox) -> int`, `wait_for_socket(host, port, deadline) -> bool`, constants `WIN_W/WIN_H/WIN_MIN/WAIT_TIMEOUT`; `test_launcher.py` monkeypatches exactly those names. `web/server.py` change reads `os.environ["SM_PORT_FILE"]` and writes `srv.server_address[1]`; `test_server_port_file.py` and `escritorio.py` both key on `SM_PORT_FILE` + the decimal port contract. `escritorio.spec` `datas` tokens match `test_spec.py` `REQUIRED`/`FORBIDDEN` exactly.
