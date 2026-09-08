"""Tests cross-workflow (B4.6/B4.7): cadenas sin contaminación."""
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
      "question_count": 2, "topics": [2], "types": {"TRUE_FALSE": 2},
      "difficulty": {"EASY": 1.0}, "exam_kind": "MOCK_EXAM"}
T0 = "2026-09-05T10:00:00+00:00"


def allw(app):
    return (TutorWorkflow(app), PracticeWorkflow(app),
            AdaptivePracticeWorkflow(app), ExamWorkflow(app),
            ReviewWorkflow(app))


def test_A_tutor_practice_mastery(tmp_path):
    app = build_app(tmp_path)
    t, p, _, _, _ = allw(app)
    c = ctx(app, workflow="TUTOR")
    r = t.ask(c, "què és la incertesa expandida?")
    assert r["ok"]
    c2 = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="a")
    q = p.start(c2, s, topic=2, question_type="TRUE_FALSE",
                seed=11)["data"]["question"]
    out = p.submit_answer(c2, s, "V", attempt_id="att-a-1")
    assert out["data"]["result"]["mastery"]


def test_B_practice_adaptive(tmp_path):
    app = build_app(tmp_path)
    _, p, a, _, _ = allw(app)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="b")
    q = p.start(c, s, topic=2, question_type="FORMULA",
                formula_id="eq-02-0034", seed=14)["data"]["question"]
    p.submit_answer(c, s, "$U=u_c/k$",
                    attempt_id="att-b-1")
    c2 = ctx(app, workflow="ADAPTIVE_PRACTICE")
    s2 = sess(app, workflow="ADAPTIVE_PRACTICE", nonce="b")
    r = a.recommend(c2, s2, limit=5, seed=7)
    assert r["data"]["recommendations"]
    fids = [f for x in r["data"]["recommendations"]
            for f in x["target_formulas"]]
    assert "eq-02-0034" in fids


def test_C_adaptive_practice(tmp_path):
    app = build_app(tmp_path)
    _, p, a, _, _ = allw(app)
    c = ctx(app, workflow="ADAPTIVE_PRACTICE")
    s = sess(app, workflow="ADAPTIVE_PRACTICE", nonce="c")
    q0 = p.start(ctx(app, workflow="PRACTICE"),
                 sess(app, workflow="PRACTICE", nonce="c0"),
                 topic=2, question_type="SHORT_ANSWER",
                 seed=13)["data"]["question"]
    app.students.submit("alu-1", q0["question_id"], "basura total",
                        attempt_id="att-c0-1")
    r = a.recommend(c, s, limit=10, seed=7)
    got = None
    for item in r["data"]["recommendations"]:
        try:
            g = a.generate(c, s, item, seed=7)
            got = g
            break
        except AppError:
            continue
    assert got is not None
    assert got["data"]["question"]["question_id"]


def test_D_exam_review(tmp_path):
    app = build_app(tmp_path)
    from app.application.exam import ExamWorkflow as EW
    from app.application.review import ReviewWorkflow as RW
    e, r = EW(app), RW(app)
    c = ctx(app, workflow="EXAM")
    s = sess(app, workflow="EXAM", nonce="d")
    eid = app.exam_sessions.store_blueprint(BP)["exam_id"]
    app.exam_sessions.prepare_exam(eid)
    xsid = e.create(c, s, eid)["data"]["exam_session"]["session_id"]
    e.prepare(c, s, xsid)
    e.start(c, s, xsid, now=T0)
    e.save_answer(c, s, xsid, 0, "V", now=T0)
    e.submit(c, s, xsid, now=T0)
    e.grade(c, s, xsid, now=T0)
    c2 = ctx(app, workflow="REVIEW")
    s2 = sess(app, workflow="REVIEW", nonce="d")
    rev = r.get_review(c2, s2, xsid)["data"]
    assert len(rev["questions"]) == 2
    assert rev["session_id"] == xsid


def test_E_practice_exam_review(tmp_path):
    app = build_app(tmp_path)
    _, p, _, e, r = allw(app)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="e")
    q = p.start(c, s, topic=2, question_type="TRUE_FALSE",
                seed=11)["data"]["question"]
    p.submit_answer(c, s, "V", attempt_id="att-e-1")
    p.complete(c, s)
    ce = ctx(app, workflow="EXAM")
    se = sess(app, workflow="EXAM", nonce="e")
    eid = app.exam_sessions.store_blueprint(BP)["exam_id"]
    app.exam_sessions.prepare_exam(eid)
    xsid = e.create(ce, se, eid)["data"]["exam_session"]["session_id"]
    e.prepare(ce, se, xsid)
    e.start(ce, se, xsid, now=T0)
    e.save_answer(ce, se, xsid, 0, "V", now=T0)
    e.submit(ce, se, xsid, now=T0)
    e.grade(ce, se, xsid, now=T0)
    cr = ctx(app, workflow="REVIEW")
    sr = sess(app, workflow="REVIEW", nonce="e")
    rev = r.get_review(cr, sr, xsid)
    assert rev["ok"]


def test_no_answer_leakage(tmp_path):
    app = build_app(tmp_path)
    _, p, _, _, _ = allw(app)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="f")
    q = p.start(c, s, topic=2, question_type="TRUE_FALSE",
                seed=11)["data"]["question"]
    p.submit_answer(c, s, "V", attempt_id="att-f-1")
    c2 = ctx(app, workflow="PRACTICE")
    s2 = sess(app, workflow="PRACTICE", nonce="f2")
    q2 = p.start(c2, s2, topic=2, question_type="TRUE_FALSE",
                 seed=11)["data"]["question"]
    assert "correct_answer" not in q2


def test_no_cross_session_state(tmp_path):
    app = build_app(tmp_path)
    _, p, _, _, _ = allw(app)
    c = ctx(app, workflow="PRACTICE")
    s1 = sess(app, workflow="PRACTICE", nonce="g1")
    s2 = sess(app, workflow="PRACTICE", nonce="g2")
    r1 = p.start(c, s1, topic=2, question_type="TRUE_FALSE", seed=11)
    assert r1["data"]["session"]["active_reference"]["kind"] == "question"
    assert s2.active_reference == {}


def test_no_double_mastery(tmp_path):
    app = build_app(tmp_path)
    _, p, _, _, _ = allw(app)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="h")
    q = p.start(c, s, topic=2, question_type="TRUE_FALSE",
                seed=11)["data"]["question"]
    a = p.submit_answer(c, s, "V", attempt_id="att-h-1")
    b = p.submit_answer(c, a["data"]["session"], "V", attempt_id="att-h-1")
    assert b["data"]["result"]["replayed"] is True
    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % app.students.store.path,
                          uri=True)
    try:
        n = con.execute("SELECT COUNT(*) FROM mastery_events WHERE "
                        "attempt_id='att-h-1'").fetchone()[0]
    finally:
        con.close()
    assert n == 2  # topic+section, una sola vez cada una


def test_no_provenance_break(tmp_path):
    app = build_app(tmp_path)
    _, p, _, _, _ = allw(app)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="i")
    q = p.start(c, s, topic=2, question_type="TRUE_FALSE",
                seed=11)["data"]["question"]
    out = p.submit_answer(c, s, "V", attempt_id="att-i-1")
    assert out["data"]["result"]["attempt_id"] == "att-i-1"
    assert out["data"]["result"]["mastery"]


def test_isolation_AB(tmp_path):
    app = build_app(tmp_path)
    _, p, _, _, _ = allw(app)
    ca = ctx(app, workflow="PRACTICE")
    sa = sess(app, workflow="PRACTICE", nonce="j")
    cb = ctx(app, student="alu-2", workflow="PRACTICE")
    sb = sess(app, student="alu-2", workflow="PRACTICE", nonce="j")
    ra = p.start(ca, sa, topic=2, question_type="TRUE_FALSE", seed=11)
    rb = p.start(cb, sb, topic=2, question_type="TRUE_FALSE", seed=22)
    assert (ra["data"]["question"]["question_id"] !=
            rb["data"]["question"]["question_id"])
    with pytest.raises(AppError):
        p.submit_answer(cb, ra["data"]["session"], "V")
