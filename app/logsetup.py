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
