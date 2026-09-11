"""Tests Fase 8: historial por estudiante + anti-repeticion en el loop.

DBs temporales siempre. Sin mocks de dominio.
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

import shutil


def _wired(tmp_path):
    """StudentService y ExaminerEngine sobre la MISMA qdb temporal."""
    qdb = str(tmp_path / "q8.sqlite")
    shutil.copyfile(GENDB, qdb)
    svc = StudentService(KB, qdb, str(tmp_path / "s8.sqlite"))
    eng = ExaminerEngine(RetrievalService(KB, INDEX), KB, qdb)
    return svc, eng


def _svc(tmp_path, name="s8.sqlite"):
    svc, _ = _wired(tmp_path)
    return svc


def _eng(tmp_path, name="q8.sqlite"):
    _, eng = _wired(tmp_path)
    return eng


def _tf(svc, eng, sid, seed, answer, attempt):
    q, log = eng.generate(topic=2, question_type="TRUE_FALSE", seed=seed)
    assert q is not None, log
    return q.question_id, svc.submit(sid, q.question_id, answer,
                                     attempt_id=attempt)


# ---------- Parte 15: historial ----------
def test_unseen_question(tmp_path):
    svc = _svc(tmp_path)
    assert svc.has_seen("alu-1", "q-x") is False
    assert svc.get_history("alu-1", "q-x") is None


def test_first_and_second_seen(tmp_path):
    svc = _svc(tmp_path)
    eng = _eng(tmp_path)
    qid, _ = _tf(svc, eng, "alu-1", 11, "V", "att-h1")
    h1 = svc.get_history("alu-1", qid)
    assert svc.has_seen("alu-1", qid) is True
    assert h1["attempt_count"] == 1
    assert h1["first_seen"] and h1["last_seen"]
    assert h1["last_attempt_id"] == "att-h1"
    assert h1["last_status"] in ("CORRECT", "PARTIALLY_CORRECT",
                                 "INCORRECT", "NO_ANSWER")
    out = svc.submit("alu-1", qid, "F", attempt_id="att-h2")
    assert out["replayed"] is False
    h2 = svc.get_history("alu-1", qid)
    assert h2["attempt_count"] == 2
    assert h2["first_seen"] == h1["first_seen"]
    assert h2["last_seen"] >= h1["last_seen"]
    assert h2["last_attempt_id"] == "att-h2"


def test_replay_does_not_duplicate_history(tmp_path):
    svc = _svc(tmp_path)
    eng = _eng(tmp_path)
    qid, _ = _tf(svc, eng, "alu-1", 11, "V", "att-r1")
    svc.submit("alu-1", qid, "V", attempt_id="att-r1")
    h = svc.get_history("alu-1", qid)
    assert h["attempt_count"] == 1


def test_history_is_per_student(tmp_path):
    svc = _svc(tmp_path)
    eng = _eng(tmp_path)
    qid, _ = _tf(svc, eng, "alu-A", 11, "V", "att-a1")
    assert svc.has_seen("alu-A", qid) is True
    assert svc.has_seen("alu-B", qid) is False
    assert svc.get_history("alu-B", qid) is None


def test_recent_question_ids(tmp_path):
    svc = _svc(tmp_path)
    eng = _eng(tmp_path)
    q1, _ = _tf(svc, eng, "alu-1", 11, "V", "att-n1")
    q2, _ = _tf(svc, eng, "alu-1", 22, "V", "att-n2")
    recent = svc.get_recent_question_ids("alu-1", limit=20)
    assert recent[0] == q2 and recent[1] == q1
    assert svc.get_recent_question_ids("alu-1", limit=1) == [q2]
    with pytest.raises(ValueError):
        svc.get_recent_question_ids("alu-1", limit=0)


# ---------- Parte 16: adaptive ----------
def test_step_avoids_seen_question(tmp_path):
    svc = _svc(tmp_path)
    eng = _eng(tmp_path)
    q1, _ = _tf(svc, eng, "alu-1", 11, "F", "att-s1")
    assert svc.has_seen("alu-1", q1)
    out = AdaptiveLoop(svc).step("alu-1", eng, limit=3, seed=11)
    q2 = out["question"]
    assert q2 is not None, out["generate_log"]
    assert q2["question_id"] != q1, "Q2 debe diferir de la ya vista Q1"


def test_step_exhaustion_is_honest(tmp_path):
    svc = _svc(tmp_path)
    eng = _eng(tmp_path)
    # Sin historial previo el loop funciona; el contrato de salida es
    # estable haya o no pregunta (nunca loop infinito, nunca excepción
    # por novedad).
    out = AdaptiveLoop(svc).step("alu-1", eng, limit=1, seed=11,
                                 max_attempts=1)
    assert set(out) == {"recommendations", "selected", "generate_kwargs",
                        "question", "generate_log"}
    if out["question"] is None:
        assert out["generate_log"].get("rejected")


def test_step_novelty_off_repeats(tmp_path):
    svc = _svc(tmp_path)
    eng = _eng(tmp_path)
    q1, _ = _tf(svc, eng, "alu-1", 11, "F", "att-o1")
    out = AdaptiveLoop(svc).step("alu-1", eng, limit=3, seed=11,
                                 novelty=False)
    assert out["question"] is not None


# ---------- Parte 17: E2E ----------
def test_step_all_seen_returns_honest_rejection(tmp_path):
    svc = _svc(tmp_path)
    eng = _eng(tmp_path)
    qid, _ = _tf(svc, eng, "alu-1", 11, "V", "att-z1")
    assert svc.has_seen("alu-1", qid)

    class FixedQ:
        question_id = qid

        def to_dict(self):
            return {"question_id": qid}

    class FixedEng:
        def generate(self, **kw):
            return FixedQ(), {"seed": kw.get("seed")}

    out = AdaptiveLoop(svc).step("alu-1", FixedEng(), limit=3, seed=11,
                                 max_attempts=3)
    assert out["question"] is None
    assert out["generate_log"].get("rejected") == \
        "no_novel_question_available"
    assert out["generate_log"].get("attempts") == 3


def test_e2e_q1_q2_q3(tmp_path):
    svc = _svc(tmp_path)
    eng = _eng(tmp_path)
    loop = AdaptiveLoop(svc)
    seen = []
    for i, (seed, ans, att) in enumerate(
            [(11, "F", "att-e1"), (0, "V", "att-e2"), (0, "V", "att-e3")]):
        if i == 0:
            q, log = eng.generate(topic=2, question_type="TRUE_FALSE",
                                  seed=seed)
            assert q is not None, log
            qid = q.question_id
        else:
            out = loop.step("alu-1", eng, limit=3, seed=seed)
            assert out["question"] is not None, out["generate_log"]
            qid = out["question"]["question_id"]
            assert qid not in seen, "repetición innecesaria en el loop"
        svc.submit("alu-1", qid, ans, attempt_id=att)
        assert svc.has_seen("alu-1", qid) is True
        seen.append(qid)
    assert len(set(seen)) == 3
    # mastery y provenance siguen funcionando
    assert svc.get_weak_units("alu-1")
    assert svc.get_mastery("alu-1", "topic:T02") is not None
