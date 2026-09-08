"""Tests red-team frontera Application (B4.8): 18 casos + propagación."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from app.application.errors import AppError  # noqa: E402
from app.application.exam import ExamWorkflow  # noqa: E402
from app.application.practice import PracticeWorkflow  # noqa: E402
from app.application.tutor import TutorWorkflow  # noqa: E402
from harness import build_app, ctx, sess  # noqa: E402

BP = {"title": "t", "version": "1", "seed": 7, "duration_seconds": 600,
      "question_count": 1, "topics": [2], "types": {"TRUE_FALSE": 1},
      "difficulty": {"EASY": 1.0}, "exam_kind": "MOCK_EXAM"}


def exam_setup(app):
    w = ExamWorkflow(app)
    c = ctx(app, workflow="EXAM")
    s = sess(app, workflow="EXAM", nonce="sec")
    eid = app.exam_sessions.store_blueprint(BP)["exam_id"]
    app.exam_sessions.prepare_exam(eid)
    xsid = w.create(c, s, eid)["data"]["exam_session"]["session_id"]
    return w, c, s, xsid


def test_01_forged_student_id(tmp_path):
    app = build_app(tmp_path)
    w, c, s, xsid = exam_setup(app)
    c2 = ctx(app, student="intruso", workflow="EXAM")
    with pytest.raises(AppError):
        w.get_question(c2, s, xsid, 0)


def test_02_cross_student(tmp_path):
    app = build_app(tmp_path)
    _, p, _, _, _ = (None, PracticeWorkflow(app), None, None, None)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="x")
    p.start(c, s, topic=2, question_type="TRUE_FALSE", seed=11)
    c2 = ctx(app, student="alu-2", workflow="PRACTICE")
    with pytest.raises(AppError) as e:
        p.submit_answer(c2, s, "V")
    assert e.value.code == "NOT_FOUND"


def test_03_cross_session(tmp_path):
    app = build_app(tmp_path)
    w, c, s, xsid = exam_setup(app)
    w.prepare(c, s, xsid)
    w.start(c, s, xsid, now="2026-09-05T10:00:00+00:00")
    c2 = ctx(app, workflow="EXAM")
    s2 = sess(app, workflow="EXAM", nonce="other")
    with pytest.raises(AppError):
        w.get_question(c2, s2, xsid, 0)


def test_04_cross_exam(tmp_path):
    from app.application.review import ReviewWorkflow
    app = build_app(tmp_path)
    w = ExamWorkflow(app)
    r = ReviewWorkflow(app)
    c = ctx(app, workflow="EXAM")
    xsids = {}
    for nonce, title, seed in (("xa", "a", 7), ("xb", "b", 99)):
        s = sess(app, workflow="EXAM", nonce=nonce)
        eid = app.exam_sessions.store_blueprint(
            dict(BP, title=title, seed=seed))["exam_id"]
        app.exam_sessions.prepare_exam(eid)
        xsid = w.create(c, s, eid)["data"]["exam_session"]["session_id"]
        w.prepare(c, s, xsid)
        w.start(c, s, xsid, now="2026-09-05T10:00:00+00:00")
        w.save_answer(c, s, xsid, 0, "V", now="2026-09-05T10:01:00+00:00")
        w.submit(c, s, xsid, now="2026-09-05T10:04:00+00:00")
        w.grade(c, s, xsid, now="2026-09-05T10:05:00+00:00")
        xsids[nonce] = (xsid, eid)
    cr = ctx(app, workflow="REVIEW")
    for nonce, (xsid, eid) in xsids.items():
        sr = sess(app, workflow="REVIEW", nonce="xr-" + nonce)
        rev = r.get_review(cr, sr, xsid)["data"]
        assert rev["exam_id"] == eid
        assert {q["question_id"] for q in rev["questions"]}
    assert xsids["xa"][1] != xsids["xb"][1]


def test_05_forged_attempt(tmp_path):
    app = build_app(tmp_path)
    _, p, _, _, _ = (None, PracticeWorkflow(app), None, None, None)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="w")
    p.start(c, s, topic=2, question_type="TRUE_FALSE", seed=11)
    out = p.submit_answer(c, s, "V", attempt_id="att-forged-1")
    assert out["data"]["result"]["attempt_id"] == "att-forged-1"


def test_06_empty_ids(tmp_path):
    app = build_app(tmp_path)
    w, _, _, _ = exam_setup(app)
    c = ctx(app, workflow="EXAM")
    s = sess(app, workflow="EXAM", nonce="e")
    for fn in (lambda: w.create(c, s, ""),
               lambda: w.get_question(c, s, "", 0)):
        with pytest.raises(AppError):
            fn()


def test_07_malformed_ids(tmp_path):
    app = build_app(tmp_path)
    w, _, _, _ = exam_setup(app)
    c = ctx(app, workflow="EXAM")
    s = sess(app, workflow="EXAM", nonce="e")
    with pytest.raises(AppError):
        w.create(c, s, "../../etc/passwd")


def test_08_stale_session(tmp_path):
    app = build_app(tmp_path)
    w, c, s, xsid = exam_setup(app)
    w.prepare(c, s, xsid)
    w.start(c, s, xsid, now="2026-09-05T10:00:00+00:00")
    w.submit(c, s, xsid, now="2026-09-05T10:04:00+00:00")
    with pytest.raises(AppError):
        w.save_answer(c, s, xsid, 0, "V", now="2026-09-05T10:05:00+00:00")


def test_09_repeated_ids(tmp_path):
    app = build_app(tmp_path)
    _, p, _, _, _ = (None, PracticeWorkflow(app), None, None, None)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="r")
    p.start(c, s, topic=2, question_type="TRUE_FALSE", seed=11)
    a = p.submit_answer(c, s, "V", attempt_id="att-r-1")
    b = p.submit_answer(c, a["data"]["session"], "V", attempt_id="att-r-1")
    assert b["data"]["result"]["replayed"] is True


def test_10_enumeration(tmp_path):
    app = build_app(tmp_path)
    w = ExamWorkflow(app)
    c = ctx(app, workflow="EXAM")
    s = sess(app, workflow="EXAM", nonce="en")
    seen = set()
    for fake in ("exs-000000000000", "exs-ffffffffffff", "exs-111111111111"):
        with pytest.raises(AppError) as e:
            w.get_question(c, s, fake, 0)
        seen.add(e.value.code)
        assert "Traceback" not in str(e.value)
    assert seen == {"NOT_FOUND"}


def test_11_sqli_strings(tmp_path):
    app = build_app(tmp_path)
    w, _, _, _ = exam_setup(app)
    c = ctx(app, workflow="EXAM")
    s = sess(app, workflow="EXAM", nonce="sq")
    evil = "' OR '1'='1'; DROP TABLE exam_sessions; --"
    with pytest.raises(AppError):
        w.create(c, s, evil)
    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % app.exam_sessions.exams.path,
                          uri=True)
    try:
        n = con.execute("SELECT COUNT(*) FROM exam_sessions").fetchone()[0]
    finally:
        con.close()
    assert n >= 1


def test_12_path_traversal(tmp_path):
    app = build_app(tmp_path)
    _, p, _, _, _ = (None, PracticeWorkflow(app), None, None, None)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="pt")
    with pytest.raises(AppError):
        p.start(c, s, topic="../../etc", question_type="TRUE_FALSE")


def test_13_oversized_input(tmp_path):
    app = build_app(tmp_path)
    t = TutorWorkflow(app)
    c = ctx(app, workflow="TUTOR")
    with pytest.raises(AppError):
        t.ask(c, 12345)
    r = t.ask(ctx(app), "x" * 5000)
    assert r["ok"] in (True, False)
    if r["ok"]:
        assert r["data"]["answer"] or r["data"]["abstain"]


def test_14_invalid_workflow(tmp_path):
    app = build_app(tmp_path)
    with pytest.raises(AppError):
        ctx(app, workflow="HACK")


def test_15_invalid_state(tmp_path):
    app = build_app(tmp_path)
    w, c, s, xsid = exam_setup(app)
    with pytest.raises(AppError) as e:
        w.grade(c, s, xsid)
    assert e.value.code == "STATE_ERROR"


def test_16_hidden_field_request(tmp_path):
    app = build_app(tmp_path)
    w, c, s, xsid = exam_setup(app)
    w.prepare(c, s, xsid)
    w.start(c, s, xsid, now="2026-09-05T10:00:00+00:00")
    q = w.get_question(c, s, xsid, 0,
                       now="2026-09-05T10:01:00+00:00")["data"]["question"]
    assert "solution" not in q and "correct_answer" not in q


def test_17_error_codes_cover(tmp_path):
    from app.application.errors import AppError as AE, map_error
    for code in ("USER_ERROR", "VALIDATION_ERROR", "NOT_FOUND",
                 "STATE_ERROR", "KNOWLEDGE_ERROR", "RETRIEVAL_ERROR",
                 "GENERATION_ERROR", "CORRECTION_ERROR", "PERSISTENCE_ERROR",
                 "POLICY_ERROR", "INTERNAL_ERROR"):
        e = AE(code, "x")
        assert e.code == code and e.to_dict()["ok"] is False
    assert map_error(AE("NOT_FOUND", "x")).code == "NOT_FOUND"


def test_18_no_traceback_leak(tmp_path):
    app = build_app(tmp_path)
    w, _, _, _ = exam_setup(app)
    c = ctx(app, workflow="EXAM")
    s = sess(app, workflow="EXAM", nonce="tb")
    try:
        w.create(c, s, "exm-nope")
        raised = False
    except AppError as e:
        raised = "Traceback" not in str(e) and "File \"" not in str(e)
    assert raised
