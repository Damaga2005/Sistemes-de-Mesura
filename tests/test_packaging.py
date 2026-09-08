"""Contrato F14 de arranque reproducible y configuración portable."""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_project_metadata_declares_portable_web_entrypoint():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "requires-python" in text
    assert "sistemes-web" in text
    assert "web.server:main" in text


def test_web_cli_help_is_available_without_installation():
    result = subprocess.run(
        [sys.executable, "-m", "web.server", "--help"],
        cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0
    assert "--port" in result.stdout
    assert "--data-dir" in result.stdout
    assert "--calendar" in result.stdout


def test_env_example_contains_no_secret_value():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "GEMINI_API_KEY=" in text
    assert "GEMINI_API_KEY=sk-" not in text
    assert "SM_DATA_DIR=" in text


def test_portable_packaging_scripts_are_present_and_safe():
    package = (ROOT / "scripts" / "package.ps1").read_text(encoding="utf-8")
    run = (ROOT / "scripts" / "run-web.ps1").read_text(encoding="utf-8")
    assert "Compress-Archive" in package
    assert "Get-FileHash" in package
    assert "GEMINI_API_KEY" not in package
    assert "web.server" in run
    assert "Remove-Item -Recurse -Force $root" not in package
