"""Tests Fase 7 Bloque 5: review + views + policies.

38 casos del benchmark (fuente unica:
data/evaluation/exam_review_benchmark.jsonl) + autoridad, provider,
inmutabilidad, IDOR, i18n y determinismo. Sin UI, sin Fase 8.
"""
import filecmp
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.exam import review as RV  # noqa: E402
from app.exam.models import ExamError  # noqa: E402
from app.exam.review_policy import (  # noqa: E402
    REVIEW_POLICY,
    effective_policy,
)
from app.exam_review_benchmark import (  # noqa: E402
    _gen_pool,
    _services,
    load_cases,
    run_case,
)

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
CASES = {c["case_id"]: c for c in load_cases()}

POOL_TF = [{"topic": 2, "type": "TRUE_FALSE", "seed": 11}]
BP_TF = {"title": "T", "version": "1", "seed": 7, "duration_seconds": 600,
         "question_count": 1, "topics": [2], "types": {"TRUE_FALSE": 1},
         "difficulty": {"EASY": 1.0}, "exam_kind": "MOCK_EXAM"}


def _flow(tmp_path):
    _gen_pool(tmp_path, POOL_TF)
    exam, stu, grading, rev = _services(tmp_path)
    from app.exam.review import ExamReviewService
    rev = ExamReviewService(exam, grading, stu, KB)
    eid = exam.store_blueprint(BP_TF)["exam_id"]
    exam.prepare_exam(eid)
    sid = exam.create_session(eid, "alu-1")["session_id"]
    exam.prepare_session(sid, "alu-1")
    exam.start_session(sid, "alu-1", now="2026-09-05T10:00:00+00:00")
    return exam, stu, grading, rev, sid


# ---------- 38 casos del benchmark ----------
@pytest.mark.parametrize("case_id", sorted(CASES), ids=sorted(CASES))
def test_benchmark_case(tmp_path, case_id):
    ok, detail = run_case(CASES[case_id], tmp_path)
    assert ok, "%s: %r" % (case_id, detail.get("fails"))


# ---------- autoridad unica ----------
def _allows(view, st, **kw):
    try:
        return RV.check_view(view, st, **kw) is True
    except ExamError:
        return False


def test_authority_matrix():
    allow = {("STEM", "IN_PROGRESS"), ("RESULT", "GRADED"),
             ("RESULT", "SUBMITTED"), ("REVIEW", "GRADED"),
             ("MASTERY", "GRADED")}
    for view in ("STEM", "RESULT", "REVIEW", "MASTERY"):
        for st in ("CREATED", "READY", "IN_PROGRESS", "SUBMITTED",
                   "EXPIRED", "GRADED", "CANCELLED"):
            assert _allows(view, st, has_result=True, complete=True) \
                == ((view, st) in allow)
    # Condicionales con fila/complete
    assert RV.check_view("RESULT", "SUBMITTED", has_result=True) is True
    with pytest.raises(ExamError):
        RV.check_view("RESULT", "SUBMITTED", has_result=False)
    with pytest.raises(ExamError):
        RV.check_view("REVIEW", "GRADED", complete=False)
    with pytest.raises(ExamError):
        RV.check_view("NOPE", "GRADED")


def test_legacy_gates_match_authority():
    # STEM legacy <=> autoridad; RESULT legacy <=> autoridad con fila.
    for st in ("CREATED", "READY", "IN_PROGRESS", "SUBMITTED", "EXPIRED",
               "GRADED", "CANCELLED"):
        legacy_stem = (st == "IN_PROGRESS")
        assert _allows("STEM", st) == legacy_stem
        legacy_result = st in ("SUBMITTED", "GRADED")
        assert _allows("RESULT", st, has_result=True) == legacy_result


# ---------- provider provenance ----------
class _FakeProvider:
    provider_name = "fake-test"
    model_name = "fake-1"

    def __init__(self, evidence_id):
        self._eid = evidence_id

    def generate(self, messages, *, temperature=0.0, max_tokens=600):
        class _R:
            pass
        r = _R()
        r.text = json.dumps({"hints": [
            {"criterion": "REASONING", "assessment": "review",
             "evidence_ids": [self._eid], "detail": "mirar mejor"}]})
        return r


def test_provider_stamp_only_when_assisted(tmp_path):
    from app.student.service import StudentService
    _gen_pool(tmp_path, [{"topic": 2, "type": "SHORT_ANSWER", "seed": 13}])
    svc = StudentService(KB, str(tmp_path / "pool.sqlite"),
                         str(tmp_path / "s.sqlite"))
    con = __import__("sqlite3").connect(
        "file:%s?mode=ro" % (tmp_path / "pool.sqlite"), uri=True)
    try:
        body = json.loads(con.execute(
            "SELECT body_json FROM questions").fetchone()[0])
    finally:
        con.close()
    qid = body["question_id"]
    ev0 = (body.get("evidence_refs", []) or ["x"])[0]
    plain = svc.correction.correct(qid, body.get("expected_answer", ""),
                                   attempt_id="att-p-1")
    assert plain.provider == "" and plain.model == ""
    assisted = svc.correction.correct(
        qid, "respuesta parcial dubtosa", attempt_id="att-p-2",
        llm_assist=True, provider=_FakeProvider(ev0))
    assert assisted.provider == "fake-test" and assisted.model == "fake-1"
    assert any(e.error_type == "AMBIGUOUS_ANSWER"
               for e in assisted.detected_errors)
    assert any(r.source == "llm-assisted" for r in assisted.criteria_results)


# ---------- inmutabilidad y no-write ----------
def test_review_reads_change_nothing(tmp_path):
    exam, stu, grading, rev, sid = _flow(tmp_path)
    exam.save_answer(sid, 0, "V", "alu-1", now="2026-09-05T10:01:00+00:00")
    exam.submit_session(sid, "alu-1", now="2026-09-05T10:04:00+00:00")
    grading.grade(sid, "alu-1", now="2026-09-05T10:05:00+00:00")
    import hashlib
    import sqlite3
    db = exam.exams.path

    def snap():
        con = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
        try:
            rows = con.execute("SELECT session_id, position, question_id,"
                               " answer, version FROM session_answers ORDER BY"
                               " position").fetchall()
            res = con.execute("SELECT session_id, earned_req_thou,"
                              " percentage_hund, status FROM exam_results"
                              ).fetchall()
            mev = con.execute("SELECT COUNT(*) FROM mastery_events"
                              ).fetchone()[0]
        finally:
            con.close()
        blob = json.dumps([rows, res, mev], sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest(), mev

    before, mev0 = snap()
    rev.get_review(sid, "alu-1")
    rev.get_review_question(sid, 0, "alu-1")
    rev.get_mastery_view("alu-1", sid)
    after, mev1 = snap()
    assert before == after and mev0 == mev1


def test_mastery_view_gated_pre_grade(tmp_path):
    exam, stu, grading, rev, sid = _flow(tmp_path)
    with pytest.raises(ExamError):
        rev.get_mastery_view("alu-1", sid)


# ---------- aislamiento cruzado ----------
def test_cross_exam_no_mix(tmp_path):
    exam, stu, grading, rev, sid = _flow(tmp_path)
    exam.save_answer(sid, 0, "V", "alu-1", now="2026-09-05T10:01:00+00:00")
    exam.submit_session(sid, "alu-1", now="2026-09-05T10:04:00+00:00")
    grading.grade(sid, "alu-1", now="2026-09-05T10:05:00+00:00")
    bp2 = dict(BP_TF, title="Otro")
    eid2 = exam.store_blueprint(bp2)["exam_id"]
    exam.prepare_exam(eid2)
    sid2 = exam.create_session(eid2, "alu-1")["session_id"]
    exam.prepare_session(sid2, "alu-1")
    exam.start_session(sid2, "alu-1", now="2026-09-05T10:00:00+00:00")
    exam.save_answer(sid2, 0, "F", "alu-1", now="2026-09-05T10:01:00+00:00")
    exam.submit_session(sid2, "alu-1", now="2026-09-05T10:04:00+00:00")
    grading.grade(sid2, "alu-1", now="2026-09-05T10:05:00+00:00")
    r1 = {q["question_id"] for q in rev.get_review(sid, "alu-1")["questions"]}
    r2 = {q["question_id"] for q in rev.get_review(sid2, "alu-1")["questions"]}
    assert r1 and r2
    f1 = rev.get_review(sid, "alu-1")["questions"][0]["feedback"]
    f2 = rev.get_review(sid2, "alu-1")["questions"][0]["feedback"]
    assert f1["status"] == "CORRECT" and f2["status"] == "INCORRECT"


# ---------- i18n y pureza ----------
def test_no_llm_no_cache_in_review():
    for name in ("review.py", "review_policy.py"):
        src = (ROOT / "app" / "exam" / name).read_text(encoding="utf-8")
        for t in ("generate(", "llm_client", "Gemini", "gemini", "openai",
                  "anthropic", "lru_cache", "cache journal", "_CACHE ="):
            assert t not in src, (name, t)


def test_review_policy_frozen():
    import dataclasses
    assert REVIEW_POLICY.status == "active"
    with pytest.raises(dataclasses.FrozenInstanceError):
        REVIEW_POLICY.status = "x"
    assert effective_policy("REAL_EXAM")["parameters"][
        "reveal_solution"] is False


def test_results_artifact_fresh():
    res = json.loads((ROOT / "data" / "evaluation"
                      / "exam_review_results.json").read_text(
                          encoding="utf-8"))
    assert res["spec"] == "review-policy-v1"
    assert len(res["cases"]) == 38
    assert all(not c["fails"] for c in res["cases"])


def test_cross_process_determinism(tmp_path):
    p1 = tmp_path / "r1.json"
    p2 = tmp_path / "r2.json"
    for p in (p1, p2):
        r = subprocess.run(
            [sys.executable, "app/exam_review_benchmark.py",
             "--out", str(p)], cwd=str(ROOT), capture_output=True, text=True,
            timeout=900)
        assert r.returncode == 0, r.stderr[-2000:]
        assert "OK" in r.stdout
    assert filecmp.cmp(str(p1), str(p2), shallow=False)
