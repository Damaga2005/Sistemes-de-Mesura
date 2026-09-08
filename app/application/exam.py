"""ExamWorkflow: fachada 1:1 sobre F7 (B4.4). Sin timer/snapshot/scoring propios."""
from __future__ import annotations

from .context import ApplicationContext
from .errors import AppError, guard
from .session import ApplicationSession


class ExamWorkflow:
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

    def _sessions(self):
        self.app.require(self.app.__dict__, "exam_sessions")
        return self.app.exam_sessions

    def _grading(self):
        self.app.require(self.app.__dict__, "exam_grading")
        return self.app.exam_grading

    def _touch(self, sess, kind, ref):
        try:
            sess.touch({"kind": kind, "id": ref})
        except AppError:
            pass
        return sess

    def configure(self, ctx: ApplicationContext, session,
                  spec: dict) -> dict:
        """Create and prepare an exam through the certified F7 service."""
        sess = self._session(session)
        self._own(ctx, sess)
        if not isinstance(spec, dict):
            raise AppError("VALIDATION_ERROR", "configuració invàlida")
        out = guard(self._sessions().store_blueprint, dict(spec))
        exam_id = out["exam_id"]
        prepared = guard(self._sessions().prepare_exam, exam_id)
        created = guard(self._sessions().create_session, exam_id,
                        ctx.technical_student_id)
        xsid = created["session_id"]
        ready = guard(self._sessions().prepare_session, xsid,
                      ctx.technical_student_id)
        return {"ok": True, "data": {"exam": prepared,
                                     "exam_session": created,
                                     "prepared": ready}}

    def state(self, ctx: ApplicationContext, session,
              exam_session_id: str) -> dict:
        """Return the backend-owned session and safe snapshot projection."""
        sess = self._session(session)
        self._own(ctx, sess)
        data = guard(self._sessions().read_session, exam_session_id,
                     ctx.technical_student_id)
        exam = guard(self._sessions().read_exam,
                     data["session"]["exam_id"])
        return {"ok": True, "data": {"session": data["session"],
                                     "exam": exam,
                                     "instances": data["instances"],
                                     "answers": data["answers"]}}

    def list_mine(self, ctx: ApplicationContext, session) -> dict:
        sess = self._session(session)
        self._own(ctx, sess)
        items = []
        for item in guard(self._sessions().list_sessions,
                          ctx.technical_student_id):
            exam = guard(self._sessions().read_exam, item["exam_id"])
            items.append({**item, "title": exam["title"],
                          "exam_kind": exam["kind"],
                          "duration_seconds": exam["duration_seconds"],
                          "question_count": exam["question_count"],
                          "topics": exam["topics"]})
        return {"ok": True, "data": {"sessions": items}}

    def history(self, ctx: ApplicationContext, session) -> dict:
        """Read-only activity history assembled from certified F7 reads."""
        sess = self._session(session)
        self._own(ctx, sess)
        items = []
        for item in guard(self._sessions().list_sessions,
                          ctx.technical_student_id):
            state = guard(self._sessions().read_session,
                          item["session_id"], ctx.technical_student_id)
            exam = guard(self._sessions().read_exam, item["exam_id"])
            session_data = state["session"]
            row = {**item, "title": exam["title"],
                   "exam_kind": exam["kind"],
                   "duration_seconds": exam["duration_seconds"],
                   "question_count": exam["question_count"],
                   "topics": exam["topics"],
                   "created_at": session_data.get("created_at", ""),
                   "started_at": session_data.get("started_at", ""),
                   "submitted_at": session_data.get("submitted_at", ""),
                   "expires_at": session_data.get("expires_at", ""),
                   "provenance": {
                       "exam_id": item["exam_id"],
                       "exam_version": session_data.get("exam_version", ""),
                       "policy_versions": session_data.get(
                           "policy_versions", {})}}
            row["result"] = self._history_result(
                ctx.technical_student_id, item["session_id"])
            items.append(row)
        return {"ok": True, "data": {"history": items}}

    def _history_result(self, student_id: str, session_id: str) -> dict:
        try:
            result = guard(self._grading().get_result, session_id,
                           student_id)
        except AppError as exc:
            if exc.code == "STATE_ERROR":
                return {"available": False,
                        "reason": "RESULT_NOT_AVAILABLE"}
            raise
        return {"available": True,
                "status": result.get("status", ""),
                "total_points": result.get("total_points"),
                "earned_points": result.get("earned_points"),
                "percentage": result.get("percentage"),
                "question_count": result.get("question_count"),
                "answered_count": result.get("answered_count"),
                "blank_count": result.get("blank_count"),
                "correct_count": result.get("correct_count"),
                "partial_count": result.get("partial_count"),
                "incorrect_count": result.get("incorrect_count"),
                "graded_at": result.get("graded_at"),
                "provenance": {
                    "exam_version": result.get("exam_version", ""),
                    "scoring_policy_id": result.get("scoring_policy_id", ""),
                    "scoring_policy_version": result.get(
                        "scoring_policy_version", "")}}

    def create(self, ctx: ApplicationContext, session, exam_id: str) -> dict:
        sess = self._session(session)
        self._own(ctx, sess)
        if not isinstance(exam_id, str) or not exam_id:
            raise AppError("VALIDATION_ERROR", "exam_id inválido")
        out = guard(self._sessions().create_session, exam_id,
                    ctx.technical_student_id)
        self._touch(sess, "exam_session", out["session_id"])
        return {"ok": True, "data": {"session": sess.to_dict(),
                                     "exam_session": out}}

    def prepare(self, ctx: ApplicationContext, session,
                exam_session_id: str) -> dict:
        sess = self._session(session)
        self._own(ctx, sess)
        out = guard(self._sessions().prepare_session, exam_session_id,
                    ctx.technical_student_id)
        self._touch(sess, "exam_session", exam_session_id)
        return {"ok": True, "data": {"session": sess.to_dict(),
                                     "prepared": out}}

    def start(self, ctx: ApplicationContext, session, exam_session_id: str,
              now: str = "") -> dict:
        sess = self._session(session)
        self._own(ctx, sess)
        out = guard(self._sessions().start_session, exam_session_id,
                    ctx.technical_student_id, **({"now": now} if now else {}))
        self._touch(sess, "exam_session", exam_session_id)
        return {"ok": True, "data": {"session": sess.to_dict(),
                                     "started": out}}

    def get_question(self, ctx: ApplicationContext, session,
                     exam_session_id: str, position: int,
                     now: str = "") -> dict:
        sess = self._session(session)
        self._own(ctx, sess)
        if not isinstance(position, int) or position < 0:
            raise AppError("VALIDATION_ERROR", "position inválida")
        out = guard(self._sessions().get_question, exam_session_id,
                    position, ctx.technical_student_id,
                    **({"now": now} if now else {}))
        return {"ok": True, "data": {"session": sess.to_dict(),
                                     "question": out}}

    def save_answer(self, ctx: ApplicationContext, session,
                    exam_session_id: str, position: int, answer: str,
                    now: str = "") -> dict:
        sess = self._session(session)
        self._own(ctx, sess)
        if not isinstance(answer, str):
            raise AppError("VALIDATION_ERROR", "respuesta debe ser str")
        out = guard(self._sessions().save_answer, exam_session_id, position,
                    answer, ctx.technical_student_id,
                    **({"now": now} if now else {}))
        self._touch(sess, "exam_session", exam_session_id)
        return {"ok": True, "data": {"session": sess.to_dict(),
                                     "saved": out}}

    def submit(self, ctx: ApplicationContext, session, exam_session_id: str,
               now: str = "") -> dict:
        sess = self._session(session)
        self._own(ctx, sess)
        out = guard(self._sessions().submit_session, exam_session_id,
                    ctx.technical_student_id, **({"now": now} if now else {}))
        self._touch(sess, "exam_session", exam_session_id)
        return {"ok": True, "data": {"session": sess.to_dict(),
                                     "submitted": out}}

    def grade(self, ctx: ApplicationContext, session, exam_session_id: str,
              now: str = "") -> dict:
        sess = self._session(session)
        self._own(ctx, sess)
        out = guard(self._grading().grade, exam_session_id,
                    ctx.technical_student_id, **({"now": now} if now else {}))
        self._touch(sess, "exam_session", exam_session_id)
        return {"ok": True, "data": {"session": sess.to_dict(),
                                     "result": out}}

    def get_result(self, ctx: ApplicationContext, session,
                   exam_session_id: str) -> dict:
        sess = self._session(session)
        self._own(ctx, sess)
        out = guard(self._grading().get_result, exam_session_id,
                    ctx.technical_student_id)
        return {"ok": True, "data": {"session": sess.to_dict(),
                                     "result": out}}

    def review(self, ctx: ApplicationContext, session, exam_session_id: str,
               policy_version: str = "") -> dict:
        sess = self._session(session)
        self._own(ctx, sess)
        self.app.require(self.app.__dict__, "exam_review")
        out = guard(self.app.exam_review.get_review, exam_session_id,
                    ctx.technical_student_id,
                    **({"policy_version": policy_version}
                       if policy_version else {}))
        return {"ok": True, "data": {"session": sess.to_dict(),
                                     "review": out}}
