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
