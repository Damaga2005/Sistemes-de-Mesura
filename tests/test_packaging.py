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
