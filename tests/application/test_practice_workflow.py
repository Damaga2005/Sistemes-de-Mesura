"""Tests PracticeWorkflow (B4.2/B4.6): delegación Examiner/F5, idempotencia."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from app.application.errors import AppError  # noqa: E402
from app.application.practice import PracticeWorkflow  # noqa: E402
from harness import build_app, ctx, sess  # noqa: E402


def wf(tmp_path):
    app = build_app(tmp_path)
    return app, PracticeWorkflow(app)


def start1(app, w, c, s, **kw):
    args = {"topic": 2, "question_type": "TRUE_FALSE", "seed": 11}
    args.update(kw)
    return w.start(c, s, **args)


def test_01_correct(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="PRACTICE"), sess(app, workflow="PRACTICE")
    r = start1(app, w, c, s)
    qid = r["data"]["question"]["question_id"]
    assert qid == "q-93f3e2c4c7fd"
    out = w.submit_answer(c, r["data"]["session"], "V")
    assert out["data"]["result"]["status"] == "CORRECT"
    assert out["data"]["result"]["score"] == 8.5


def test_02_wrong(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="PRACTICE"), sess(app, workflow="PRACTICE")
    r = start1(app, w, c, s)
    out = w.submit_answer(c, r["data"]["session"], "F")
    assert out["data"]["result"]["status"] == "INCORRECT"
    assert out["data"]["result"]["score"] == 0.0


def test_03_partial(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="PRACTICE"), sess(app, workflow="PRACTICE")
    r = start1(app, w, c, s, question_type="FORMULA",
               formula_id="eq-02-0034", seed=14)
    out = w.submit_answer(c, r["data"]["session"], "$U=k\\,u_c(y)$")
    assert out["data"]["result"]["status"] == "PARTIALLY_CORRECT"


def test_04_blank(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="PRACTICE"), sess(app, workflow="PRACTICE")
    r = start1(app, w, c, s)
    out = w.submit_answer(c, r["data"]["session"], "")
    assert out["data"]["result"]["status"] == "NO_ANSWER"


def test_05_invalid_question(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="PRACTICE"), sess(app, workflow="PRACTICE")
    with pytest.raises(AppError):
        w.submit_answer(c, s, "V")


def test_06_repeated_submit(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="PRACTICE"), sess(app, workflow="PRACTICE")
    r = start1(app, w, c, s)
    a = w.submit_answer(c, r["data"]["session"], "V",
                        attempt_id="att-rep-1")
    b = w.submit_answer(c, a["data"]["session"], "V",
                        attempt_id="att-rep-1")
    assert b["data"]["result"]["attempt_id"] == a["data"]["result"]["attempt_id"]
    assert b["data"]["result"]["replayed"] is True


def test_07_correction_failure(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="PRACTICE"), sess(app, workflow="PRACTICE")
    r = start1(app, w, c, s)
    real = app.students.correction.correct
    app.students.correction.correct = lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("corrector roto"))
    try:
        with pytest.raises(AppError) as e:
            w.submit_answer(c, r["data"]["session"], "V",
                            attempt_id="att-cf-1")
        assert e.value.code == "CORRECTION_ERROR"
    finally:
        app.students.correction.correct = real


def test_08_mastery_recorded(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="PRACTICE"), sess(app, workflow="PRACTICE")
    r = start1(app, w, c, s)
    out = w.submit_answer(c, r["data"]["session"], "V")
    units = [u["unit"] for u in out["data"]["result"]["mastery"]]
    assert "topic:T02" in units
    got = w.get_result(c, out["data"]["session"], units)
    assert got["data"]["mastery"][0]["attempt_count"] >= 1


def test_09_restart(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="PRACTICE"), sess(app, workflow="PRACTICE",
                                              nonce="r")
    r = start1(app, w, c, s)
    w.submit_answer(c, r["data"]["session"], "V", attempt_id="att-rs-1")
    import json
    blob = json.dumps(r["data"]["session"])
    from app.application.session import ApplicationSession
    s2 = ApplicationSession.from_dict(json.loads(blob))
    out = w.submit_answer(c, s2, "V", attempt_id="att-rs-1")
    assert out["data"]["result"]["replayed"] is True


def test_10_same_request_twice(tmp_path):
    app, w = wf(tmp_path)
    c = ctx(app, workflow="PRACTICE")
    s1 = sess(app, workflow="PRACTICE", nonce="same")
    s2 = sess(app, workflow="PRACTICE", nonce="same")
    r1 = start1(app, w, c, s1)
    r2 = start1(app, w, c, s2)
    assert (r1["data"]["question"]["question_id"] ==
            r2["data"]["question"]["question_id"])


def test_11_no_answer_key_in_view(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="PRACTICE"), sess(app, workflow="PRACTICE")
    r = start1(app, w, c, s)
    blob = str(r["data"]["question"])
    for bad in ("correct_answer", "solution", "distractor_reason",
                "expected_answer"):
        assert bad not in blob


def test_12_get_question(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="PRACTICE"), sess(app, workflow="PRACTICE")
    r = start1(app, w, c, s)
    g = w.get_question(c, r["data"]["session"])
    assert g["data"]["question_id"] == r["data"]["question"]["question_id"]


def test_13_complete(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="PRACTICE"), sess(app, workflow="PRACTICE")
    out = w.complete(c, s)
    assert out["data"]["session"]["status"] == "COMPLETED"


def test_14_cross_student_denied(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="PRACTICE"), sess(app, workflow="PRACTICE")
    r = start1(app, w, c, s)
    c2 = ctx(app, student="alu-2", workflow="PRACTICE")
    with pytest.raises(AppError) as e:
        w.submit_answer(c2, r["data"]["session"], "V")
    assert e.value.code == "NOT_FOUND"


def test_15_mastery_failure(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="PRACTICE"), sess(app, workflow="PRACTICE")
    r = start1(app, w, c, s)
    import sqlite3
    real_connect = sqlite3.connect

    def boom(*a, **k):
        raise sqlite3.OperationalError("disco lleno (inyectado)")

    sqlite3.connect = boom
    try:
        with pytest.raises(AppError) as e:
            w.submit_answer(c, r["data"]["session"], "V",
                            attempt_id="att-mf-1")
        assert e.value.code in ("PERSISTENCE_ERROR", "CORRECTION_ERROR")
    finally:
        sqlite3.connect = real_connect
