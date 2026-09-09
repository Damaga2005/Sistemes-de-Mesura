import os
from pathlib import Path

import pytest

import app.paths as paths


@pytest.mark.skipif(os.name != "nt",
                    reason="ruta con flavour Windows; pathlib no instancia "
                           "WindowsPath en POSIX aunque se parchee os.name")
def test_home_defaults_under_localappdata_on_windows(monkeypatch):
    monkeypatch.delenv("SM_HOME", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\me\AppData\Local")
    monkeypatch.setattr(paths.os, "name", "nt", raising=False)
    assert paths.home() == Path(r"C:\Users\me\AppData\Local\SistemesDeMesura")


@pytest.mark.skipif(os.name == "nt",
                    reason="rama POSIX de home(); en Windows aplica la de arriba")
def test_home_defaults_under_xdg_on_posix(monkeypatch):
    monkeypatch.delenv("SM_HOME", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/xdg")
    assert paths.home() == Path("/tmp/xdg/sistemes-de-mesura")


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
