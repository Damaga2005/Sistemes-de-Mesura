"""Tests idempotencia B5.11: repetir es equivalente, sin duplicar estado."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from app.application.adaptive import AdaptivePracticeWorkflow  # noqa: E402
from app.application.errors import AppError  # noqa: E402
from app.application.exam import ExamWorkflow  # noqa: E402
from app.application.practice import PracticeWorkflow  # noqa: E402
from app.application.review import ReviewWorkflow  # noqa: E402
from app.application.tutor import TutorWorkflow  # noqa: E402
from harness import build_app, ctx, sess  # noqa: E402

BP = {"title": "t", "version": "1", "seed": 7, "duration_seconds": 600,
      "question_count": 1, "topics": [2], "types": {"TRUE_FALSE": 1},
      "difficulty": {"EASY": 1.0}, "exam_kind": "MOCK_EXAM"}
T0 = "2026-09-05T10:00:00+00:00"


def test_practice_submit_x3(tmp_path):
    app = build_app(tmp_path)
    p = PracticeWorkflow(app)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="i")
    p.start(c, s, topic=2, question_type="TRUE_FALSE", seed=11)
    r1 = p.submit_answer(c, s, "V", attempt_id="att-i-1")
    assert r1["data"]["result"]["replayed"] is False
    for _ in range(2):
        r = p.submit_answer(c, s, "V", attempt_id="att-i-1")
        assert r["data"]["result"]["replayed"] is True
    r3 = p.submit_answer(c, s, "V", attempt_id="att-i-1")
    assert r3["data"]["result"]["replayed"] is True
    assert r3["data"]["result"]["score"] == 8.5


def test_exam_submit_grade_x3(tmp_path):
    app = build_app(tmp_path)
    ex = ExamWorkflow(app)
    c = ctx(app, workflow="EXAM")
    s = sess(app, workflow="EXAM", nonce="i")
    eid = app.exam_sessions.store_blueprint(dict(BP))["exam_id"]
    app.exam_sessions.prepare_exam(eid)
    xsid = ex.create(c, s, eid)["data"]["exam_session"]["session_id"]
    ex.prepare(c, s, xsid)
    ex.start(c, s, xsid, now=T0)
    ex.save_answer(c, s, xsid, 0, "F",
                   now="2026-09-05T10:01:00+00:00")
    subs = [ex.submit(c, s, xsid, now="2026-09-05T10:04:00+00:00")
            ["data"]["submitted"]["status"] for _ in range(3)]
    assert subs == ["SUBMITTED"] * 3
    pcts = [ex.grade(c, s, xsid, now="2026-09-05T10:05:00+00:00")
            ["data"]["result"]["percentage"] for _ in range(3)]
    assert pcts == ["85.00"] * 3


def test_review_x3_equal(tmp_path):
    app = build_app(tmp_path)
    ex = ExamWorkflow(app)
    c = ctx(app, workflow="EXAM")
    s = sess(app, workflow="EXAM", nonce="i")
    eid = app.exam_sessions.store_blueprint(dict(BP))["exam_id"]
    app.exam_sessions.prepare_exam(eid)
    xsid = ex.create(c, s, eid)["data"]["exam_session"]["session_id"]
    ex.prepare(c, s, xsid)
    ex.start(c, s, xsid, now=T0)
    ex.save_answer(c, s, xsid, 0, "F",
                   now="2026-09-05T10:01:00+00:00")
    ex.submit(c, s, xsid, now="2026-09-05T10:04:00+00:00")
    ex.grade(c, s, xsid, now="2026-09-05T10:05:00+00:00")
    r = ReviewWorkflow(app)
    cr = ctx(app, workflow="REVIEW")
    outs = [r.get_review(cr, sess(app, workflow="REVIEW", nonce="i%d" % n),
                         xsid)["data"] for n in range(3)]
    assert outs[0] == outs[1] == outs[2]


def test_tutor_ask_x2_equal(tmp_path):
    app = build_app(tmp_path)
    t = TutorWorkflow(app)
    c = ctx(app, workflow="TUTOR")
    a = t.ask(c, "qu\u00e8 \u00e9s la incertesa expandida?")["data"]
    b = t.ask(c, "qu\u00e8 \u00e9s la incertesa expandida?")["data"]
    assert b["answer"] == a["answer"]
    assert b["claims"] == a["claims"]


def test_adaptive_recommend_x2_equal(tmp_path):
    app = build_app(tmp_path)
    p = PracticeWorkflow(app)
    a = AdaptivePracticeWorkflow(app)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="i")
    p.start(c, s, topic=2, question_type="SHORT_ANSWER", seed=13)
    p.submit_answer(c, s, "basura total", attempt_id="att-i-2")
    ca = ctx(app, workflow="ADAPTIVE_PRACTICE")
    r1 = a.recommend(ca, sess(app, workflow="ADAPTIVE_PRACTICE",
                              nonce="i1"), limit=5, seed=7)["data"][
                                  "recommendations"]
    r2 = a.recommend(ca, sess(app, workflow="ADAPTIVE_PRACTICE",
                              nonce="i2"), limit=5, seed=7)["data"][
                                  "recommendations"]
    assert r2 == r1


def test_complete_twice_is_state_error(tmp_path):
    """`complete` NO es idempotente por diseno: terminal documentado."""
    app = build_app(tmp_path)
    p = PracticeWorkflow(app)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="i")
    p.start(c, s, topic=2, seed=7)
    p.complete(c, s)
    with pytest.raises(AppError) as e:
        p.complete(c, s)
    assert e.value.code == "STATE_ERROR"
