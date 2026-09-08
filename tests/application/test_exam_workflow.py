"""Tests ExamWorkflow (B4.4): fachada 1:1 sobre F7, sin duplicar."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from app.application.errors import AppError  # noqa: E402
from app.application.exam import ExamWorkflow  # noqa: E402
from harness import build_app, ctx, sess  # noqa: E402

T0 = "2026-09-05T10:00:00+00:00"


BP = {"title": "t", "version": "1", "seed": 7, "duration_seconds": 600,
      "question_count": 2, "topics": [2], "types": {"TRUE_FALSE": 2},
      "difficulty": {"EASY": 1.0}, "exam_kind": "MOCK_EXAM"}


def wf(tmp_path):
    app = build_app(tmp_path)
    return app, ExamWorkflow(app)


def mkexam(app, kind="MOCK_EXAM"):
    bp = dict(BP, exam_kind=kind)
    eid = app.exam_sessions.store_blueprint(bp)["exam_id"]
    app.exam_sessions.prepare_exam(eid)
    return eid


def full_flow(app, w, c, s, answers=("V", "F"), now="2026-09-05T10:00:00+00:00"):
    eid = mkexam(app)
    xsid = w.create(c, s, eid)["data"]["exam_session"]["session_id"]
    w.prepare(c, s, xsid)
    w.start(c, s, xsid, now=now)
    for pos, ans in enumerate(answers):
        w.save_answer(c, s, xsid, pos, ans, now=now)
    w.submit(c, s, xsid, now=now)
    return xsid


def test_01_valid_exam(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="EXAM"), sess(app, workflow="EXAM")
    eid = mkexam(app)
    out = w.create(c, s, eid)
    assert out["ok"] and out["data"]["exam_session"]["session_id"]


def test_02_invalid_exam(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="EXAM"), sess(app, workflow="EXAM")
    with pytest.raises(AppError) as e:
        w.create(c, s, "exm-inexistente")
    assert e.value.code == "NOT_FOUND"


def test_03_prepare(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="EXAM"), sess(app, workflow="EXAM")
    eid = mkexam(app)
    xsid = w.create(c, s, eid)["data"]["exam_session"]["session_id"]
    out = w.prepare(c, s, xsid)
    assert out["data"]["prepared"]["status"] == "READY"


def test_04_ready(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="EXAM"), sess(app, workflow="EXAM")
    eid = mkexam(app)
    xsid = w.create(c, s, eid)["data"]["exam_session"]["session_id"]
    assert app.exam_sessions.session_status(xsid)["status"] == "CREATED"
    w.prepare(c, s, xsid)
    assert app.exam_sessions.session_status(xsid)["status"] == "READY"


def test_05_start(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="EXAM"), sess(app, workflow="EXAM")
    eid = mkexam(app)
    xsid = w.create(c, s, eid)["data"]["exam_session"]["session_id"]
    w.prepare(c, s, xsid)
    out = w.start(c, s, xsid, now="2026-09-05T10:00:00+00:00")
    assert out["data"]["started"]["status"] == "IN_PROGRESS"


def test_06_question(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="EXAM"), sess(app, workflow="EXAM")
    eid = mkexam(app)
    xsid = w.create(c, s, eid)["data"]["exam_session"]["session_id"]
    w.prepare(c, s, xsid)
    w.start(c, s, xsid, now=T0)
    q = w.get_question(c, s, xsid, 0,
                       now="2026-09-05T10:01:00+00:00")["data"]["question"]
    assert q["question_id"] and "correct_answer" not in q


def test_07_save_answer(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="EXAM"), sess(app, workflow="EXAM")
    eid = mkexam(app)
    xsid = w.create(c, s, eid)["data"]["exam_session"]["session_id"]
    w.prepare(c, s, xsid)
    w.start(c, s, xsid, now=T0)
    out = w.save_answer(c, s, xsid, 0, "V", now="2026-09-05T10:01:00+00:00")
    assert out["data"]["saved"]["version"] == 1


def test_08_submit(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="EXAM"), sess(app, workflow="EXAM")
    eid = mkexam(app)
    xsid = w.create(c, s, eid)["data"]["exam_session"]["session_id"]
    w.prepare(c, s, xsid)
    w.start(c, s, xsid, now=T0)
    out = w.submit(c, s, xsid, now="2026-09-05T10:04:00+00:00")
    assert out["data"]["submitted"]["status"] == "SUBMITTED"


def test_09_grade(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="EXAM"), sess(app, workflow="EXAM")
    xsid = full_flow(app, w, c, s)
    out = w.grade(c, s, xsid, now="2026-09-05T10:05:00+00:00")
    assert out["data"]["result"]["status"] in ("COMPLETE", "INCOMPLETE")


def test_10_result(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="EXAM"), sess(app, workflow="EXAM")
    xsid = full_flow(app, w, c, s)
    w.grade(c, s, xsid, now="2026-09-05T10:05:00+00:00")
    r = w.get_result(c, s, xsid)["data"]["result"]
    assert r["question_count"] == 2 and "percentage" in r


def test_11_review(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="EXAM"), sess(app, workflow="EXAM")
    xsid = full_flow(app, w, c, s)
    w.grade(c, s, xsid, now="2026-09-05T10:05:00+00:00")
    r = w.review(c, s, xsid)["data"]["review"]
    assert len(r["questions"]) == 2


def test_12_blank_answer(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="EXAM"), sess(app, workflow="EXAM")
    eid = mkexam(app)
    xsid = w.create(c, s, eid)["data"]["exam_session"]["session_id"]
    w.prepare(c, s, xsid)
    w.start(c, s, xsid, now=T0)
    w.save_answer(c, s, xsid, 0, "", now="2026-09-05T10:01:00+00:00")
    w.save_answer(c, s, xsid, 1, "V", now="2026-09-05T10:02:00+00:00")
    w.submit(c, s, xsid, now="2026-09-05T10:04:00+00:00")
    g = w.grade(c, s, xsid, now="2026-09-05T10:05:00+00:00")
    assert g["data"]["result"]["blank_count"] == 1


def test_13_partial_answer(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="EXAM"), sess(app, workflow="EXAM")
    xsid = full_flow(app, w, c, s, answers=("V", ""))
    g = w.grade(c, s, xsid, now="2026-09-05T10:05:00+00:00")
    assert g["data"]["result"]["answered_count"] == 1


def test_14_expiry(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="EXAM"), sess(app, workflow="EXAM")
    eid = mkexam(app)
    xsid = w.create(c, s, eid)["data"]["exam_session"]["session_id"]
    w.prepare(c, s, xsid)
    w.start(c, s, xsid, now=T0)
    with pytest.raises(AppError):
        w.save_answer(c, s, xsid, 0, "V", now="2026-09-05T11:00:00+00:00")
    assert app.exam_sessions.session_status(xsid)["status"] == "EXPIRED"


def test_15_cancellation(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="EXAM"), sess(app, workflow="EXAM")
    eid = mkexam(app)
    xsid = w.create(c, s, eid)["data"]["exam_session"]["session_id"]
    app.exam_sessions.cancel_session(xsid, "alu-1")
    with pytest.raises(AppError):
        w.start(c, s, xsid, now=T0)


def test_16_repeated_submit(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="EXAM"), sess(app, workflow="EXAM")
    xsid = full_flow(app, w, c, s)
    a = w.submit(c, s, xsid, now="2026-09-05T10:06:00+00:00")
    b = w.submit(c, s, xsid, now="2026-09-05T10:07:00+00:00")
    assert (a["data"]["submitted"]["submitted_at"] ==
            b["data"]["submitted"]["submitted_at"])


def test_17_repeated_grade(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="EXAM"), sess(app, workflow="EXAM")
    xsid = full_flow(app, w, c, s)
    a = w.grade(c, s, xsid, now="2026-09-05T10:05:00+00:00")
    b = w.grade(c, s, xsid, now="2026-09-05T10:06:00+00:00")
    assert a["data"]["result"] == b["data"]["result"]


def test_18_invalid_state(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="EXAM"), sess(app, workflow="EXAM")
    eid = mkexam(app)
    xsid = w.create(c, s, eid)["data"]["exam_session"]["session_id"]
    with pytest.raises(AppError) as e:
        w.submit(c, s, xsid, now="2026-09-05T10:00:00+00:00")
    assert e.value.code == "STATE_ERROR"
