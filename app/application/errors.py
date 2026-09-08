"""AppError: vocabulario cerrado de errores de aplicación (B2.12).

Fail-loud: lo inesperado propaga sin normalizar. Nunca incluye secretos,
CoT, SQL, prompts ni answer keys (mensajes seguros por construcción).
"""
from __future__ import annotations


CODES = ("USER_ERROR", "VALIDATION_ERROR", "NOT_FOUND", "STATE_ERROR",
         "KNOWLEDGE_ERROR", "RETRIEVAL_ERROR", "GENERATION_ERROR",
         "CORRECTION_ERROR", "PERSISTENCE_ERROR", "POLICY_ERROR",
         "INTERNAL_ERROR")


class AppError(Exception):
    def __init__(self, code: str, message: str, cause: str = "") -> None:
        if code not in CODES:
            raise ValueError("código AppError desconocido: %r" % code)
        super().__init__("[%s] %s" % (code, message))
        self.code = code
        self.message = message
        self.cause = cause

    def to_dict(self) -> dict:
        return {"ok": False, "code": self.code, "message": self.message}


# Marcadores de servicios existentes → código AppError. Orden importa:
# lo específico antes que lo genérico. Lo no listado propaga intacto.
_MAPPINGS: tuple[tuple[str, str], ...] = (
    ("otro estudiante", "NOT_FOUND"),
    ("inexistente o ajena", "NOT_FOUND"),
    ("inexistente:", "NOT_FOUND"),
    ("question not found", "NOT_FOUND"),
    ("no existe", "NOT_FOUND"),
    ("RESULT_NOT_AVAILABLE", "STATE_ERROR"),
    ("REVIEW_NOT_AVAILABLE", "STATE_ERROR"),
    ("STEM_NOT_AVAILABLE", "STATE_ERROR"),
    ("MASTERY_NOT_AVAILABLE", "STATE_ERROR"),
    ("transicion invalida", "STATE_ERROR"),
    ("solo se califica", "STATE_ERROR"),
    ("GRADING_INCOMPLETE", "STATE_ERROR"),
    ("NO-GO:", "INTERNAL_ERROR"),
    ("no se admite respuesta en estado", "STATE_ERROR"),
    ("pregunta solo disponible en", "STATE_ERROR"),
    ("examen no READY", "STATE_ERROR"),
    ("sin pregunta activa", "STATE_ERROR"),
    ("SNAPSHOT_INVALID", "STATE_ERROR"),
    ("answer debe ser str", "VALIDATION_ERROR"),
    ("GRADING_INCOMPLETE", "STATE_ERROR"),
    ("SNAPSHOT_INVALID", "STATE_ERROR"),
    ("EXAM NOT READY", "STATE_ERROR"),
    ("REVIEW_POLICY_NOT_FOUND", "POLICY_ERROR"),
    ("policy debe ser", "POLICY_ERROR"),
    ("blueprint invalido", "VALIDATION_ERROR"),
    ("ABSTAIN", "VALIDATION_ERROR"),
    ("reasoning_unavailable", "GENERATION_ERROR"),
    ("NO_EVIDENCE", "RETRIEVAL_ERROR"),
    ("INSUFFICIENT_EVIDENCE", "RETRIEVAL_ERROR"),
    ("FORMULA_NOT_FOUND", "KNOWLEDGE_ERROR"),
    ("EVIDENCE_TOPIC_MISMATCH", "RETRIEVAL_ERROR"),
)


def map_error(exc: Exception) -> AppError:
    """Traduce errores conocidos; lo demás se propaga sin tocar."""
    if isinstance(exc, AppError):
        return exc
    text = str(exc)
    for marker, code in _MAPPINGS:
        if marker in text:
            return AppError(code, text[:300], cause=type(exc).__name__)
    raise exc


def guard(fn, *args, **kwargs):
    """Frontera de workflow: AppError pasa; ExamError se mapea;
    sqlite → PERSISTENCE_ERROR; lo demás propaga (fail-loud)."""
    import sqlite3
    from app.exam.models import ExamError
    try:
        return fn(*args, **kwargs)
    except AppError:
        raise
    except ExamError as e:
        raise map_error(e)
    except KeyError as e:
        raise map_error(e)
    except sqlite3.Error as e:
        raise AppError("PERSISTENCE_ERROR",
                       "persistencia: %s" % type(e).__name__)

