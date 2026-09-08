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
