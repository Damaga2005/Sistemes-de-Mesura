"""ApplicationContext: contexto de ejecución efímero y validado (B2.2/B3.2)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from .errors import AppError

WORKFLOWS = ("TUTOR", "PRACTICE", "ADAPTIVE_PRACTICE", "EXAM", "REVIEW")
LANGUAGES = ("ca", "es")
REFERENCE_KINDS = ("exam", "session", "attempt", "question", "recommendation",
                   "none")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class ApplicationContext:
    technical_student_id: str
    language: str = "ca"
    application_session_id: str = ""
    workflow: str = "TUTOR"
    active_reference: dict = field(default_factory=dict)
    created_at: str = ""
    policy_versions: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.technical_student_id or not isinstance(
                self.technical_student_id, str):
            raise AppError("VALIDATION_ERROR", "student_id vacío o inválido")
        if self.language not in LANGUAGES:
            raise AppError("VALIDATION_ERROR",
                           "idioma no soportado: %r" % (self.language,))
        if self.workflow not in WORKFLOWS:
            raise AppError("VALIDATION_ERROR",
                           "workflow desconocido: %r" % (self.workflow,))
        ref = self.active_reference or {}
        if not isinstance(ref, dict):
            raise AppError("VALIDATION_ERROR", "reference inválida")
        if ref.get("kind", "none") not in REFERENCE_KINDS:
            raise AppError("VALIDATION_ERROR",
                           "reference kind inválido: %r" % (ref.get("kind"),))
        if ref.get("kind", "none") != "none" and not ref.get("id"):
            raise AppError("VALIDATION_ERROR", "reference sin id")

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def create(technical_student_id: str, workflow: str = "TUTOR",
               language: str = "ca",
               application_session_id: str = "",
               active_reference: dict | None = None,
               policy_versions: dict | None = None,
               created_at: str = "") -> "ApplicationContext":
        return ApplicationContext(
            technical_student_id=technical_student_id, language=language,
            application_session_id=application_session_id, workflow=workflow,
            active_reference=active_reference or {},
            created_at=created_at or _now(),
            policy_versions=policy_versions or {})
