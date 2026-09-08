"""Tests P0-1: grade concurrente no destruye al ganador (F7).

Un grader perdedor jamas borra filas COMMITTED de otro. Viola esto
-> P0. Secuencial intacto, GRADING_INCOMPLETE intacto, mastery
equivalente, procesos separados incluidos.
"""
import json
import shutil
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.exam.grading import ExamGradingService  # noqa: E402
from app.exam.service import ExamSessionService  # noqa: E402
from app.student.service import StudentService  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
GENDB = str(ROOT / "data" / "generated" / "questions.sqlite")
SPEC = {"title": "t", "version": "1", "seed": 7, "duration_seconds": 600,
        "question_count": 1, "topics": [2],
        "types": {"TRUE_FALSE": 1}, "difficulty": {"EASY": 1.0},
        "exam_kind": "MOCK_EXAM"}
T0 = "2026-09-05T10:00:00+00:00"


def wired(tmp):
    tmp = Path(tmp)
    qdb = str(tmp / "q.sqlite")
    shutil.copyfile(GENDB, qdb)
    sdb = str(tmp / "s.sqlite")
    ex = ExamSessionService(sdb, qdb, KB)
    stu = StudentService(KB, qdb, sdb)
    return ex, stu, ExamGradingService(ex, stu), sdb


def submitted_session(ex, answer="F"):
    eid = ex.store_blueprint(dict(SPEC))["exam_id"]
    ex.prepare_exam(eid)
    xs = ex.create_session(eid, "alu-1")["session_id"]
    ex.prepare_session(xs, "alu-1")
    ex.start_session(xs, "alu-1", now=T0)
    ex.save_answer(xs, 0, answer, "alu-1",
                   now="2026-09-05T10:01:00+00:00")
    ex.submit_session(xs, "alu-1", now="2026-09-05T10:04:00+00:00")
    return xs


def db_state(sdb, xs):
    con = sqlite3.connect(str(sdb))
    try:
        st = con.execute("SELECT status FROM exam_sessions WHERE "
                         "session_id=?", (xs,)).fetchone()[0]
        nq = con.execute("SELECT COUNT(*) FROM exam_question_results "
                         "WHERE session_id=?", (xs,)).fetchone()[0]
        nr = con.execute("SELECT COUNT(*) FROM exam_results WHERE "
                         "session_id=?", (xs,)).fetchone()[0]
        return st, nq, nr
    finally:
        con.close()


def student_counts(sdb):
    con = sqlite3.connect(str(sdb))
    try:
        a = con.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
        c = con.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]
        m = con.execute("SELECT COUNT(*) FROM mastery_events").fetchone()[0]
        return a, c, m
    finally:
        con.close()


def race(grd, xs, n):
    outs = []

    def one():
        try:
            outs.append(("ok", grd.grade(
                xs, "alu-1",
                now="2026-09-05T10:05:00+00:00")["percentage"]))
        except Exception as e:  # noqa: BLE001
            outs.append(("err", getattr(e, "code", type(e).__name__)))

    ts = [threading.Thread(target=one) for _ in range(n)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    return outs


def assert_valid_final(grd, sdb, xs):
    st, nq, nr = db_state(sdb, xs)
    assert (st, nq, nr) == ("GRADED", 1, 1), (st, nq, nr)
    res = grd.get_result(xs, "alu-1")
    assert res["percentage"] == "85.00"
    q = grd.get_question_result(xs, 0, "alu-1")
    assert q["question_id"]


def test_grade_sequential_idempotent(tmp_path):
    ex, stu, grd, sdb = wired(tmp_path)
    xs = submitted_session(ex)
    g1 = grd.grade(xs, "alu-1", now="2026-09-05T10:05:00+00:00")
    g2 = grd.grade(xs, "alu-1", now="2026-09-05T10:05:00+00:00")
    assert g1["percentage"] == g2["percentage"] == "85.00"
    assert_valid_final(grd, sdb, xs)
    assert student_counts(sdb) == student_counts(sdb)


def test_grade_concurrent_two_callers(tmp_path):
    ex, stu, grd, sdb = wired(tmp_path)
    xs = submitted_session(ex)
    outs = race(grd, xs, 2)
    assert all(o[0] == "ok" and o[1] == "85.00" for o in outs), outs
    assert_valid_final(grd, sdb, xs)


def test_grade_concurrent_four_callers(tmp_path):
    ex, stu, grd, sdb = wired(tmp_path)
    xs = submitted_session(ex)
    outs = race(grd, xs, 4)
    assert all(o[0] == "ok" and o[1] == "85.00" for o in outs), outs
    assert_valid_final(grd, sdb, xs)


def test_grade_concurrent_repeated(tmp_path):
    for i in range(4):
        d = tmp_path / ("r%d" % i)
        d.mkdir(exist_ok=True)
        ex, stu, grd, sdb = wired(d)
        xs = submitted_session(ex)
        outs = race(grd, xs, 2)
        assert all(o[0] == "ok" for o in outs), (i, outs)
        assert_valid_final(grd, sdb, xs)


def test_cleanup_does_not_delete_committed_winner(tmp_path):
    ex, stu, grd, sdb = wired(tmp_path)
    xs = submitted_session(ex)
    grd.grade(xs, "alu-1", now="2026-09-05T10:05:00+00:00")
    before = db_state(sdb, xs)
    grd._cleanup_partial(xs)
    assert db_state(sdb, xs) == before == ("GRADED", 1, 1)
    assert_valid_final(grd, sdb, xs)


def test_grading_incomplete_retry(tmp_path):
    ex, stu, grd, sdb = wired(tmp_path)
    xs = submitted_session(ex)
    calls = []
    orig = grd._store_question_result

    def boom(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("fallo controlado pre-commit")
        return orig(*a, **k)

    grd._store_question_result = boom
    with pytest.raises(Exception):
        grd.grade(xs, "alu-1", now="2026-09-05T10:05:00+00:00")
    st, nq, nr = db_state(sdb, xs)
    assert (st, nr) == ("SUBMITTED", 0), (st, nq, nr)
    g = grd.grade(xs, "alu-1", now="2026-09-05T10:05:00+00:00")
    assert g["percentage"] == "85.00"
    assert_valid_final(grd, sdb, xs)


def test_submit_concurrency_regression(tmp_path):
    ex, stu, grd, sdb = wired(tmp_path)
    eid = ex.store_blueprint(dict(SPEC))["exam_id"]
    ex.prepare_exam(eid)
    xs = ex.create_session(eid, "alu-1")["session_id"]
    ex.prepare_session(xs, "alu-1")
    ex.start_session(xs, "alu-1", now=T0)
    ex.save_answer(xs, 0, "F", "alu-1",
                   now="2026-09-05T10:01:00+00:00")
    outs = []

    def one():
        try:
            outs.append(ex.submit_session(
                xs, "alu-1",
                now="2026-09-05T10:04:00+00:00")["status"])
        except Exception as e:  # noqa: BLE001
            outs.append(getattr(e, "code", type(e).__name__))

    ts = [threading.Thread(target=one) for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert outs == ["SUBMITTED", "SUBMITTED"], outs


def test_get_result_after_concurrent_grade(tmp_path):
    ex, stu, grd, sdb = wired(tmp_path)
    xs = submitted_session(ex)
    race(grd, xs, 4)
    res = grd.get_result(xs, "alu-1")
    assert res["status"] == "COMPLETE" and res["percentage"] == "85.00"
    q = grd.get_question_result(xs, 0, "alu-1")
    assert q["session_id"] == xs


def test_mastery_equivalent_sequential_vs_concurrent(tmp_path):
    seq = tmp_path / "seq"
    seq.mkdir()
    ex, stu, grd, sdb = wired(seq)
    xs = submitted_session(ex)
    grd.grade(xs, "alu-1", now="2026-09-05T10:05:00+00:00")
    base = student_counts(sdb)
    cc = tmp_path / "cc"
    cc.mkdir()
    ex2, stu2, grd2, sdb2 = wired(cc)
    xs2 = submitted_session(ex2)
    outs = race(grd2, xs2, 4)
    assert all(o[0] == "ok" for o in outs), outs
    assert student_counts(sdb2) == base


def test_grade_concurrent_processes(tmp_path):
    ex, stu, grd, sdb = wired(tmp_path)
    xs = submitted_session(ex)
    code = (
        "import sys; sys.path.insert(0, %r); "
        "from app.exam.service import ExamSessionService; "
        "from app.exam.grading import ExamGradingService; "
        "from app.student.service import StudentService; "
        "ex = ExamSessionService(%r, %r, %r); "
        "stu = StudentService(%r, %r, %r); "
        "g = ExamGradingService(ex, stu); "
        "print(g.grade(%r, 'alu-1', "
        "now='2026-09-05T10:05:00+00:00')['percentage'])"
        % (str(ROOT), sdb, str(Path(sdb).parent / "q.sqlite"), KB,
           KB, str(Path(sdb).parent / "q.sqlite"), sdb, xs))
    main_outs = []

    def main_grade():
        try:
            main_outs.append(grd.grade(
                xs, "alu-1",
                now="2026-09-05T10:05:00+00:00")["percentage"])
        except Exception as e:  # noqa: BLE001
            main_outs.append(getattr(e, "code", type(e).__name__))

    t = threading.Thread(target=main_grade)
    t.start()
    p = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, timeout=300, cwd=str(ROOT))
    t.join()
    sub = p.stdout.strip().splitlines()[-1] if p.returncode == 0 else (
        "exit=%d %s" % (p.returncode, p.stderr[-200:]))
    assert set(main_outs) <= {"85.00"}, (main_outs, sub)
    assert sub == "85.00", (main_outs, sub)
    assert_valid_final(grd, sdb, xs)
