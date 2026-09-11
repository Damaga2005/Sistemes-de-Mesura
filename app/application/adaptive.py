"""AdaptivePracticeWorkflow: F6 decide, Examiner genera, F5 registra (B4.3).

Application solo ordena llamadas explícitas (una llamada = una
transición). Sin bucles, sin scheduler, sin decidir prioridad/
dificultad/score/mastery. Sin LLM en adaptación.
"""
from __future__ import annotations

from app.adaptive.models import LearningPathItem
from app.exam.models import stem_view

from .context import ApplicationContext
from .errors import AppError, guard
from .session import ApplicationSession


class AdaptivePracticeWorkflow:
    def __init__(self, app) -> None:
        self.app = app

    @staticmethod
    def _session(session) -> ApplicationSession:
        if isinstance(session, ApplicationSession):
            return session
        if isinstance(session, dict):
            return ApplicationSession.from_dict(session)
        raise AppError("VALIDATION_ERROR", "sesión inválida")

    @staticmethod
    def _own(ctx: ApplicationContext, sess: ApplicationSession) -> None:
        if ctx.technical_student_id != sess.student_id:
            raise AppError("NOT_FOUND",
                           "sesión no disponible para este estudiante")

    def recommend(self, ctx: ApplicationContext, session, *,
                  limit: int = 5, seed: int = 0,
                  mode: str = "PRACTICE") -> dict:
        sess = self._session(session)
        self._own(ctx, sess)
        if not isinstance(limit, int) or limit < 1:
            raise AppError("VALIDATION_ERROR", "limit inválido")
        self.app.require(self.app.__dict__, "adaptive")
        try:
            items = guard(self.app.adaptive.recommend,
                          ctx.technical_student_id, limit=limit, seed=seed,
                          mode=mode)
        except ValueError as e:
            raise AppError("VALIDATION_ERROR", str(e)[:200])
        return {"ok": True, "data": {"session": sess.to_dict(),
                                     "recommendations": [
                                         _project_item(i) for i in items]}}

    def generate(self, ctx: ApplicationContext, session, item: dict,
                 seed: int = 0) -> dict:
        sess = self._session(session)
        self._own(ctx, sess)
        self.app.require(self.app.__dict__, "adaptive", "examiner")
        loop = self.app.adaptive
        try:
            lp = LearningPathItem(**_item_kwargs(item))
        except Exception:
            raise AppError("VALIDATION_ERROR", "item inválido")
        try:
            spec = loop.selector.to_spec(lp, seed=seed)
            q, log = self.app.examiner.generate(
                topic=spec.topic, section=spec.section,
                question_type=spec.type, difficulty=spec.difficulty,
                formula_id=(spec.formula_ids[0] if spec.formula_ids else ""),
                seed=seed)
        except AppError:
            raise
        except Exception as e:  # noqa: BLE001 - frontera generación
            raise AppError("GENERATION_ERROR", str(e)[:300],
                           cause=type(e).__name__)
        if q is None:
            raise AppError("GENERATION_ERROR",
                           "sin pregunta: %s" % str(log.get("rejected", ""))[:200])
        body = q.to_dict() if hasattr(q, "to_dict") else dict(q)
        view = stem_view(body, position=0,
                         question_version=str(body.get("version", "")),
                         points=10.0, required=True,
                         session_id=sess.session_id)
        sess.touch({"kind": "question", "id": view["question_id"]})
        return {"ok": True, "data": {"session": sess.to_dict(),
                                     "question": view, "log": log}}

    def answer(self, ctx: ApplicationContext, session, question_id: str,
               answer: str, attempt_id: str = "") -> dict:
        sess = self._session(session)
        self._own(ctx, sess)
        if not isinstance(question_id, str) or not question_id:
            raise AppError("VALIDATION_ERROR", "question_id inválido")
        if not isinstance(answer, str):
            raise AppError("VALIDATION_ERROR", "respuesta debe ser str")
        self.app.require(self.app.__dict__, "students")
        try:
            out = self.app.students.submit(
                ctx.technical_student_id, question_id, answer,
                attempt_id=attempt_id or "")
        except AppError:
            raise
        except KeyError as e:
            raise AppError("NOT_FOUND", str(e)[:200])
        except RuntimeError as e:
            raise AppError("CORRECTION_ERROR", str(e)[:300],
                           cause=type(e).__name__)
        except Exception as e:  # noqa: BLE001 - persistencia SQLite
            import sqlite3
            if isinstance(e, sqlite3.Error):
                raise AppError("PERSISTENCE_ERROR",
                               "persistencia: %s" % type(e).__name__)
            raise
        corr = out.get("correction", {})
        sess.touch({"kind": "question", "id": question_id,
                    "attempt": out.get("attempt_id", "")})
        return {"ok": True, "data": {"session": sess.to_dict(),
                                     "result": {
                                         "attempt_id": out.get("attempt_id", ""),
                                         "replayed": bool(out.get("replayed", False)),
                                         "status": corr.get("status", ""),
                                         "score": corr.get("score", 0.0),
                                         "mastery": [
                                             {"unit": u.get("unit", ""),
                                              "score": u.get("score", 0.0),
                                              "status": u.get("status", "")}
                                             for u in out.get("mastery_updates", [])
                                             or []]}}}

    def result(self, ctx: ApplicationContext, session,
               units: list) -> dict:
        sess = self._session(session)
        self._own(ctx, sess)
        if not isinstance(units, list) or not units:
            raise AppError("VALIDATION_ERROR", "units inválidas")
        self.app.require(self.app.__dict__, "students")
        states = []
        for uid in units:
            if not isinstance(uid, str) or not uid:
                raise AppError("VALIDATION_ERROR", "unit inválida")
            m = guard(self.app.students.get_mastery,
                      ctx.technical_student_id, uid)
            if m is None:
                raise AppError("NOT_FOUND", "sin mastery para la unidad")
            states.append(m)
        return {"ok": True, "data": {"session": sess.to_dict(),
                                     "mastery": states}}

    def next(self, ctx: ApplicationContext, session, *,
             limit: int = 5, seed: int = 0,
             mode: str = "PRACTICE") -> dict:
        """Una transición explícita: recomienda de nuevo con el estado
        actual (datos reales F5/F6, nunca heurística local)."""
        return self.recommend(ctx, session, limit=limit, seed=seed,
                              mode=mode)


def _project_item(item) -> dict:
    """Recommendation F6 -> dict público (renombres explícitos, sin lógica)."""
    d = item.to_dict() if hasattr(item, "to_dict") else dict(item)
    return {"knowledge_unit_id": d.get("knowledge_unit_id", ""),
            "unit_kind": d.get("unit_kind", ""),
            "priority": d.get("priority_score", d.get("priority", 0.0)),
            "action": d.get("action", ""),
            "difficulty": d.get("difficulty", ""),
            "target_topic": d.get("target_topic"),
            "target_section": d.get("target_section"),
            "target_concepts": list(d.get("target_concepts", []) or []),
            "target_formulas": list(d.get("target_formulas", []) or []),
            "reasons": list(d.get("reason_codes", d.get("reasons", []))
                            or [])}


def _item_kwargs(item: dict) -> dict:
    if not isinstance(item, dict) or not item.get("knowledge_unit_id"):
        raise ValueError("item inválido")
    return {"knowledge_unit_id": item["knowledge_unit_id"],
            "unit_kind": item.get("unit_kind", ""),
            "priority": float(item.get("priority", 0.0)),
            "action": item.get("action", ""),
            "difficulty": item.get("difficulty", ""),
            "target_topic": item.get("target_topic"),
            "target_section": item.get("target_section"),
            "target_concepts": tuple(item.get("target_concepts", []) or ()),
            "target_formulas": tuple(item.get("target_formulas", []) or ()),
            "reasons": tuple(item.get("reasons", []) or ())}
