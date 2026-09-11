"""Tests Fase 9: Error Memory + uso en recomendación.

DBs temporales siempre. Errores reales de CorrectionService
(nunca inferidos). Sin mocks de dominio.
"""
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.adaptive.loop import AdaptiveLoop  # noqa: E402
from app.examiner.service import ExaminerEngine  # noqa: E402
from app.retrieval.service import RetrievalService  # noqa: E402
from app.student.service import StudentService  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
INDEX = str(ROOT / "data" / "index")
GENDB = str(ROOT / "data" / "generated" / "questions.sqlite")


def _wired(tmp_path):
    qdb = str(tmp_path / "q9.sqlite")
    shutil.copyfile(GENDB, qdb)
    svc = StudentService(KB, qdb, str(tmp_path / "s9.sqlite"))
    eng = ExaminerEngine(RetrievalService(KB, INDEX), KB, qdb)
    return svc, eng


def _tf_wrong(svc, eng, sid, seed, att):
    q, log = eng.generate(topic=2, question_type="TRUE_FALSE", seed=seed)
    assert q is not None, log
    ca = str(getattr(q, "correct_answer", None) or
             q.to_dict().get("correct_answer", "V")).strip().upper()
    wrong = "F" if ca.startswith("V") else "V"
    out = svc.submit(sid, q.question_id, wrong, attempt_id=att)
    assert out["correction"]["status"] == "INCORRECT", \
        out["correction"]["status"]
    return q.question_id, out


def _num_wrong(svc, eng, sid, seed, att):
    q, log = eng.generate(topic=2, question_type="NUMERICAL",
                          formula_id="eq-02-0201", seed=seed)
    assert q is not None, log
    return svc.submit(sid, q.question_id, "9999 kg", attempt_id=att)


# ---------- Parte 27: memoria ----------
def test_fresh_student_empty(tmp_path):
    svc, _ = _wired(tmp_path)
    assert svc.get_error_memory("nuevo") == []
    assert svc.get_recurrent_errors("nuevo") == []
    assert svc.get_error_history("nuevo", "WRONG_FINAL_RESULT") is None


def test_new_error_recorded(tmp_path):
    svc, eng = _wired(tmp_path)
    _tf_wrong(svc, eng, "alu-1", 11, "att-e1")
    mem = svc.get_error_memory("alu-1")
    assert len(mem) == 1
    m = mem[0]
    assert m["error_key"] == "WRONG_FINAL_RESULT"
    assert m["error_count"] == 1
    assert m["severity"] == "MODERATE"
    assert m["first_seen"] and m["last_seen"]
    assert m["last_status"] == "INCORRECT"
    assert m["last_question_id"].startswith("q-")
    assert m["last_attempt_id"] == "att-e1"


def test_second_error_increments(tmp_path):
    svc, eng = _wired(tmp_path)
    _tf_wrong(svc, eng, "alu-1", 11, "att-e1")
    h1 = svc.get_error_history("alu-1", "WRONG_FINAL_RESULT")
    _tf_wrong(svc, eng, "alu-1", 22, "att-e2")
    h2 = svc.get_error_history("alu-1", "WRONG_FINAL_RESULT")
    assert h2["error_count"] == 2
    assert h2["first_seen"] == h1["first_seen"]
    assert h2["last_seen"] >= h1["last_seen"]
    assert h2["last_attempt_id"] == "att-e2"


def test_multiple_errors_independent(tmp_path):
    svc, eng = _wired(tmp_path)
    _num_wrong(svc, eng, "alu-1", 7, "att-m1")
    keys = {m["error_key"]: m["error_count"]
            for m in svc.get_error_memory("alu-1")}
    assert keys.get("ARITHMETIC_ERROR", 0) >= 1
    assert keys.get("WRONG_FINAL_RESULT", 0) >= 1


def test_recurrent_rule(tmp_path):
    svc, eng = _wired(tmp_path)
    _tf_wrong(svc, eng, "alu-1", 11, "att-r1")
    assert svc.get_recurrent_errors("alu-1") == []
    _tf_wrong(svc, eng, "alu-1", 22, "att-r2")
    rec = svc.get_recurrent_errors("alu-1")
    assert [r["error_key"] for r in rec] == ["WRONG_FINAL_RESULT"]
    with pytest.raises(ValueError):
        svc.get_recurrent_errors("alu-1", min_count=0)


def test_replay_no_duplicate(tmp_path):
    svc, eng = _wired(tmp_path)
    _tf_wrong(svc, eng, "alu-1", 11, "att-d1")
    svc.submit("alu-1", svc.get_error_history(
        "alu-1", "WRONG_FINAL_RESULT")["last_question_id"],
        "F", attempt_id="att-d1")
    h = svc.get_error_history("alu-1", "WRONG_FINAL_RESULT")
    assert h["error_count"] == 1


def test_per_student_isolation(tmp_path):
    svc, eng = _wired(tmp_path)
    _tf_wrong(svc, eng, "alu-A", 11, "att-a1")
    assert svc.get_error_memory("alu-B") == []
    assert svc.get_error_history("alu-B", "WRONG_FINAL_RESULT") is None


def test_ordering_deterministic(tmp_path):
    svc, eng = _wired(tmp_path)
    for i in range(4):
        _num_wrong(svc, eng, "alu-1", 7, "att-o%d" % i)
    rec = svc.get_recurrent_errors("alu-1")
    keys = [r["error_key"] for r in rec]
    assert keys[0] == "ARITHMETIC_ERROR"
    again = [r["error_key"] for r in svc.get_recurrent_errors("alu-1")]
    assert again == keys


# ---------- Parte 29: adaptive ----------
def test_no_history_no_code(tmp_path):
    svc, eng = _wired(tmp_path)
    recs = AdaptiveLoop(svc).recommend("nuevo", limit=3, seed=7)
    for r in recs:
        assert not [c for c in r.reason_codes
                    if c.startswith("error_recurrent:")]


def test_recurrent_code_appears(tmp_path):
    svc, eng = _wired(tmp_path)
    _tf_wrong(svc, eng, "alu-1", 11, "att-c1")
    _tf_wrong(svc, eng, "alu-1", 22, "att-c2")
    recs = AdaptiveLoop(svc).recommend("alu-1", limit=3, seed=7)
    assert recs
    codes = [c for r in recs for c in r.reason_codes
             if c.startswith("error_recurrent:")]
    assert "error_recurrent:WRONG_FINAL_RESULT:x2" in codes


def test_old_error_stays_recorded(tmp_path):
    svc, eng = _wired(tmp_path)
    _tf_wrong(svc, eng, "alu-1", 11, "att-h1")
    _num_wrong(svc, eng, "alu-1", 7, "att-h2")
    h = svc.get_error_history("alu-1", "WRONG_FINAL_RESULT")
    assert h["error_count"] >= 1 and h["first_seen"]


def test_two_students_differ(tmp_path):
    svc, eng = _wired(tmp_path)
    for i in range(2):
        _tf_wrong(svc, eng, "alu-A", 11 + i, "att-ea%d" % i)
    for i in range(4):
        _num_wrong(svc, eng, "alu-B", 7, "att-eb%d" % i)
    ca = {c for r in AdaptiveLoop(svc).recommend("alu-A", limit=5,
                                                 seed=7)
          for c in r.reason_codes if c.startswith("error_recurrent:")}
    cb = {c for r in AdaptiveLoop(svc).recommend("alu-B", limit=5,
                                                 seed=7)
          for c in r.reason_codes if c.startswith("error_recurrent:")}
    assert ca == {"error_recurrent:WRONG_FINAL_RESULT:x2"}
    assert "error_recurrent:ARITHMETIC_ERROR:x4" in cb
    assert ca != cb


# ---------- Parte 30: E2E ----------
def test_e2e_error_to_recommendation(tmp_path):
    svc, eng = _wired(tmp_path)
    loop = AdaptiveLoop(svc)
    r1 = loop.recommend("alu-1", limit=3, seed=7)
    assert not [c for r in r1 for c in r.reason_codes
                if c.startswith("error_recurrent:")]
    _tf_wrong(svc, eng, "alu-1", 11, "att-w1")
    out = loop.step("alu-1", eng, limit=3, seed=7)
    assert out["question"] is not None
    qid = out["question"]["question_id"]
    svc.submit("alu-1", qid, "F", attempt_id="att-w2")
    out = loop.step("alu-1", eng, limit=3, seed=7)
    assert out["question"] is not None
    svc.submit("alu-1", out["question"]["question_id"], "F",
               attempt_id="att-w3")
    # consistencia memoria -> codigos, sea cual sea el patron real
    rec = svc.get_recurrent_errors("alu-1")
    r2 = loop.recommend("alu-1", limit=3, seed=7)
    codes = [c for r in r2 for c in r.reason_codes
             if c.startswith("error_recurrent:")]
    # cada recomendacion lleva el top recurrente (mismo para todas)
    assert codes, "el patron debe llegar a la recomendacion"
    assert set(codes) == {
        "error_recurrent:%s:x%d" % (rec[0]["error_key"],
                                    rec[0]["error_count"])}
    mem = svc.get_error_memory("alu-1")
    assert sum(m["error_count"] for m in mem) >= 2
    assert svc.get_history("alu-1", qid) is not None
