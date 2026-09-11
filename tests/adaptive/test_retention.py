"""Tests Fase 12: Retention / Forgetting + Recovery Intelligence.

Una sola funcion canonica (app.adaptive.retention.calculate_retention),
sin tablas nuevas, sin ML, sin LLM. Reloj inyectable via `now`.
DBs temporales para E2E; FakeSvc para unidad pura determinista.
"""
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.adaptive import retention as RET  # noqa: E402
from app.adaptive.loop import AdaptiveLoop  # noqa: E402
from app.adaptive.modes import apply_mode_filter  # noqa: E402
from app.examiner.service import ExaminerEngine  # noqa: E402
from app.retrieval.service import RetrievalService  # noqa: E402
from app.student import service as _svcmod  # noqa: E402
from app.student.service import StudentService  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
INDEX = str(ROOT / "data" / "index")
GENDB = str(ROOT / "data" / "generated" / "questions.sqlite")

T0 = "2026-09-01T10:00:00+00:00"
UID = "formula:eq-02-0201"


class FakeSvc:
    def __init__(self, state=None, events=(), spacing=None):
        self._state = state
        self._events = list(events)
        self._spacing = spacing

    def get_unit_history(self, sid, uid):
        return {"knowledge_unit_id": uid, "state": self._state,
                "events": list(self._events)}

    def get_spacing(self, sid, kind, ref):
        return dict(self._spacing) if self._spacing else None

    def get_recurrent_errors(self, sid):
        return []

    def get_mastery(self, sid, uid):
        if self._state is None:
            return None
        d = dict(self._state)
        d["knowledge_unit_id"] = uid
        d.setdefault("error_counts", {})
        return d


def _st(score, n, status, ok=0, last=T0, lcorrect=T0):
    return {"unit_kind": "formula", "score": score, "confidence": 0.6,
            "attempt_count": n, "correct_count": ok,
            "incorrect_count": max(0, n - ok), "last_attempt": last,
            "last_correct": lcorrect, "error_counts": {},
            "status": status, "policy_version": "mastery-policy-v1"}


def _ev(signals):
    return [{"event_id": "e%d" % i, "question_id": "q",
             "attempt_id": "a%d" % i, "correction_id": "c",
             "evidence": {"signal": s, "root_errors": []}}
            for i, s in enumerate(signals)]


def _sp(next_review, last_review=T0, interval=7, count=1,
        status="CORRECT", score=1.0):
    return {"student_id": "s", "unit_kind": "formula",
            "unit_id": "eq-02-0201", "first_review": T0,
            "last_review": last_review, "next_review": next_review,
            "review_count": count, "interval_days": interval,
            "last_status": status, "last_score": score,
            "last_attempt_id": "att"}


# ---------- Retention basica ----------
def test_unseen_no_state():
    r = RET.calculate_retention(FakeSvc(), "s", UID, now=T0)
    assert r.state == "UNSEEN"
    assert r.retention_score == 0.0


def test_learning_weak_no_due():
    svc = FakeSvc(_st(0.2, 2, "EMERGING", ok=0), _ev([0.0, 0.0]),
                  _sp("2026-09-10T10:00:00+00:00"))
    r = RET.calculate_retention(svc, "s", UID, now=T0)
    assert r.state == "LEARNING"


def test_mastered_fresh():
    svc = FakeSvc(_st(0.95, 4, "MASTERED", ok=4), _ev([1.0] * 4),
                  _sp("2026-09-10T10:00:00+00:00", interval=7))
    r = RET.calculate_retention(svc, "s", UID, now=T0)
    assert r.state == "MASTERED"
    assert r.due is False


def test_due_detection():
    svc = FakeSvc(_st(0.95, 4, "MASTERED", ok=4), _ev([1.0] * 4),
                  _sp("2026-09-01T10:00:00+00:00", interval=7))
    r = RET.calculate_retention(
        svc, "s", UID, now="2026-09-05T10:00:00+00:00")
    assert r.state == "DUE"
    assert r.due is True and r.overdue_days == 4
    assert RET.retention_code("DUE") == "retention_due"


def test_exact_boundary_is_due():
    svc = FakeSvc(_st(0.9, 4, "MASTERED", ok=4), _ev([1.0] * 4),
                  _sp("2026-09-05T10:00:00+00:00", interval=7))
    r = RET.calculate_retention(
        svc, "s", UID, now="2026-09-05T10:00:00+00:00")
    assert r.state == "DUE"


def test_at_risk_before_review():
    svc = FakeSvc(_st(0.95, 4, "MASTERED", ok=4), _ev([1.0] * 4),
                  _sp("2026-09-08T10:00:00+00:00", interval=7))
    r = RET.calculate_retention(
        svc, "s", UID, now="2026-09-05T10:00:00+00:00")
    assert r.state == "AT_RISK"
    assert RET.retention_code("AT_RISK") == "retention_at_risk"


def test_forgotten_needs_all_three():
    svc = FakeSvc(_st(0.6, 5, "DEVELOPING", ok=4),
                  _ev([1.0, 1.0, 1.0, 1.0, 0.0]),
                  _sp("2026-09-01T10:00:00+00:00", interval=7,
                      status="INCORRECT", score=0.0))
    r = RET.calculate_retention(
        svc, "s", UID, now="2026-09-05T10:00:00+00:00")
    assert r.state == "FORGOTTEN"
    assert RET.retention_code("FORGOTTEN") == "retention_forgotten"


def test_deterministic():
    svc = FakeSvc(_st(0.95, 4, "MASTERED", ok=4), _ev([1.0] * 4),
                  _sp("2026-09-08T10:00:00+00:00", interval=7))
    a = RET.calculate_retention(svc, "s", UID,
                                now="2026-09-05T10:00:00+00:00")
    b = RET.calculate_retention(svc, "s", UID,
                                now="2026-09-05T10:00:00+00:00")
    assert a == b


# ---------- No false forgetting ----------
def test_never_seen_is_not_forgotten():
    r = RET.calculate_retention(FakeSvc(), "s", UID,
                                now="2027-01-01T00:00:00+00:00")
    assert r.state == "UNSEEN"


def test_mastered_gap_without_negative_is_not_forgotten():
    svc = FakeSvc(_st(0.95, 4, "MASTERED", ok=4), _ev([1.0] * 4),
                  _sp("2026-09-01T10:00:00+00:00", interval=7))
    r = RET.calculate_retention(
        svc, "s", UID, now="2026-12-01T10:00:00+00:00")
    assert r.state in ("DUE", "AT_RISK")
    assert r.state != "FORGOTTEN"


def test_first_try_correct_is_learning_or_mastered_not_forgotten():
    svc = FakeSvc(_st(1.0, 1, "EMERGING", ok=1), _ev([1.0]), None)
    r = RET.calculate_retention(svc, "s", UID, now=T0)
    assert r.state in ("LEARNING", "MASTERED")
    assert r.state != "FORGOTTEN"


def test_first_try_incorrect_is_learning():
    svc = FakeSvc(_st(0.0, 1, "EMERGING", ok=0), _ev([0.0]), None)
    r = RET.calculate_retention(svc, "s", UID, now=T0)
    assert r.state == "LEARNING"


def test_mastery_at_risk_status_maps_to_learning():
    svc = FakeSvc(_st(0.1, 3, "AT_RISK", ok=0),
                  _ev([0.0, 0.0, 0.0]), None)
    r = RET.calculate_retention(svc, "s", UID, now=T0)
    assert r.state == "LEARNING"


def _seed_emerging(svc, sid):
    con = svc.store.connect()
    try:
        con.execute("INSERT OR IGNORE INTO students(student_id, created_at)"
                    " VALUES(?,?)", (sid, T0))
        for uid, score in (("formula:eq-02-0034", 0.2),
                           ("topic:T02", 0.1)):
            con.execute(
                "INSERT INTO mastery_states(mastery_id,student_id,"
                "knowledge_unit_id,unit_kind,score,confidence,attempt_count,"
                "correct_count,incorrect_count,last_attempt,last_correct,"
                "error_counts_json,status,policy_version)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("ms-%s-%s" % (sid, uid.replace(":", "-")), sid, uid,
                 uid.split(":")[0], score, 0.5, 3, 0, 3, T0, "",
                 "{}", "EMERGING", "mastery-policy-v1"))
        con.commit()
    finally:
        con.close()


# ---------- Recovery / modes ----------
def test_study_distinguishes_unseen_from_forgotten(tmp_path):
    svc = StudentService(KB, GENDB, str(tmp_path / "s.sqlite"))
    _seed_emerging(svc, "s-study12")
    loop = AdaptiveLoop(svc)
    base = loop.recommend("s-study12", limit=5, seed=7, mode="PRACTICE")
    assert base
    got = loop.recommend("s-study12", limit=5, seed=7, mode="STUDY",
                         now=T0)
    assert got
    assert all("mode_study" in r.reason_codes for r in got)


def test_practice_intact_with_retention_codes(tmp_path):
    svc = StudentService(KB, GENDB, str(tmp_path / "s.sqlite"))
    loop = AdaptiveLoop(svc)
    a = loop.recommend("s-p12", limit=3, seed=7, mode="PRACTICE")
    b = loop.recommend("s-p12", limit=3, seed=7)
    assert [r.knowledge_unit_id for r in a] == \
        [r.knowledge_unit_id for r in b]


def test_exam_still_rejected(tmp_path):
    svc = StudentService(KB, GENDB, str(tmp_path / "s.sqlite"))
    with pytest.raises(ValueError, match="closed blueprint"):
        AdaptiveLoop(svc).recommend("s", mode="EXAM")


def test_recovery_rank_order():
    assert RET.recovery_rank("FORGOTTEN", True) < \
        RET.recovery_rank("FORGOTTEN", False) < \
        RET.recovery_rank("AT_RISK", False)
    assert RET.study_rank("UNSEEN") < RET.study_rank("FORGOTTEN") < \
        RET.study_rank("AT_RISK") < RET.study_rank("DUE")


def test_mode_filter_accepts_now_kwarg(tmp_path):
    svc = StudentService(KB, GENDB, str(tmp_path / "s.sqlite"))
    _seed_emerging(svc, "s")
    items = AdaptiveLoop(svc).recommend("s", limit=3, seed=7)
    assert items
    out = apply_mode_filter(items, svc, "s", "STUDY", now=T0)
    assert out


# ---------- E2E con DB real ----------
def _wired(tmp_path):
    qdb = str(tmp_path / "q12.sqlite")
    shutil.copyfile(GENDB, qdb)
    svc = StudentService(KB, qdb, str(tmp_path / "s12.sqlite"))
    eng = ExaminerEngine(RetrievalService(KB, INDEX), KB, qdb)
    return svc, eng


def _freeze(monkeypatch, now):
    monkeypatch.setattr(_svcmod, "_now", lambda: now)


def _correct_num(svc, eng, sid, seed, att):
    q, log = eng.generate(topic=2, question_type="NUMERICAL",
                          formula_id="eq-02-0201", seed=seed)
    assert q is not None, log
    body = q.to_dict()
    return svc.submit(sid, q.question_id, str(body["correct_answer"]),
                      attempt_id=att)


def _wrong_num(svc, eng, sid, seed, att):
    q, log = eng.generate(topic=2, question_type="NUMERICAL",
                          formula_id="eq-02-0201", seed=seed)
    assert q is not None, log
    body = q.to_dict()
    try:
        wrong = str(float(str(body["correct_answer"]).replace(",", ".")) + 9999.0)
    except (TypeError, ValueError):
        wrong = "respuesta_falsa_seguro"
    out = svc.submit(sid, q.question_id, wrong, attempt_id=att)
    assert out["correction"]["status"] == "INCORRECT", out["correction"]
    return out


def _tf_ans(svc, eng, sid, seed, att, wrong):
    q, log = eng.generate(topic=2, question_type="TRUE_FALSE", seed=seed)
    assert q is not None, log
    body = q.to_dict()
    ca = str(body.get("correct_answer", "V")).strip().upper()
    good = "V" if ca.startswith("V") else "F"
    bad = "F" if ca.startswith("V") else "V"
    out = svc.submit(sid, q.question_id, bad if wrong else good,
                     attempt_id=att)
    return out


def test_e2e_forget_then_recover(tmp_path, monkeypatch):
    _freeze(monkeypatch, T0)
    svc, eng = _wired(tmp_path)
    sid = "alu-forget"
    uid = "topic:T02"
    for i in range(4):
        out = _tf_ans(svc, eng, sid, 100 + i, "att-m%d" % i, wrong=False)
        assert out["correction"]["status"] == "CORRECT", \
            out["correction"]
    m = svc.get_mastery(sid, uid)
    assert m is not None and m["correct_count"] >= 3, m
    sp = svc.get_spacing(sid, "topic", "T02")
    assert sp is not None
    # Vencida + fallo -> FORGOTTEN
    future = "2026-12-01T10:00:00+00:00"
    _freeze(monkeypatch, future)
    out = _tf_ans(svc, eng, sid, 500, "att-fail", wrong=True)
    assert out["correction"]["status"] == "INCORRECT", \
        out["correction"]
    r = RET.calculate_retention(svc, sid, uid, now=future)
    assert r.state == "FORGOTTEN", r.to_dict()
    # Recovery la selecciona
    loop = AdaptiveLoop(svc)
    recs = loop.recommend(sid, limit=5, seed=7, mode="RECOVERY",
                          now=future)
    assert recs
    # Exito de recovery: acierto -> ya no FORGOTTEN
    _tf_ans(svc, eng, sid, 600, "att-rec", wrong=False)
    r2 = RET.calculate_retention(svc, sid, uid, now=future)
    assert r2.state != "FORGOTTEN", r2.to_dict()
    assert r2.retention_score >= r.retention_score


def test_replay_idempotent(tmp_path, monkeypatch):
    _freeze(monkeypatch, T0)
    svc, eng = _wired(tmp_path)
    q, _ = eng.generate(topic=2, question_type="NUMERICAL",
                        formula_id="eq-02-0201", seed=21)
    body = q.to_dict()
    a = svc.submit("alu-rep", q.question_id,
                   str(body["correct_answer"]), attempt_id="att-rep")
    b = svc.submit("alu-rep", q.question_id,
                   str(body["correct_answer"]), attempt_id="att-rep")
    assert b["replayed"] is True
    r1 = RET.calculate_retention(svc, "alu-rep", UID, now=T0)
    r2 = RET.calculate_retention(svc, "alu-rep", UID, now=T0)
    assert r1 == r2
    assert a["replayed"] is False


def test_multi_student_isolation(tmp_path):
    svc = StudentService(KB, GENDB, str(tmp_path / "s.sqlite"))
    con = svc.store.connect()
    try:
        for sid, score, n, status, ok in (
                ("A", 0.95, 4, "MASTERED", 4), ("B", 0.0, 0, "UNKNOWN", 0)):
            con.execute("INSERT OR IGNORE INTO students(student_id,"
                        "created_at) VALUES(?,?)", (sid, T0))
            if n:
                con.execute(
                    "INSERT INTO mastery_states(mastery_id,student_id,"
                    "knowledge_unit_id,unit_kind,score,confidence,"
                    "attempt_count,correct_count,incorrect_count,"
                    "last_attempt,last_correct,error_counts_json,status,"
                    "policy_version) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    ("ms-%s" % sid, sid, UID, "formula", score, 0.8, n,
                     ok, n - ok, T0, T0, "{}", status,
                     "mastery-policy-v1"))
        con.commit()
    finally:
        con.close()
    ra = RET.calculate_retention(svc, "A", UID, now=T0)
    rb = RET.calculate_retention(svc, "B", UID, now=T0)
    assert rb.state == "UNSEEN"
    assert ra.state in ("MASTERED", "AT_RISK", "LEARNING")
    assert ra.state != "UNSEEN"


def test_no_spacing_params_changed():
    from app.student.policy import REVIEW_POLICY
    p = REVIEW_POLICY.parameters
    assert p["initial_days"] == {"correct": 7, "partial": 3,
                                 "incorrect": 1}
    assert p["growth_factor"] == 2.0
    assert p["max_interval_days"] == 30


def test_retention_module_has_no_llm():
    src = Path(RET.__file__).read_text(encoding="utf-8").lower()
    assert "llm" not in src
    assert "embedding" not in src
    assert "openai" not in src
    assert "anthropic" not in src
