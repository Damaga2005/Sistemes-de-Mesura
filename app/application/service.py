"""ApplicationService: fachada delgada de orquestación (B3.5).

Crea contexto/sesión, valida frontera, delega, normaliza errores.
NO recupera conocimiento, corrige, genera, decide ni puntúa.
"""
from __future__ import annotations

from .context import ApplicationContext
from .errors import AppError, map_error
from .session import ApplicationSession, create_session


class ApplicationService:
    def __init__(self, *, retriever=None, reasoning=None, examiner=None,
                 correction=None, students=None, adaptive=None,
                 exam_sessions=None, exam_grading=None, exam_review=None,
                 kb_path: str = "") -> None:
        self.retriever = retriever
        self.reasoning = reasoning
        self.examiner = examiner
        self.correction = correction
        self.students = students
        self.adaptive = adaptive
        self.exam_sessions = exam_sessions
        self.exam_grading = exam_grading
        self.exam_review = exam_review
        self.kb_path = kb_path

    # ---------- contexto y sesión ----------
    def create_context(self, student_id: str, workflow: str = "TUTOR",
                       language: str = "ca", session_id: str = "",
                       reference: dict | None = None,
                       policies: dict | None = None) -> ApplicationContext:
        if not isinstance(student_id, str) or not student_id:
            raise AppError("VALIDATION_ERROR", "student_id inválido")
        if not isinstance(workflow, str) or not isinstance(language, str) \
                or not isinstance(session_id, str):
            raise AppError("VALIDATION_ERROR", "tipos de contexto inválidos")
        if reference is not None and not isinstance(reference, dict):
            raise AppError("VALIDATION_ERROR", "reference inválida")
        if policies is not None and not isinstance(policies, dict):
            raise AppError("VALIDATION_ERROR", "policies inválidas")
        return ApplicationContext.create(
            student_id, workflow, language, session_id, reference or {},
            policies or {})

    def create_session(self, student_id: str, workflow: str,
                       language: str = "ca",
                       nonce: str = "") -> ApplicationSession:
        return create_session(student_id, workflow, language, nonce)

    # ---------- frontera ----------
    @staticmethod
    def check_scope(ctx: ApplicationContext, owner_id: str,
                    resource: str = "recurso") -> None:
        """El recurso debe pertenecer al estudiante del contexto."""
        if ctx.technical_student_id != owner_id:
            raise AppError("NOT_FOUND",
                           "%s no disponible para este estudiante" % resource)

    @staticmethod
    def require(services: dict, *names: str) -> None:
        missing = [n for n in names if services.get(n) is None]
        if missing:
            raise AppError("INTERNAL_ERROR",
                           "servicio no configurado: %s" % ",".join(missing))

    def normalize(self, exc: Exception) -> AppError:
        return map_error(exc)
