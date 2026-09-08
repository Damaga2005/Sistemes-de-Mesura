"""Lector determinista del calendario académico versionado.

La fuente es opcional y de solo lectura. No se crean eventos por defecto.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.application.errors import AppError


class CalendarSource:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None

    def read(self) -> dict:
        if self.path is None or not self.path.exists():
            return {
                "events": [], "configured": False,
                "source": "COURSE_SOURCE",
                "message": "No hi ha esdeveniments acadèmics configurats.",
            }
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AppError("VALIDATION_ERROR", "font de calendari invàlida",
                           cause=type(exc).__name__)
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise AppError("VALIDATION_ERROR", "versió de calendari invàlida")
        source_path = payload.get("source_path")
        source_hash = payload.get("source_hash")
        events = payload.get("events")
        if not isinstance(source_path, str) or not source_path.strip():
            raise AppError("VALIDATION_ERROR", "falta source_path")
        if not isinstance(source_hash, str) or not source_hash.strip():
            raise AppError("VALIDATION_ERROR", "falta source_hash")
        if not isinstance(events, list):
            raise AppError("VALIDATION_ERROR", "events invàlids")
        normalized = []
        for event in events:
            if not isinstance(event, dict):
                raise AppError("VALIDATION_ERROR", "esdeveniment invàlid")
            required = ("id", "title", "start", "end", "kind")
            if any(not isinstance(event.get(key), str) or
                   not event.get(key).strip() for key in required):
                raise AppError("VALIDATION_ERROR", "esdeveniment incomplet")
            item = {key: event[key] for key in required}
            for key in ("location", "topic"):
                if key in event:
                    item[key] = event[key]
            item["source_path"] = source_path
            item["source_hash"] = source_hash
            normalized.append(item)
        normalized.sort(key=lambda item: (item["start"], item["id"]))
        return {"events": normalized, "configured": True,
                "source": "COURSE_SOURCE", "source_path": source_path,
                "source_hash": source_hash}
