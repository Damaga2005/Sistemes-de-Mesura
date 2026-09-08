"""Tests ReviewWorkflow (B4.5): fachada ExamReviewService, anti-leak."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from app.application.errors import AppError  # noqa: E402
from app.application.review import ReviewWorkflow  # noqa: E402
from harness import build_app, ctx, sess  # noqa: E402

T0 = "2026-09-05T10:00:00+00:00"
BP = {"title": "t", "version": "1", "seed": 7, "duration_seconds": 600,
      "question_count": 2, "topics": [2], "types": {"TRUE_FALSE": 2},
      "difficulty": {"EASY": 1.0}, "exam_kind": "MOCK_EXAM"}


def wf(tmp_path):
    app = build_app(tmp_path)
    return app, ReviewWorkflow(app)


def graded(app, w, c, s, answers=("V", "F"), student="alu-1"):
    eid = app.exam_sessions.store_blueprint(BP)["exam_id"]
    app.exam_sessions.prepare_exam(eid)
    xsid = app.exam_sessions.create_session(eid, student)["session_id"]
    app.exam_sessions.prepare_session(xsid, student)
    app.exam_sessions.start_session(xsid, student, now=T0)
    for pos, ans in enumerate(answers):
        app.exam_sessions.save_answer(xsid, pos, ans, student, now=T0)
    app.exam_sessions.submit_session(xsid, student, now=T0)
    app.exam_grading.grade(xsid, student, now=T0)
    return xsid


def test_01_graded_exam(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="REVIEW"), sess(app, workflow="REVIEW")
    xsid = graded(app, w, c, s)
    r = w.get_result(c, s, xsid)["data"]
    assert r["percentage"] and r["question_count"] == 2


def test_02_review_available(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="REVIEW"), sess(app, workflow="REVIEW")
    xsid = graded(app, w, c, s)
    r = w.get_review(c, s, xsid)["data"]
    assert len(r["questions"]) == 2


def test_03_review_unavailable(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="REVIEW"), sess(app, workflow="REVIEW")
    eid = app.exam_sessions.store_blueprint(BP)["exam_id"]
    app.exam_sessions.prepare_exam(eid)
    xsid = app.exam_sessions.create_session(eid, "alu-1")["session_id"]
    with pytest.raises(AppError):
        w.get_review(c, s, xsid)


def test_04_incomplete_grading(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="REVIEW"), sess(app, workflow="REVIEW")
    eid = app.exam_sessions.store_blueprint(BP)["exam_id"]
    app.exam_sessions.prepare_exam(eid)
    xsid = app.exam_sessions.create_session(eid, "alu-1")["session_id"]
    app.exam_sessions.prepare_session(xsid, "alu-1")
    app.exam_sessions.start_session(xsid, "alu-1", now=T0)
    app.exam_sessions.save_answer(xsid, 0, "V", "alu-1", now=T0)
    app.exam_sessions.submit_session(xsid, "alu-1", now=T0)
    with pytest.raises(AppError) as e:
        w.get_review(c, s, xsid)
    assert e.value.code in ("STATE_ERROR", "NOT_FOUND")


def test_05_cancelled(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="REVIEW"), sess(app, workflow="REVIEW")
    eid = app.exam_sessions.store_blueprint(BP)["exam_id"]
    app.exam_sessions.prepare_exam(eid)
    xsid = app.exam_sessions.create_session(eid, "alu-1")["session_id"]
    app.exam_sessions.cancel_session(xsid, "alu-1")
    with pytest.raises(AppError):
        w.get_result(c, s, xsid)
    with pytest.raises(AppError):
        w.get_review(c, s, xsid)


def test_06_wrong_student(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="REVIEW"), sess(app, workflow="REVIEW")
    xsid = graded(app, w, c, s)
    c2 = ctx(app, student="alu-2", workflow="REVIEW")
    for fn in (lambda: w.get_result(c2, s, xsid),
               lambda: w.get_review(c2, s, xsid),
               lambda: w.get_question_review(c2, s, xsid, 0),
               lambda: w.get_mastery_view(c2, s, xsid)):
        with pytest.raises(AppError) as e:
            fn()
        assert e.value.code == "NOT_FOUND"


def test_07_wrong_exam(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="REVIEW"), sess(app, workflow="REVIEW")
    graded(app, w, c, s)
    with pytest.raises(AppError):
        w.get_result(c, s, "exs-inexistente")


def test_08_wrong_session(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="REVIEW"), sess(app, workflow="REVIEW")
    xsid = graded(app, w, c, s)
    with pytest.raises(AppError):
        w.get_question_review(c, s, xsid, 99)


def test_09_catalan(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="REVIEW", language="ca"), sess(
        app, workflow="REVIEW")
    xsid = graded(app, w, c, s)
    r = w.get_review(c, s, xsid)
    assert r["ok"]


def test_10_spanish(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="REVIEW", language="es"), sess(
        app, workflow="REVIEW")
    xsid = graded(app, w, c, s)
    r = w.get_review(c, s, xsid)
    assert r["ok"]


def test_11_mastery_view(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="REVIEW"), sess(app, workflow="REVIEW")
    xsid = graded(app, w, c, s)
    r = w.get_mastery_view(c, s, xsid)["data"]
    assert r["units"]


def test_12_repeated_review(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="REVIEW"), sess(app, workflow="REVIEW")
    xsid = graded(app, w, c, s)
    a = w.get_review(c, s, xsid)
    b = w.get_review(c, s, xsid)
    assert a == b
