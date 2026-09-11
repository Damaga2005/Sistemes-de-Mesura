"""Tests Fase 10: Spaced Repetition (memoria persistente) + Coverage.

DBs temporales siempre. Tiempo controlado sin sleeps (monkeypatch de
app.student.service._now en cada test que lo necesite).
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
from app.student import service as _svcmod  # noqa: E402
from app.student.service import StudentService  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
INDEX = str(ROOT / "data" / "index")
GENDB = str(ROOT / "data" / "generated" / "questions.sqlite")

T0 = "2026-09-07T10:00:00+00:00"


def _wired(tmp_path):
    qdb = str(tmp_path / "q10.sqlite")
    shutil.copyfile(GENDB, qdb)
    svc = StudentService(KB, qdb, str(tmp_path / "s10.sqlite"))
    eng = ExaminerEngine(RetrievalService(KB, INDEX), KB, qdb)
    return svc, eng


def _freeze(monkeypatch, now):
    monkeypatch.setattr(_svcmod, "_now", lambda: now)


def _tf(svc, eng, sid, seed, att, wrong=True):
    q, log = eng.generate(topic=2, question_type="TRUE_FALSE", seed=seed)
    assert q is not None, log
    ca = str(getattr(q, "correct_answer", None) or
             q.to_dict().get("correct_answer", "V")).strip().upper()
    ans = "F" if ca.startswith("V") else "V"
    if not wrong:
        ans = "V" if ca.startswith("V") else "F"
    return svc.submit(sid, q.question_id, ans, attempt_id=att)


def _num(svc, eng, sid, seed, ans, att):
    q, log = eng.generate(topic=2, question_type="NUMERICAL",
                          formula_id="eq-02-0201", seed=seed)
    assert q is not None, log
    return svc.submit(sid, q.question_id, ans, attempt_id=att)


def _topic_uids(svc, sid):
    return svc.get_topic_mastery(sid, 2)


# ---------- Bloque A: memoria ----------
def test_new_unit_no_row(tmp_path):
    svc, _ = _wired(tmp_path)
    assert svc.get_spacing("alu-1", "topic", "T02") is None
    assert svc.get_due_units("alu-1") == []


def test_first_submit_incorrect(tmp_path, monkeypatch):
    _freeze(monkeypatch, T0)
    svc, eng = _wired(tmp_path)
    _tf(svc, eng, "alu-1", 11, "att-s1")
    sp = svc.get_spacing("alu-1", "topic", "T02")
    assert sp["review_count"] == 1
    assert sp["interval_days"] == 1
    assert sp["first_review"] == T0 and sp["last_review"] == T0
    assert sp["next_review"] == "2026-09-08T10:00:00+00:00"
    assert sp["last_status"] == "INCORRECT"
    assert sp["last_attempt_id"] == "att-s1"


def test_partial_interval(tmp_path, monkeypatch):
    _freeze(monkeypatch, T0)
    svc, eng = _wired(tmp_path)
    _num(svc, eng, "alu-1", 7, "1 m", "att-p1")
    sp = svc.get_spacing("alu-1", "topic", "T02")
    assert sp["interval_days"] == 3
    assert sp["next_review"] == "2026-09-10T10:00:00+00:00"
    assert sp["last_status"] == "PARTIALLY_CORRECT"


def test_correct_grows_capped(tmp_path, monkeypatch):
    svc, eng = _wired(tmp_path)
    days = ["2026-09-07T10:00:00+00:00", "2026-09-08T10:00:00+00:00",
            "2026-09-09T10:00:00+00:00", "2026-09-10T10:00:00+00:00"]
    intervals = []
    for i, day in enumerate(days):
        _freeze(monkeypatch, day)
        _tf(svc, eng, "alu-1", 11, "att-g%d" % i, wrong=False)
        intervals.append(
            svc.get_spacing("alu-1", "topic", "T02")["interval_days"])
    assert intervals == [7, 14, 28, 30]
    sp = svc.get_spacing("alu-1", "topic", "T02")
    assert sp["review_count"] == 4
    assert sp["next_review"] == "2026-10-10T10:00:00+00:00"


def test_due_detection(tmp_path, monkeypatch):
    _freeze(monkeypatch, T0)
    svc, eng = _wired(tmp_path)
    _tf(svc, eng, "alu-1", 11, "att-d1")
    assert svc.get_due_units("alu-1", now=T0) == []
    due = svc.get_due_units("alu-1", now="2026-09-08T10:00:01+00:00")
    ids = {d["knowledge_unit_id"] for d in due}
    assert "topic:T02" in ids
    assert due[0]["interval_days"] == 1
    with pytest.raises(ValueError):
        svc.get_due_units("alu-1", limit=0)


def test_determinism_two_students(tmp_path, monkeypatch):
    _freeze(monkeypatch, T0)
    got = []
    for stu in ("alu-1", "alu-2"):
        d = tmp_path / stu
        d.mkdir(exist_ok=True)
        svc, eng = _wired(d)
        _tf(svc, eng, stu, 11, "att-x")
        got.append(svc.get_spacing(stu, "topic", "T02"))
    a, b = got
    for k in ("interval_days", "next_review", "review_count",
              "last_status"):
        assert a[k] == b[k]


def test_replay_no_duplicate(tmp_path, monkeypatch):
    _freeze(monkeypatch, T0)
    svc, eng = _wired(tmp_path)
    _tf(svc, eng, "alu-1", 11, "att-r1")
    before = svc.get_spacing("alu-1", "topic", "T02")
    qid = svc.get_history(
        "alu-1", svc.get_recent_question_ids("alu-1")[0])["question_id"]
    out = svc.submit("alu-1", qid, "F", attempt_id="att-r1")
    assert out["replayed"] is True
    after = svc.get_spacing("alu-1", "topic", "T02")
    assert after == before


def test_multi_student_isolation(tmp_path, monkeypatch):
    _freeze(monkeypatch, T0)
    svc, eng = _wired(tmp_path)
    _tf(svc, eng, "alu-A", 11, "att-a1")
    assert svc.get_spacing("alu-B", "topic", "T02") is None
    assert svc.get_due_units("alu-B", now="2026-10-01T00:00:00+00:00") \
        == []


# ---------- Bloque C: coverage ----------
def test_coverage_fresh_student(tmp_path):
    svc, _ = _wired(tmp_path)
    cov = svc.get_coverage("nuevo")
    assert cov["total_units"] == 10 + 2896 + 365 + 271
    assert cov["seen_units"] == 0 and cov["unseen_units"] == 3542
    assert cov["coverage_ratio"] == 0.0
    assert set(cov["by_kind"]) == {"topic", "formula", "concept",
                                   "section"}
    assert cov["by_kind"]["formula"]["total"] == 2896


def test_coverage_seen_weak_mastered(tmp_path, monkeypatch):
    _freeze(monkeypatch, T0)
    svc, eng = _wired(tmp_path)
    _tf(svc, eng, "alu-1", 11, "att-c1")
    cov = svc.get_coverage("alu-1")
    assert cov["seen_units"] >= 2  # topic + seccion como minimo
    assert cov["by_kind"]["topic"]["seen"] >= 1
    assert cov["by_kind"]["topic"]["weak"] >= 1  # EMERGING tras fallo
    assert cov["by_kind"]["formula"]["seen"] == 0
    assert 0.0 < cov["coverage_ratio"] < 0.01
    for i in range(8):
        _tf(svc, eng, "alu-1", 11, "att-m%d" % i, wrong=False)
    cov2 = svc.get_coverage("alu-1")
    assert cov2["by_kind"]["topic"]["mastered"] == 1


def test_formula_coverage(tmp_path, monkeypatch):
    _freeze(monkeypatch, T0)
    svc, eng = _wired(tmp_path)
    q, log = eng.generate(topic=2, question_type="FORMULA",
                          formula_id="eq-02-0034", seed=14)
    assert q is not None, log
    svc.submit("alu-1", q.question_id, "falsa", attempt_id="att-f1")
    cov = svc.get_coverage("alu-1")
    assert cov["by_kind"]["formula"]["seen"] >= 1
    assert cov["by_kind"]["formula"]["unseen"] == \
        2896 - cov["by_kind"]["formula"]["seen"]


# ---------- Bloques B/D/G: adaptive ----------
def test_due_code_in_recommendation(tmp_path, monkeypatch):
    _freeze(monkeypatch, T0)
    svc, eng = _wired(tmp_path)
    _tf(svc, eng, "alu-1", 11, "att-u1")
    recs = AdaptiveLoop(svc).recommend(
        "alu-1", limit=5, seed=7, now="2026-09-09T10:00:00+00:00")
    assert recs
    t2 = [r for r in recs if r.knowledge_unit_id == "topic:T02"]
    assert t2 and "spacing_due" in t2[0].reason_codes


def test_unseen_code_fresh_student(tmp_path):
    # Estudiante nuevo: sin historial no hay recomendaciones (conducta
    # preexistente); la regla coverage_unseen se prueba directa.
    from app.adaptive.models import LearningPathItem
    from app.adaptive.recommendations import _unit_review_codes
    svc, _ = _wired(tmp_path)
    assert AdaptiveLoop(svc).recommend("nuevo", limit=5, seed=7) == []
    item = LearningPathItem(knowledge_unit_id="topic:T99",
                            unit_kind="topic", priority=1.0,
                            action="PRACTICE", difficulty="EASY")
    assert _unit_review_codes(svc, "nuevo", item, None) == \
        ["coverage_unseen"]
    assert _unit_review_codes(svc, "nuevo", item, T0) == \
        ["coverage_unseen"]


def test_weak_and_recurrent_preserved(tmp_path, monkeypatch):
    _freeze(monkeypatch, T0)
    svc, eng = _wired(tmp_path)
    _tf(svc, eng, "alu-1", 11, "att-k1")
    _tf(svc, eng, "alu-1", 22, "att-k2")
    recs = AdaptiveLoop(svc).recommend("alu-1", limit=5, seed=7)
    codes = [c for r in recs for c in r.reason_codes]
    assert any(c.startswith("error_recurrent:") for c in codes)
    assert any(c == "coverage_weak" for c in codes)


def test_novelty_still_works(tmp_path, monkeypatch):
    _freeze(monkeypatch, T0)
    svc, eng = _wired(tmp_path)
    q, _ = eng.generate(topic=2, question_type="TRUE_FALSE", seed=11)
    svc.submit("alu-1", q.question_id, "F", attempt_id="att-n1")
    out = AdaptiveLoop(svc).step("alu-1", eng, limit=3, seed=11)
    assert out["question"] is not None
    assert out["question"]["question_id"] != q.question_id


def test_exhausted_novelty_honest(tmp_path, monkeypatch):
    _freeze(monkeypatch, T0)
    svc, eng = _wired(tmp_path)
    out = AdaptiveLoop(svc).step("nuevo2", eng, limit=1, seed=11,
                                 max_attempts=1)
    assert set(out) == {"recommendations", "selected",
                        "generate_kwargs", "question", "generate_log"}


# ---------- E2E ----------
def test_e2e_spacing_coverage_loop(tmp_path, monkeypatch):
    _freeze(monkeypatch, T0)
    svc, eng = _wired(tmp_path)
    loop = AdaptiveLoop(svc)
    _tf(svc, eng, "alu-1", 11, "att-e0")
    r1 = loop.recommend("alu-1", limit=3, seed=7)
    assert r1
    out = loop.step("alu-1", eng, limit=3, seed=7)
    assert out["question"] is not None
    qid = out["question"]["question_id"]
    svc.submit("alu-1", qid, "F", attempt_id="att-e1")
    assert svc.get_spacing("alu-1", "topic", "T02") is not None
    cov = svc.get_coverage("alu-1")
    assert cov["seen_units"] >= 1
    r2 = loop.recommend("alu-1", limit=3, seed=7,
                        now="2026-09-09T10:00:00+00:00")
    assert r2


def test_isolation_mastered_vs_unseen(tmp_path, monkeypatch):
    _freeze(monkeypatch, T0)
    svc, eng = _wired(tmp_path)
    for i in range(4):
        _tf(svc, eng, "alu-A", 11, "att-iso%d" % i, wrong=False)
    assert svc.get_spacing("alu-A", "topic", "T02") is not None
    assert svc.get_spacing("alu-B", "topic", "T02") is None
    ca = svc.get_coverage("alu-A")
    cb = svc.get_coverage("alu-B")
    assert ca["by_kind"]["topic"]["mastered"] == 1
    assert cb["seen_units"] == 0
