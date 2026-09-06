"""Tests Fase 7 Bloque 3: grading + scoring + ExamResult.

24 casos del benchmark (fuente unica:
data/evaluation/exam_grading_benchmark.jsonl) + unidades de scoring
entero, inmutabilidad, puertas anti-fuga e invariantes F5. Sin UI,
sin Fase 8.
"""
import filecmp
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.exam.grading import (  # noqa: E402
    ExamGradingService,
    avail_thou,
    fmt_pct,
    fmt_thou,
    pct_hundredths,
    thou,
)
from app.exam_grading_benchmark import load_cases, run_case  # noqa: E402

CASES = {c["case_id"]: c for c in load_cases()}


# ---------- 24 casos del benchmark ----------
@pytest.mark.parametrize("case_id", sorted(CASES), ids=sorted(CASES))
def test_benchmark_case(tmp_path, case_id):
    ok, detail = run_case(CASES[case_id], tmp_path)
    assert ok, "%s: %r" % (case_id, detail.get("fails"))


# ---------- scoring entero ----------
def test_money_helpers_exact():
    assert thou(8.5, 1.0) == 850
    assert thou(0.0, 2.5) == 0
    assert avail_thou(1.0) == 1000
    assert fmt_thou(1450) == "1.450"
    assert fmt_thou(0) == "0.000"
    assert fmt_pct(7250) == "72.50"
    assert fmt_pct(0) == "0.00"
    # Dominio no negativo (notas 0..10, puntos > 0): sin negativos.
    assert pct_hundredths(1450, 2000) == 7250
    assert pct_hundredths(5, 0) == 0


def test_decimal_not_float_round():
    # round(2.675, 2) flotante da 2.67 (binario); HALF_UP decimal da 268.
    # Por eso el scoring usa Decimal, nunca round() de Python (§10).
    assert thou(2.675, 1.0) == 268
    assert round(2.675, 2) == 2.67  # el binario traiciona: 2.675 < 2.675


# ---------- F5 aditivo intacto ----------
def test_correction_exam_fields_default():
    from app.correction.models import Correction
    import inspect as _insp
    sig = _insp.signature(Correction)
    assert sig.parameters["exam_id"].default == ""
    assert sig.parameters["session_id"].default == ""
    c = Correction(correction_id="c", attempt_id="a", question_id="q",
                   question_version="4.0", score=1.0, max_score=10.0,
                   percentage=10.0, status="CORRECT")
    assert c.exam_id == "" and c.session_id == ""
    d = c.to_dict()
    assert d["exam_id"] == "" and d["session_id"] == ""


def test_correct_submit_accept_session_id():
    import inspect as _insp
    from app.correction.service import CorrectionService
    from app.student.service import StudentService
    assert _insp.signature(
        CorrectionService.correct).parameters["session_id"].default == ""
    assert _insp.signature(
        StudentService.submit).parameters["session_id"].default == ""


# ---------- inmutabilidad y puertas ----------
def test_grading_incomplete_then_resume(tmp_path):
    """Fallo inesperado -> GRADING_INCOMPLETE explicito, SUBMITTED intacto,
    reintento limpio sin duplicar (inyeccion de fallo, no mock de F5)."""
    from app.exam.service import ExamSessionService
    from app.exam.grading import ExamGradingService
    from app.exam.models import ExamError
    from app.student.service import StudentService
    from app.exam_grading_benchmark import _gen_pool
    pool = [{"topic": 2, "type": "TRUE_FALSE", "seed": 11}]
    _gen_pool(tmp_path, pool)
    sdb, qdb = str(tmp_path / "s.sqlite"), str(tmp_path / "pool.sqlite")
    exam = ExamSessionService(sdb, qdb,
                              str(ROOT / "data/processed/knowledge.sqlite"))
    stu = StudentService(str(ROOT / "data/processed/knowledge.sqlite"),
                         qdb, sdb)
    bp = {"title": "T", "version": "1", "seed": 7, "question_count": 1,
          "topics": [2], "types": {"TRUE_FALSE": 1},
          "difficulty": {"EASY": 1.0}, "exam_kind": "MOCK_EXAM"}
    eid = exam.store_blueprint(bp)["exam_id"]
    exam.prepare_exam(eid)
    sid = exam.create_session(eid, "alu-1")["session_id"]
    exam.prepare_session(sid, "alu-1")
    exam.start_session(sid, "alu-1", now="2026-09-05T10:00:00+00:00")
    exam.save_answer(sid, 0, "V", "alu-1", now="2026-09-05T10:01:00+00:00")
    exam.submit_session(sid, "alu-1", now="2026-09-05T10:04:00+00:00")
    grading = ExamGradingService(exam, stu)
    real = stu.correction.correct
    calls = []

    def boom(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("proveedor caido (inyectado)")
        return real(*a, **k)

    stu.correction.correct = boom
    try:
        with pytest.raises(ExamError, match="GRADING_INCOMPLETE"):
            grading.grade(sid, "alu-1", now="2026-09-05T10:05:00+00:00")
    finally:
        stu.correction.correct = real
    assert exam.session_status(sid)["status"] == "SUBMITTED"
    res = grading.grade(sid, "alu-1", now="2026-09-05T10:05:00+00:00")
    assert res["status"] == "COMPLETE" and res["percentage"] == "85.00"
    assert exam.session_status(sid)["status"] == "GRADED"


def test_graded_session_rejects_answers(tmp_path):
    from app.exam.service import ExamSessionService
    from app.exam.models import ExamError
    from app.student.service import StudentService
    sdb, qdb = str(tmp_path / "s.sqlite"), str(tmp_path / "q.sqlite")
    from app.examiner.store import QuestionStore
    QuestionStore(qdb)
    exam = ExamSessionService(sdb, qdb, "kb")
    assert exam is not None
    with pytest.raises(ExamError):
        exam.save_answer("inexistente", 0, "x", "alu")


def test_result_gates_documented():
    import inspect as _insp
    import app.exam.grading as _g
    src = _insp.getsource(_g.ExamGradingService.get_result)
    assert "RESULT_NOT_AVAILABLE" in src
    src2 = _insp.getsource(_g.ExamGradingService.get_question_result)
    assert "get_result" in src2  # reutiliza la misma puerta


# ---------- determinismo entre procesos ----------
def test_cross_process_determinism(tmp_path):
    p1 = tmp_path / "r1.json"
    p2 = tmp_path / "r2.json"
    for p in (p1, p2):
        r = subprocess.run(
            [sys.executable, "app/exam_grading_benchmark.py",
             "--out", str(p)], cwd=str(ROOT), capture_output=True, text=True,
            timeout=600)
        assert r.returncode == 0, r.stderr[-2000:]
        assert "OK" in r.stdout
    assert filecmp.cmp(str(p1), str(p2), shallow=False)


def test_results_artifact_fresh():
    res = json.loads((ROOT / "data" / "evaluation"
                      / "exam_grading_results.json").read_text(
                          encoding="utf-8"))
    assert res["spec"] == "exam-spec-v1"
    assert len(res["cases"]) == 24
    assert all(not c["fails"] for c in res["cases"])
