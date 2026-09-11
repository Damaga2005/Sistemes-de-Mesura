"""PracticeWorkflow: pregunta → respuesta → corrección → mastery (B4.2).

Delega en Examiner (generar), Correction+Student vía submit (corregir y
registrar). Sin generador/corrector/mastery propios. Sin answer keys en
salida (vista STEM + errores proyectados).
"""
from __future__ import annotations

from app.exam.models import stem_view

from .context import ApplicationContext
from .errors import AppError, guard
from .session import ApplicationSession


class PracticeWorkflow:
    def __init__(self, app) -> None:
        self.app = app

    def _svc(self):
        self.app.require(self.app.__dict__, "examiner", "students")
        return self.app.examiner, self.app.students

    @staticmethod
    def _session(session) -> ApplicationSession:
        if isinstance(session, ApplicationSession):
            return session
        if isinstance(session, dict):
            return ApplicationSession.from_dict(session)
        raise AppError("VALIDATION_ERROR", "sesión inválida")

    def start(self, ctx: ApplicationContext, session, *, topic: int,
              question_type: str = "TRUE_FALSE", section: str = "",
              formula_id: str = "", difficulty: str = "",
              seed: int = 0) -> dict:
        sess = self._session(session)
        self._own(ctx, sess)
        if not isinstance(topic, int) or topic < 1:
            raise AppError("VALIDATION_ERROR", "topic inválido")
        engine, _ = self._svc()
        try:
            q, log = engine.generate(
                topic=topic, section=section, question_type=question_type,
                difficulty=difficulty, formula_id=formula_id, seed=seed)
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

    def get_question(self, ctx: ApplicationContext, session) -> dict:
        sess = self._session(session)
        self._own(ctx, sess)
        ref = sess.active_reference or {}
        if ref.get("kind") != "question" or not ref.get("id"):
            raise AppError("STATE_ERROR", "sin pregunta activa")
        _, students = self._svc()
        body = guard(students.correction.load_question, ref["id"])
        return {"ok": True, "data": stem_view(
            body, position=0, question_version=str(body.get("version", "")),
            points=10.0, required=True, session_id=sess.session_id)}

    def submit_answer(self, ctx: ApplicationContext, session,
                      answer: str, attempt_id: str = "",
                      *, adaptive: bool = False,
                      seed: int = 7) -> dict:
        sess = self._session(session)
        self._own(ctx, sess)
        if not isinstance(answer, str):
            raise AppError("VALIDATION_ERROR", "respuesta debe ser str")
        if not isinstance(adaptive, bool):
            raise AppError("VALIDATION_ERROR", "adaptive debe ser bool")
        if not isinstance(seed, int) or seed < 0:
            raise AppError("VALIDATION_ERROR", "seed inválido")
        ref = sess.active_reference or {}
        if ref.get("kind") != "question" or not ref.get("id"):
            raise AppError("STATE_ERROR", "sin pregunta activa")
        _, students = self._svc()
        try:
            out = students.submit(ctx.technical_student_id, ref["id"],
                                  answer, attempt_id=attempt_id or "")
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
        fb = corr.get("feedback", {}) or {}
        data = {"attempt_id": out.get("attempt_id", ""),
                "replayed": bool(out.get("replayed", False)),
                "status": corr.get("status", ""),
                "score": corr.get("score", 0.0),
                "errors": [{"type": e.get("error_type", ""),
                            "severity": e.get("severity", ""),
                            "root": bool(e.get("root_cause", False))}
                           for e in corr.get("detected_errors", []) or []],
                "feedback": {
                    "what_was_correct": list(
                        fb.get("what_was_correct", []) or []),
                    "what_was_wrong": list(
                        fb.get("what_was_wrong", []) or []),
                    "points": [{"error": p.get("error", ""),
                                "severity": p.get("severity", ""),
                                "why": p.get("why", ""),
                                "how_to_fix": p.get("how_to_fix", "")}
                               for p in fb.get("points", []) or []],
                    "feedback_version": fb.get("feedback_version", "")},
                "claims": [{"text": c.get("text", ""),
                            "type": c.get("type", ""),
                            "status": c.get("status", ""),
                            "evidence_ids": list(
                                c.get("evidence_ids", []) or [])}
                           for c in corr.get("claims", []) or []],
                "formulas": [{"status": f.get("status", ""),
                              "detail": f.get("detail", "")}
                             for f in corr.get("formula_results", [])
                             or []],
                "calculations": [{"match": bool(c.get("match", False))}
                                 for c in corr.get("calculation_results",
                                                   []) or []],
                "units": [{"status": u.get("status", "")}
                          for u in corr.get("unit_results", []) or []],
                "provenance": [{"source_path": p.get("source_path", "")}
                               for p in corr.get("provenance", []) or []],
                "mastery": [{"unit": u.get("unit", ""),
                             "score": u.get("score", 0.0),
                             "status": u.get("status", "")}
                            for u in out.get("mastery_updates", [])
                            or []],
                "next": None}
        nxt = self._next_question(ctx, sess, adaptive, seed)
        data["next"] = nxt
        nxt_q = (nxt or {}).get("question") or {}
        sess.touch({"kind": "question",
                    "id": nxt_q.get("question_id") or ref["id"],
                    "attempt": out.get("attempt_id", "")})
        return {"ok": True, "data": {"session": sess.to_dict(),
                                     "result": data}}

    def _next_question(self, ctx: ApplicationContext,
                       sess: ApplicationSession, adaptive: bool,
                       seed: int) -> dict | None:
        """Cierre del loop: recommend+generate canónicos vía loop.step().

        Manual -> None (sin pregunta adicional). Adaptive -> siguiente
        pregunta o rechazo honesto. La corrección ya está registrada;
        un fallo aquí no la invalida (next lleva el error).
        """
        if not adaptive:
            return None
        self.app.require(self.app.__dict__, "adaptive", "examiner")
        try:
            out = self.app.adaptive.step(
                ctx.technical_student_id, self.app.examiner,
                limit=1, seed=seed)
        except AppError as e:
            return {"question": None, "item": None,
                    "generation": {"rejected": "%s: %s" % (e.code,
                                                           e.message)}}
        question = out.get("question")
        if question is None:
            return {"question": None,
                    "item": (out.get("recommendations") or [None])[0],
                    "generation": out.get("generate_log", {})}
        body = dict(question)
        view = stem_view(body, position=0,
                         question_version=str(body.get("version", "")),
                         points=10.0, required=True,
                         session_id=sess.session_id)
        sess.touch({"kind": "question", "id": view["question_id"]})
        return {"question": view,
                "item": out.get("selected"),
                "generation": {k: v for k, v in
                               out.get("generate_log", {}).items()
                               if k != "blueprint_obj"}}

    def get_result(self, ctx: ApplicationContext, session,
                   units: list) -> dict:
        sess = self._session(session)
        self._own(ctx, sess)
        if not isinstance(units, list) or not units:
            raise AppError("VALIDATION_ERROR", "units inválidas")
        _, students = self._svc()
        states = []
        for uid in units:
            if not isinstance(uid, str) or not uid:
                raise AppError("VALIDATION_ERROR", "unit inválida")
            m = guard(students.get_mastery, ctx.technical_student_id, uid)
            if m is None:
                raise AppError("NOT_FOUND",
                               "sin mastery para la unidad")
            states.append(m)
        return {"ok": True, "data": {"session": sess.to_dict(),
                                     "mastery": states}}

    def complete(self, ctx: ApplicationContext, session) -> dict:
        sess = self._session(session)
        self._own(ctx, sess)
        sess.transition("COMPLETED")
        return {"ok": True, "data": {"session": sess.to_dict()}}

    @staticmethod
    def _own(ctx: ApplicationContext, sess: ApplicationSession) -> None:
        if ctx.technical_student_id != sess.student_id:
            raise AppError("NOT_FOUND",
                           "sesión no disponible para este estudiante")
