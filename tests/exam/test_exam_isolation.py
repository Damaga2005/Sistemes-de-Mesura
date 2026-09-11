"""Tests Fase 11 Bloque E-F: Exam Mode como evaluacion cerrada.

Sin adaptive durante el examen, sesion estable, ciego REAL_EXAM,
metricas agregadas, idempotencia, aislamiento multi-estudiante.
DBs temporales.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.exam.grading import ExamGradingService  # noqa: E402
from app.exam.models import ExamError  # noqa: E402
from app.exam.review import ExamReviewService  # noqa: E402
from app.exam.service import ExamSessionService  # noqa: E402
from app.examiner.service import ExaminerEngine  # noqa: E402
from app.retrieval.service import RetrievalService  # noqa: E402
from app.student.service import StudentService  # noqa: E402
from app.exam_grading_benchmark import _gen_pool  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
INDEX = str(ROOT / "data" / "index")

BP = {"title": "T", "version": "1", "seed": 7, "question_count": 2,
      "topics": [2], "types": {"TRUE_FALSE": 2},
      "difficulty": {"EASY": 1.0}, "exam_kind": "MOCK_EXAM"}
T0 = "2026-09-05T10:00:00+00:00"


def _wired(tmp_path, pool=None):
    _gen_pool(tmp_path, pool or [{"topic": 2, "type": "TRUE_FALSE",
                                  "seed": 11},
                                 {"topic": 2, "type": "TRUE_FALSE",
                                  "seed": 22}])
    sdb, qdb = str(tmp_path / "s.sqlite"), str(tmp_path / "pool.sqlite")
    exam = ExamSessionService(sdb, qdb, KB)
    stu = StudentService(KB, qdb, sdb)
    return exam, stu, ExamGradingService(exam, stu), ExamReviewService(
        exam, ExamGradingService(exam, stu), stu, KB)


def _full(exam, grading, bp, answers, sid="alu-1"):
    eid = exam.store_blueprint(dict(bp))["exam_id"]
    exam.prepare_exam(eid)
    xsid = exam.create_session(eid, sid)["session_id"]
    exam.prepare_session(xsid, sid)
    exam.start_session(xsid, sid, now=T0)
    for pos, ans in enumerate(answers):
        exam.save_answer(xsid, pos, ans, sid,
                         now="2026-09-05T10:01:00+00:00")
    exam.submit_session(xsid, sid, now="2026-09-05T10:04:00+00:00")
    res = grading.grade(xsid, sid, now="2026-09-05T10:05:00+00:00")
    return eid, xsid, res


# ---------- Bloque J-16/17: config determinista ----------
def test_config_valid_and_seed_deterministic(tmp_path):
    exam, _, _, _ = _wired(tmp_path)
    e1 = exam.store_blueprint(dict(BP))["exam_id"]
    e2 = exam.store_blueprint(dict(BP))["exam_id"]
    assert e1 == e2
    other = dict(BP, seed=8)
    assert exam.store_blueprint(other)["exam_id"] != e1


def test_config_invalid_rejected(tmp_path):
    exam, _, _, _ = _wired(tmp_path)
    with pytest.raises(ExamError):
        exam.store_blueprint({"title": "", "question_count": 0,
                              "topics": []})


# ---------- Bloque J-18/19/20: sesion cerrada, sin adaptacion ----------
def test_session_question_set_stable(tmp_path):
    exam, _, grading, _ = _wired(tmp_path)
    eid, xsid, _ = _full(exam, grading, BP, ["V", "F"])
    first = [q["question_id"] for q in
             exam.read_session(xsid, "alu-1")["instances"]]
    assert len(first) == 2
    second = [q["question_id"] for q in
              exam.read_session(xsid, "alu-1")["instances"]]
    assert first == second
    # responder no altera el conjunto (sin regeneracion adaptativa)
    assert exam.session_status(xsid)["status"] == "GRADED"


def test_exam_modules_do_not_import_adaptive():
    import inspect as _insp
    import re as _re
    import app.exam.service as _s
    import app.exam.grading as _g
    import app.exam.review as _r
    import app.exam.models as _m
    for mod in (_s, _g, _r, _m):
        for ln in _insp.getsource(mod).splitlines():
            s = ln.strip()
            if s.startswith("import ") or s.startswith("from "):
                assert "adaptive" not in s and "AdaptiveLoop" not in s, \
                    (mod.__name__, s)


# ---------- Bloque J-21/22/23: ciego + metricas ----------
def test_mock_review_reveals_but_real_blinds(tmp_path):
    exam, _, grading, review = _wired(tmp_path)
    _, xsid, _ = _full(exam, grading, BP, ["V", "F"])
    fb = review.get_review_question(xsid, 0, "alu-1")["feedback"]
    assert fb["correct_answer"] not in (None, "")
    real = dict(BP, exam_kind="REAL_EXAM")
    _, xs2, _ = _full(exam, grading, real, ["V", "F"])
    fb2 = review.get_review_question(xs2, 0, "alu-1")["feedback"]
    assert fb2["correct_answer"] is None
    assert fb2["solution"] is None
    assert fb2["score"] is not None  # la nota no es secreta


def test_result_aggregates(tmp_path):
    exam, _, grading, _ = _wired(tmp_path)
    _, _, res = _full(exam, grading, BP, ["V", "F"])
    for k in ("total_points", "earned_points", "percentage",
              "question_count", "answered_count", "blank_count",
              "correct_count", "partial_count", "incorrect_count"):
        assert k in res, k
    assert res["question_count"] == 2
    assert res["answered_count"] == 2
    assert res["correct_count"] + res["partial_count"] + \
        res["incorrect_count"] == 2


# ---------- Bloque J-24/25: idempotencia ----------
def test_finish_idempotent(tmp_path):
    exam, _, grading, _ = _wired(tmp_path)
    _, xsid, first = _full(exam, grading, BP, ["V", "F"])
    second = grading.grade(xsid, "alu-1",
                           now="2026-09-05T10:05:00+00:00")
    assert second["percentage"] == first["percentage"]
    assert second["graded_at"] == first["graded_at"]


def test_submit_idempotent(tmp_path):
    exam, _, grading, _ = _wired(tmp_path)
    eid = exam.store_blueprint(dict(BP))["exam_id"]
    exam.prepare_exam(eid)
    xsid = exam.create_session(eid, "alu-1")["session_id"]
    exam.prepare_session(xsid, "alu-1")
    exam.start_session(xsid, "alu-1", now=T0)
    exam.save_answer(xsid, 0, "V", "alu-1",
                     now="2026-09-05T10:01:00+00:00")
    a = exam.submit_session(xsid, "alu-1",
                            now="2026-09-05T10:04:00+00:00")
    b = exam.submit_session(xsid, "alu-1",
                            now="2026-09-05T10:04:00+00:00")
    assert a["status"] == b["status"] == "SUBMITTED"
    grading.grade(xsid, "alu-1", now="2026-09-05T10:05:00+00:00")


# ---------- Bloque J: mastery documentado + multi-estudiante ----------
def test_grade_records_mastery_explicitly(tmp_path):
    # Decision documentada: el grading comparte StudentService.submit,
    # luego las respuestas de examen actualizan mastery/history igual
    # que practice. Sin mecanismo separado de sync.
    exam, stu, grading, _ = _wired(tmp_path)
    _, xsid, _ = _full(exam, grading, BP, ["V", "F"])
    assert stu.get_mastery("alu-1", "topic:T02") is not None
    assert exam.session_status(xsid)["status"] == "GRADED"


def test_cross_student_denied(tmp_path):
    exam, _, grading, _ = _wired(tmp_path)
    eid = exam.store_blueprint(dict(BP))["exam_id"]
    exam.prepare_exam(eid)
    xsid = exam.create_session(eid, "alu-1")["session_id"]
    with pytest.raises(ExamError):
        exam.start_session(xsid, "alu-2", now=T0)
    exam.prepare_session(xsid, "alu-1")
    exam.start_session(xsid, "alu-1", now=T0)
    exam.save_answer(xsid, 0, "V", "alu-1",
                     now="2026-09-05T10:01:00+00:00")
    with pytest.raises(ExamError):
        exam.save_answer(xsid, 0, "V", "alu-2",
                         now="2026-09-05T10:01:00+00:00")
    exam.submit_session(xsid, "alu-1", now="2026-09-05T10:04:00+00:00")
    grading.grade(xsid, "alu-1", now="2026-09-05T10:05:00+00:00")
    with pytest.raises(ExamError):
        grading.get_result(xsid, "alu-2")


def test_results_isolated_per_student(tmp_path):
    exam, _, grading, _ = _wired(tmp_path)
    _, x1, r1 = _full(exam, grading, BP, ["V", "F"], sid="alu-1")
    _, x2, r2 = _full(exam, grading, BP, ["F", "V"], sid="alu-2")
    assert x1 != x2
    assert grading.get_result(x1, "alu-1")["percentage"] == \
        r1["percentage"]
    assert grading.get_result(x2, "alu-2")["percentage"] == \
        r2["percentage"]
