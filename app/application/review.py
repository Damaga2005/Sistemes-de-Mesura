"""ReviewWorkflow: fachada sobre ExamReviewService (B4.5). Solo lecturas."""
from __future__ import annotations

from .context import ApplicationContext
from .errors import AppError, guard
from .session import ApplicationSession


class ReviewWorkflow:
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

    def _review(self):
        self.app.require(self.app.__dict__, "exam_review")
        return self.app.exam_review

    def _grading(self):
        self.app.require(self.app.__dict__, "exam_grading")
        return self.app.exam_grading

    def get_result(self, ctx: ApplicationContext, session,
                   exam_session_id: str) -> dict:
        sess = self._session(session)
        self._own(ctx, sess)
        out = guard(self._grading().get_result, exam_session_id,
                    ctx.technical_student_id)
        return {"ok": True, "data": out}

    def get_review(self, ctx: ApplicationContext, session,
                   exam_session_id: str, policy_version: str = "") -> dict:
        sess = self._session(session)
        self._own(ctx, sess)
        out = guard(self._review().get_review, exam_session_id,
                    ctx.technical_student_id,
                    **({"policy_version": policy_version}
                       if policy_version else {}))
        return {"ok": True, "data": out}

    def get_question_review(self, ctx: ApplicationContext, session,
                            exam_session_id: str, position: int,
                            policy_version: str = "") -> dict:
        sess = self._session(session)
        self._own(ctx, sess)
        if not isinstance(position, int) or position < 0:
            raise AppError("VALIDATION_ERROR", "position inválida")
        out = guard(self._review().get_review_question, exam_session_id,
                    position, ctx.technical_student_id,
                    **({"policy_version": policy_version}
                       if policy_version else {}))
        return {"ok": True, "data": out}

    def get_mastery_view(self, ctx: ApplicationContext, session,
                         exam_session_id: str,
                         policy_version: str = "") -> dict:
        sess = self._session(session)
        self._own(ctx, sess)
        out = guard(self._review().get_mastery_view,
                    ctx.technical_student_id, exam_session_id,
                    **({"policy_version": policy_version}
                       if policy_version else {}))
        return {"ok": True, "data": out}
