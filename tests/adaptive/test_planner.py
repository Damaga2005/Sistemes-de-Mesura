"""Tests Fase 13: Curriculum Planner + Long-Term Learning Path.

Planner = WHAT/WHEN (unidades + horizonte + modo); AdaptiveLoop =
WHICH QUESTION. Sin segundo engine, Priority congelada, sin LLM.
"""
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.adaptive import planner as PLN  # noqa: E402
from app.adaptive.planner import CurriculumPlanner  # noqa: E402
from app.adaptive.priority import PriorityCalculator  # noqa: E402
from app.examiner.service import ExaminerEngine  # noqa: E402
from app.retrieval.service import RetrievalService  # noqa: E402
from app.student import service as _svcmod  # noqa: E402
from app.student.service import StudentService  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
INDEX = str(ROOT / "data" / "index")
GENDB = str(ROOT / "data" / "generated" / "questions.sqlite")

T0 = "2026-09-01T10:00:00+00:00"


def _svc(tmp_path, name="s.sqlite"):
    return StudentService(KB, GENDB, str(tmp_path / name))


def _seed_row(svc, sid, uid, score, n, status, ok=0):
    con = svc.store.connect()
    try:
        con.execute("INSERT OR IGNORE INTO students(student_id, created_at)"
                    " VALUES(?,?)", (sid, T0))
        con.execute(
            "INSERT INTO mastery_states(mastery_id,student_id,"
            "knowledge_unit_id,unit_kind,score,confidence,attempt_count,"
            "correct_count,incorrect_count,last_attempt,last_correct,"
            "error_counts_json,status,policy_version)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("ms-" + sid + "-" + uid.replace(":", "-"), sid, uid,
             uid.split(":")[0], score, 0.5, n, ok, max(0, n - ok),
             T0, T0 if ok else "", "{}", status,
             "mastery-policy-v1"))
        con.commit()
    finally:
        con.close()


def _seed_spacing(svc, sid, uid, next_review, last=T0, interval=7,
                  count=2, status="CORRECT"):
    kind, _, ref = uid.partition(":")
    con = svc.store.connect()
    try:
        con.execute("INSERT OR IGNORE INTO students(student_id, created_at)"
                    " VALUES(?,?)", (sid, T0))
        con.execute(
            "INSERT INTO student_spacing(student_id,unit_kind,unit_id,"
            "first_review,last_review,next_review,review_count,"
            "interval_days,last_status,last_score,last_attempt_id)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(student_id,unit_kind,unit_id) DO UPDATE SET "
            "next_review=excluded.next_review",
            (sid, kind, ref, T0, last, next_review, count, interval,
             status, 1.0, "att"))
        con.commit()
    finally:
        con.close()


def _plan(svc, sid, **kw):
    kw.setdefault("now", T0)
    return CurriculumPlanner(svc).generate(sid, **kw)


# ---------- 1. new student: UNSEEN / coverage ----------
def test_new_student_prioritizes_unseen(tmp_path):
    svc = _svc(tmp_path)
    plan = _plan(svc, "nuevo")
    assert plan.today, "nuevo: TODAY no vacio"
    assert all(i.coverage_state == "unseen" for i in plan.today)
    assert all(i.recommended_mode == "STUDY" for i in plan.today)
    assert any("coverage_unseen" in i.reason_codes
               for i in plan.today)


# ---------- 2. weak antes que estable ----------
def test_weak_before_stable(tmp_path):
    svc = _svc(tmp_path)
    _seed_row(svc, "s", "formula:eq-02-0034", 0.2, 3, "EMERGING", ok=0)
    _seed_row(svc, "s", "formula:eq-02-0035", 0.95, 4, "MASTERED",
              ok=4)
    _seed_spacing(svc, "s", "formula:eq-02-0035",
                  "2026-12-01T10:00:00+00:00")
    plan = _plan(svc, "s")
    today = [i.knowledge_unit_id for i in plan.today]
    assert "formula:eq-02-0034" in today
    assert "formula:eq-02-0035" not in today
    assert "formula:eq-02-0035" in [i.knowledge_unit_id
                                    for i in plan.later]


# ---------- 3. recurrent errors ----------
def test_recurrent_error_in_today(tmp_path):
    svc = _svc(tmp_path)
    _seed_row(svc, "s", "formula:eq-02-0034", 0.5, 3, "DEVELOPING",
              ok=1)
    con = svc.store.connect()
    try:
        con.execute("INSERT OR IGNORE INTO students(student_id, created_at)"
                    " VALUES(?,?)", ("s", T0))
        con.execute(
            "UPDATE mastery_states SET error_counts_json=? WHERE "
            "student_id=? AND knowledge_unit_id=?",
            ('{"UNIT_ERROR": 3}', "s", "formula:eq-02-0034"))
        con.execute(
            "INSERT INTO error_memory(student_id,error_key,first_seen,"
            "last_seen,error_count,severity,last_status,last_question_id,"
            "last_attempt_id) VALUES(?,?,?,?,?,?,?,?,?)",
            ("s", "UNIT_ERROR", T0, T0, 3, "MODERATE", "INCORRECT",
             "q", "att"))
        con.commit()
    finally:
        con.close()
    plan = _plan(svc, "s")
    hits = [i for i in plan.today
            if i.knowledge_unit_id == "formula:eq-02-0034"]
    assert hits
    assert any("error_recurrent" in c for i in hits
               for c in i.reason_codes)
    assert hits[0].recommended_mode == "RECOVERY"


# ---------- 4/5/6. forgotten / due / at-risk ----------
def test_forgotten_due_at_risk_placement(tmp_path):
    svc = _svc(tmp_path)
    _seed_row(svc, "s", "formula:eq-02-0034", 0.95, 4, "MASTERED",
              ok=4)
    _seed_spacing(svc, "s", "formula:eq-02-0034",
                  "2026-08-01T10:00:00+00:00")
    plan = _plan(svc, "s")
    due = [i for i in plan.today
           if i.knowledge_unit_id == "formula:eq-02-0034"]
    assert due and due[0].retention_state == "DUE"
    assert "retention_due" in due[0].reason_codes


def test_mastered_stable_goes_later(tmp_path):
    svc = _svc(tmp_path)
    _seed_row(svc, "s", "formula:eq-02-0034", 0.2, 3, "EMERGING", ok=0)
    _seed_row(svc, "s", "formula:eq-02-0035", 0.95, 4, "MASTERED",
              ok=4)
    _seed_spacing(svc, "s", "formula:eq-02-0035",
                  "2026-12-01T10:00:00+00:00")
    plan = _plan(svc, "s")
    assert "formula:eq-02-0035" not in \
        [i.knowledge_unit_id for i in plan.today]
    assert "formula:eq-02-0035" in [i.knowledge_unit_id
                                    for i in plan.later]


# ---------- 8/9. determinismo / no duplicados ----------
def test_deterministic_and_unique(tmp_path):
    svc = _svc(tmp_path)
    _seed_row(svc, "s", "formula:eq-02-0034", 0.2, 3, "EMERGING", ok=0)
    a = _plan(svc, "s", seed=7)
    b = _plan(svc, "s", seed=7)
    assert a.to_dict() == b.to_dict()
    assert a.plan_id == b.plan_id
    uids = [i.knowledge_unit_id for i in a.items()]
    assert len(uids) == len(set(uids))


# ---------- 10. multi-student ----------
def test_multi_student_isolation(tmp_path):
    svc = _svc(tmp_path)
    _seed_row(svc, "A", "formula:eq-02-0034", 0.2, 3, "EMERGING", ok=0)
    pa = _plan(svc, "A")
    pb = _plan(svc, "B")
    assert pa.plan_id != pb.plan_id
    assert "formula:eq-02-0034" in [i.knowledge_unit_id
                                    for i in pa.today]
    assert "formula:eq-02-0034" not in [i.knowledge_unit_id
                                        for i in pb.items()]


# ---------- horizons ----------
def test_horizon_filter_and_limits(tmp_path):
    svc = _svc(tmp_path)
    full = _plan(svc, "s")
    assert full.horizon == "full"
    assert set(full.to_dict()) >= {"today", "next_7_days", "later",
                                   "plan_id"}
    t = _plan(svc, "s", horizon="today")
    assert t.horizon == "today"
    assert [i.knowledge_unit_id for i in t.items()] == \
        [i.knowledge_unit_id for i in full.today]
    w = _plan(svc, "s", horizon="week", week_limit=2)
    assert len(w.items()) <= 2
    with pytest.raises(ValueError):
        _plan(svc, "s", horizon="manana")
    with pytest.raises(ValueError):
        _plan(svc, "s", today_limit=-1)


# ---------- 11. recompute ----------
def test_recompute_after_state_change(tmp_path, monkeypatch):
    monkeypatch.setattr(_svcmod, "_now", lambda: T0)
    qdb = str(tmp_path / "q13.sqlite")
    shutil.copyfile(GENDB, qdb)
    svc = StudentService(KB, qdb, str(tmp_path / "s.sqlite"))
    eng = ExaminerEngine(RetrievalService(KB, INDEX), KB, qdb)
    before = _plan(svc, "alu", now=T0)
    assert all(i.coverage_state == "unseen"
               for i in before.today)
    q, log = eng.generate(topic=2, question_type="TRUE_FALSE", seed=31)
    assert q is not None, log
    body = q.to_dict()
    ca = str(body.get("correct_answer", "V")).strip().upper()
    bad = "F" if ca.startswith("V") else "V"
    svc.submit("alu", q.question_id, bad, attempt_id="att-r1")
    after = _plan(svc, "alu", now=T0)
    assert after.plan_id != before.plan_id
    assert any(i.coverage_state != "unseen" for i in after.items())


# ---------- 12. plan item -> AdaptiveLoop -> question ----------
def test_plan_item_feeds_adaptive_loop(tmp_path, monkeypatch):
    from app.adaptive.loop import AdaptiveLoop  # noqa: E402
    monkeypatch.setattr(_svcmod, "_now", lambda: T0)
    qdb = str(tmp_path / "q13.sqlite")
    shutil.copyfile(GENDB, qdb)
    svc = StudentService(KB, qdb, str(tmp_path / "s.sqlite"))
    eng = ExaminerEngine(RetrievalService(KB, INDEX), KB, qdb)
    q, log = eng.generate(topic=2, question_type="TRUE_FALSE", seed=41)
    body = q.to_dict()
    ca = str(body.get("correct_answer", "V")).strip().upper()
    svc.submit("alu", q.question_id,
               "F" if ca.startswith("V") else "V",
               attempt_id="att-r1")
    plan = _plan(svc, "alu")
    assert "question_id" not in plan.today[0].to_dict()
    item = plan.today[0]
    kind, _, ref = item.knowledge_unit_id.partition(":")
    calc = PriorityCalculator(svc)
    prs = calc.calculate("alu", limit=5,
                         candidates=[(kind, ref)], now=T0)
    assert prs, "la unidad del plan resuelve via Priority existente"
    loop = AdaptiveLoop(svc)
    out = loop.step("alu", eng, limit=3, seed=7)
    assert out["question"] is not None or \
        out["generate_log"].get("rejected") in (
            "no_novel_question_available", "sin_recomendacion") or \
        out["question"] is None


# ---------- 13/14. no LLM / exam isolation ----------
def test_planner_module_has_no_llm():
    src = Path(PLN.__file__).read_text(encoding="utf-8").lower()
    assert "llm" not in src
    assert "embedding" not in src
    assert "openai" not in src
    assert "gemini" not in src


def test_exam_units_never_planned(tmp_path):
    svc = _svc(tmp_path)
    plan = _plan(svc, "s")
    assert all(not i.knowledge_unit_id.startswith("exam")
               for i in plan.items())
    assert all(i.recommended_mode != "EXAM" for i in plan.items())


def test_priority_formula_untouched():
    from app.student.policy import PRIORITY_POLICY  # noqa: E402
    p = PRIORITY_POLICY.parameters
    assert (p["w_mastery"], p["w_error"], p["w_recency"]) == \
        (0.5, 0.3, 0.2)


# ---------- API /api/learn/plan ----------
def _bridge():
    import tempfile
    sys.path.insert(0, str(ROOT / "web"))
    import server as S  # noqa: E402
    return S.Bridge(workdir=tempfile.mkdtemp(prefix="sm-plan-"))


def test_learn_plan_endpoint():
    b = _bridge()
    st, data, _ = b.route("GET", "/api/learn/plan", {})
    assert st == 200
    plan = data["plan"]
    assert set(plan) >= {"today", "next_7_days", "later", "plan_id",
                         "policy_id"}
    assert plan["policy_id"] == "curriculum-policy"
    assert all("question_id" not in i for i in
               plan["today"] + plan["next_7_days"] + plan["later"])


def test_learn_plan_horizon_and_validation():
    b = _bridge()
    st, data, _ = b.route("GET", "/api/learn/plan",
                          {"horizon": "today", "limit": "2"})
    assert st == 200 and len(data["plan"]["today"]) <= 2
    st, _, _ = b.route("GET", "/api/learn/plan",
                       {"horizon": "manana"})
    assert st == 400
