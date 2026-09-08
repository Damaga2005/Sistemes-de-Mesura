"""ApplicationSession: orquestación efímera (B2.3/B3.3). Sin tabla, sin DB."""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from .errors import AppError

SESSION_STATUSES = ("ACTIVE", "COMPLETED", "ABANDONED")
SESSION_TRANSITIONS = {"ACTIVE": ("COMPLETED", "ABANDONED"),
                       "COMPLETED": (), "ABANDONED": ()}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sid(student_id: str, workflow: str, nonce: str) -> str:
    return "apps-" + hashlib.sha256(
        ("%s|%s|%s" % (student_id, workflow, nonce)).encode()
    ).hexdigest()[:12]


@dataclass
class ApplicationSession:
    session_id: str
    student_id: str
    workflow: str
    status: str = "ACTIVE"
    language: str = "ca"
    active_reference: dict = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def transition(self, target: str) -> str:
        if target not in SESSION_TRANSITIONS.get(self.status, ()):
            raise AppError("STATE_ERROR",
                           "transición inválida: %s -> %s"
                           % (self.status, target))
        self.status = target
        self.updated_at = _now()
        return target

    def touch(self, active_reference: dict | None = None) -> None:
        if self.status != "ACTIVE":
            raise AppError("STATE_ERROR",
                           "sesión no activa: %s" % self.status)
        if active_reference is not None:
            if not isinstance(active_reference, dict):
                raise AppError("VALIDATION_ERROR", "reference inválida")
            self.active_reference = active_reference
        self.updated_at = _now()

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "ApplicationSession":
        s = ApplicationSession(
            session_id=d["session_id"], student_id=d["student_id"],
            workflow=d["workflow"], status=d.get("status", "ACTIVE"),
            language=d.get("language", "ca"),
            active_reference=d.get("active_reference", {}),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""))
        if s.workflow not in ("TUTOR", "PRACTICE", "ADAPTIVE_PRACTICE",
                              "EXAM", "REVIEW"):
            raise AppError("VALIDATION_ERROR", "workflow desconocido")
        if s.status not in SESSION_STATUSES:
            raise AppError("VALIDATION_ERROR", "estado desconocido")
        return s


def create_session(student_id: str, workflow: str, language: str = "ca",
                   nonce: str = "") -> ApplicationSession:
    if workflow not in ("TUTOR", "PRACTICE", "ADAPTIVE_PRACTICE", "EXAM",
                        "REVIEW"):
        raise AppError("VALIDATION_ERROR",
                       "workflow desconocido: %r" % (workflow,))
    if language not in ("ca", "es"):
        raise AppError("VALIDATION_ERROR",
                       "idioma no soportado: %r" % (language,))
    if not student_id:
        raise AppError("VALIDATION_ERROR", "student_id vacío o inválido")
    now = _now()
    return ApplicationSession(session_id=_sid(student_id, workflow, nonce),
                              student_id=student_id, workflow=workflow,
                              status="ACTIVE", language=language,
                              created_at=now, updated_at=now)
