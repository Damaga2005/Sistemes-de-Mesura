import os
import subprocess
import sys
from pathlib import Path

import pytest

from app import cli

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _isolate_env():
    # cli.main() calls load_env(), which does os.environ.setdefault(...).
    # Snapshot/restore so `init` tests don't leak SM_* into the rest of the suite.
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)


def test_no_subcommand_prints_help_and_returns_2(capsys):
    assert cli.main([]) == 2
    assert "sistemes" in capsys.readouterr().out.lower()


def test_version_reads_pyproject(capsys):
    assert cli.main(["--version"]) == 0
    out = capsys.readouterr().out.strip()
    # Intent: prints a dotted version string (see task-5 report for the
    # simplification away from the brief's VERSION_MARKER branch).
    assert out.count(".") >= 2


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
    # --source present, --out absent: the default target sits under the package
    # dir. Point package_dir at a plain file so the mkdir probe raises OSError
    # (deterministic; a source checkout's data/ is writable).
    blocker = tmp_path / "pkg"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr(cli._paths, "package_dir", lambda: blocker)
    rc = cli.main(["ingest", "--source", str(tmp_path)])
    assert rc == 2


def test_deprecated_alias_still_runs():
    result = subprocess.run(
        [sys.executable, "-m", "web.server", "--help"],
        cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0
