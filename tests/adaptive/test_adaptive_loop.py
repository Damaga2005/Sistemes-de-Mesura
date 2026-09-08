"""Tests Fase 6 Bloque B: spacing + RecommendationBuilder + loop cerrado.

24 casos del benchmark (fuente unica:
data/evaluation/adaptive_loop_benchmark.jsonl) + invariantes de
buckets, categorias, adapter, step unico, aislamiento y LLM OFF.
Sin UI, sin Fase 7. Toda DB real solo se abre en lectura.
"""
import filecmp
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.adaptive import exam_adapter as AD  # noqa: E402
from app.adaptive.loop import AdaptiveLoop  # noqa: E402
from app.adaptive.models import LearningPathItem, Recommendation  # noqa: E402
from app.adaptive.path import LearningPathSelector  # noqa: E402
from app.adaptive.priority import PriorityCalculator  # noqa: E402
from app.adaptive.recommendations import (  # noqa: E402
    CATEGORIES,
    RecommendationBuilder,
    category_for,
)
from app.adaptive.spacing import (  # noqa: E402
    ALLOW,
    DEFER,
    NEVER_SEEN,
    bucket_for,
    evaluate,
)
from app.adaptive_loop_benchmark import load_cases, run_case  # noqa: E402
from app.student.policy import SPACING_POLICY  # noqa: E402
from app.student.service import StudentService  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
GENDB = str(ROOT / "data" / "generated" / "questions.sqlite")
EVALDB = str(ROOT / "data" / "evaluation" / "eval.sqlite")
CHUNKS = str(ROOT / "data" / "processed" / "chunks.jsonl")
MANIFEST = str(ROOT / "data" / "source_manifest.json")

CASES = {c["case_id"]: c for c in load_cases()}
P = SPACING_POLICY.parameters


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _svc(tmp_path, name="s.sqlite"):
    return StudentService(KB, GENDB, str(tmp_path / name))


def _seed_row(svc, sid, uid, score, n, status, last="", lcorrect="",
              conf=0.5, ok=1, bad=1, errors="{}"):
    con = svc.store.connect()
    try:
        con.execute("INSERT OR IGNORE INTO students(student_id, created_at)"
                    " VALUES(?,?)", (sid, "2026-01-01T00:00:00+00:00"))
        con.execute(
            "INSERT INTO mastery_states(mastery_id,student_id,"
            "knowledge_unit_id,unit_kind,score,confidence,attempt_count,"
            "correct_count,incorrect_count,last_attempt,last_correct,"
            "error_counts_json,status,policy_version)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("ms-" + sid + "-" + uid.replace(":", "-"), sid, uid,
             uid.split(":")[0], score, conf, n, ok, bad, last, lcorrect,
             errors, status, "mastery-policy-v1"))
        con.commit()
    finally:
        con.close()


# ---------- 24 casos del benchmark ----------
@pytest.mark.parametrize("case_id", sorted(CASES), ids=sorted(CASES))
def test_benchmark_case(tmp_path, case_id):
    ok, detail = run_case(CASES[case_id], tmp_path)
    assert ok, "%s: %r" % (case_id, detail.get("fails"))


# ---------- spacing: buckets ----------
def test_buckets_from_policy():
    assert bucket_for(0, None, P) == NEVER_SEEN
    assert bucket_for(2, 0, P) == "VERY_RECENT"
    assert bucket_for(2, 1, P) == "VERY_RECENT"
    assert bucket_for(2, 2, P) == "RECENT"
    assert bucket_for(2, 7, P) == "RECENT"
    assert bucket_for(2, 8, P) == "NORMAL"
    assert bucket_for(2, 30, P) == "NORMAL"
    assert bucket_for(2, 31, P) == "OLD"
    assert bucket_for(3, None, P) == "OLD"


def test_critical_definitions():
    base = {"knowledge_unit_id": "formula:f", "state": {}, "events": []}
    now = "2026-06-01T12:00:00+00:00"

    def ev(state, events=()):
        return evaluate({**base, "state": state, "events": list(events)},
                        now=now)

    recent = "2026-06-01T09:00:00+00:00"
    s = lambda **kw: {"score": 0.8, "confidence": 0.8, "attempt_count": 4,  # noqa: E731
                      "correct_count": 4, "incorrect_count": 0,
                      "last_attempt": recent, "last_correct": recent,
                      "status": "PROFICIENT", **kw}
    assert ev(s()) == ev(s()) and ev(s()).verdict == DEFER
    assert ev(s(status="AT_RISK")).critical is True
    assert ev(s(score=0.2, attempt_count=3, correct_count=0,
               incorrect_count=3)).critical is True
    assert ev(s(score=0.5)).critical is False  # 1 fallo sin raiz no critica
    roots = [{"evidence": {"signal": 0.0, "root_errors": ["FORMULA_ERROR"]}}]
    assert ev(s(score=0.6, incorrect_count=2), roots).critical is True
    assert ev(s(score=0.6, incorrect_count=1), roots).critical is False
    assert ev(s(score=0.75), roots).critical is False
    assert ev({"score": 0.0, "confidence": 0.0, "attempt_count": 0,
               "correct_count": 0, "incorrect_count": 0,
               "last_attempt": "", "last_correct": "",
               "status": "UNKNOWN"}).verdict == ALLOW


def test_fresh_failure_beats_recent_correct():
    sig = lambda v: {"evidence": {"signal": v, "root_errors": []}}  # noqa: E731
    got = evaluate(
        {"knowledge_unit_id": "formula:f",
         "state": {"score": 0.5, "confidence": 0.5, "attempt_count": 3,
                   "correct_count": 2, "incorrect_count": 1,
                   "last_attempt": "2026-06-01T09:00:00+00:00",
                   "last_correct": "2026-06-01T09:00:00+00:00",
                   "status": "DEVELOPING"},
         "events": [sig(1.0), sig(1.0), sig(0.0)]},
        now="2026-06-01T12:00:00+00:00")
    assert got.verdict == ALLOW  # fallo fresco > correcto reciente


# ---------- builder: categorias y orden ----------
def test_category_table():
    assert CATEGORIES == ("critical_weakness", "high_priority_practice",
                          "reinforce_errors", "normal_practice",
                          "maintenance", "exploration")
    hi = P["high_priority_min_score"]
    assert category_for(critical=True, explored=True, action="PRACTICE",
                        priority_score=0.0, high_min=hi) == 1
    assert category_for(critical=False, explored=True, action="PRACTICE",
                        priority_score=99.0, high_min=hi) == 6
    assert category_for(critical=False, explored=False, action="PRACTICE",
                        priority_score=hi, high_min=hi) == 2
    assert category_for(critical=False, explored=False, action="PRACTICE",
                        priority_score=hi - 0.001, high_min=hi) == 4
    assert category_for(critical=False, explored=False, action="REINFORCE",
                        priority_score=99.0, high_min=hi) == 3
    assert category_for(critical=False, explored=False, action="MAINTAIN",
                        priority_score=99.0, high_min=hi) == 5
    assert category_for(critical=False, explored=False, action="CHALLENGE",
                        priority_score=99.0, high_min=hi) == 4
    assert category_for(critical=False, explored=False, action="REVIEW",
                        priority_score=99.0, high_min=hi) == 4


def test_builder_empty_and_dedupe(tmp_path):
    svc = _svc(tmp_path)
    b = RecommendationBuilder(svc)
    assert b.build("nadie", [], [], limit=5) == []
    _seed_row(svc, "t", "formula:eq-02-0034", 0.3, 2, "EMERGING",
              last="2026-05-01T09:00:00+00:00")
    calc = PriorityCalculator(svc)
    sel = LearningPathSelector(svc)
    prios = calc.calculate("t", limit=100, now="2026-06-01T12:00:00+00:00")
    path = sel.select("t", limit=3, now="2026-06-01T12:00:00+00:00")
    dup = path + path  # duplicado adversarial
    recs = b.build("t", prios, dup, limit=3, now="2026-06-01T12:00:00+00:00")
    ids = [r.knowledge_unit_id for r in recs]
    assert len(ids) == len(set(ids))
    assert recs and all(r.policy_id == "spacing-policy"
                        and r.policy_version == "v1" for r in recs)
    assert all("priority-policy@v1" in r.source_policies.values()
               for r in recs)


def test_builder_only_closed_actions(tmp_path):
    svc = _svc(tmp_path)
    _seed_row(svc, "t", "formula:eq-02-0034", 0.3, 2, "EMERGING",
              last="2026-05-01T09:00:00+00:00")
    loop = AdaptiveLoop(svc)
    recs = loop.recommend("t", limit=3, seed=7,
                          now="2026-06-01T12:00:00+00:00")
    assert recs
    for r in recs:
        assert r.action in ("REVIEW", "PRACTICE", "REINFORCE", "CHALLENGE",
                            "MAINTAIN")
        assert r.difficulty in ("EASY", "MEDIUM", "HARD", "EXPERT")


# ---------- adapter ----------
def test_adapter_rejects_without_topic():
    rec = Recommendation(student_id="s", knowledge_unit_id="concept:x",
                         unit_kind="concept", priority_score=10.0,
                         action="PRACTICE", difficulty="EASY",
                         target_topic=None)
    with pytest.raises(ValueError):
        AD.to_blueprint(rec, seed=1)
    with pytest.raises(ValueError):
        AD.to_generate_kwargs(rec, seed=1, origin="FORGED")


def test_adapter_learning_objective_is_template():
    rec = Recommendation(student_id="s", knowledge_unit_id="formula:eq-1",
                         unit_kind="formula", priority_score=10.0,
                         action="REINFORCE", difficulty="EASY",
                         target_topic=2, target_formulas=("eq-1",))
    bp = AD.to_blueprint(rec, seed=3)
    assert bp.learning_objective == "REINFORCE:formula:eq-1"
    assert bp.seed == 3 and bp.topic == 2
    kw = AD.to_generate_kwargs(rec, seed=3)
    assert kw == {"topic": 2, "section": "", "question_type": "FORMULA",
                  "difficulty": "EASY", "formula_id": "eq-1", "seed": 3,
                  "origin": "GENERATED"}


# ---------- loop: una sola iteracion ----------
def test_step_is_single_iteration(tmp_path):
    svc = _svc(tmp_path)
    _seed_row(svc, "t", "formula:eq-02-0034", 0.2, 3, "EMERGING",
              last="2026-05-01T09:00:00+00:00")
    import inspect as _insp
    lines = [ln.strip() for ln in _insp.getsource(AdaptiveLoop.step).splitlines()]
    assert not any(ln.startswith(("for ", "while ")) for ln in lines)
    loop = AdaptiveLoop(svc)
    recs = loop.recommend("t", limit=1, seed=7,
                          now="2026-06-01T12:00:00+00:00")
    assert len(recs) == 1 and recs[0].knowledge_unit_id == "formula:eq-02-0034"


def test_step_empty_is_honest(tmp_path):
    svc = _svc(tmp_path)
    out = AdaptiveLoop(svc).step("nuevo", object(), limit=3, seed=7,
                                 now="2026-06-01T12:00:00+00:00")
    assert out["recommendations"] == [] and out["question"] is None
    assert out["generate_log"]["rejected"] == "sin_recomendacion"


# ---------- aislamiento y pureza ----------
def test_real_dbs_unchanged_by_loop(tmp_path):
    before = {p: _sha(p) for p in (KB, GENDB, EVALDB, CHUNKS, MANIFEST)}
    svc = _svc(tmp_path)
    _seed_row(svc, "t", "formula:eq-02-0034", 0.2, 3, "EMERGING",
              last="2026-05-01T09:00:00+00:00")
    loop = AdaptiveLoop(svc)
    recs = loop.recommend("t", limit=3, seed=7,
                          now="2026-06-01T12:00:00+00:00")
    assert recs
    AD.to_generate_kwargs(recs[0], seed=7)
    for p, h in before.items():
        assert _sha(p) == h, p


def test_no_llm_tokens_in_loop_files():
    import re
    tokens = ("LLMProvider", "Gemini", "gemini", "openai", "OpenAI",
              "anthropic", "llm_client", "EmbeddingProvider")
    for name in ("spacing.py", "recommendations.py", "exam_adapter.py",
                 "loop.py"):
        src = (ROOT / "app" / "adaptive" / name).read_text(encoding="utf-8")
        for t in tokens:
            assert not re.search(r"\b%s\b" % t, src), (name, t)


def test_cross_process_determinism(tmp_path):
    p1 = tmp_path / "r1.json"
    p2 = tmp_path / "r2.json"
    for p in (p1, p2):
        r = subprocess.run(
            [sys.executable, "app/adaptive_loop_benchmark.py",
             "--out", str(p)], cwd=str(ROOT), capture_output=True, text=True,
            timeout=600)
        assert r.returncode == 0, r.stderr[-2000:]
        assert "OK" in r.stdout
    assert filecmp.cmp(str(p1), str(p2), shallow=False)


def test_results_artifact_fresh():
    res = json.loads((ROOT / "data" / "evaluation"
                      / "adaptive_loop_results.json").read_text(
                          encoding="utf-8"))
    assert res["policies"] == ["priority-policy@v1", "difficulty-policy@v1",
                               "spacing-policy@v1"]
    assert len(res["cases"]) == 24
    assert all(not c["fails"] for c in res["cases"])


def test_priority_calculator_untouched_by_spacing():
    import inspect as _insp
    src = _insp.getsource(PriorityCalculator)
    assert "spacing" not in src.lower()
    item_src = _insp.getsource(LearningPathItem)
    assert "spacing" not in item_src.lower()


def test_seed_guard_rejects_real_gendb(tmp_path):
    from app.adaptive_loop_benchmark import _seed
    case = {"student": "g", "states": [], "events": [],
            "questions": [{"question_id": "qm-x", "topic": 2}]}
    with pytest.raises(RuntimeError):
        _seed(case, tmp_path, GENDB)


def test_gendb_has_no_benchmark_rows():
    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % GENDB, uri=True)
    try:
        n = con.execute("SELECT COUNT(*) FROM questions WHERE question_id"
                        " LIKE 'qm-%' OR question_id LIKE 'qb-%'").fetchone()[0]
    finally:
        con.close()
    assert n == 0


def test_numerical_without_formula_rejected_in_loop(tmp_path):
    """P1 F10-B4 extremo a extremo: concepto + REINFORCE + raiz
    UNIT_ERROR -> NUMERICAL sin formula -> rechazo contractual en
    generate() y en AdaptiveLoop.step (sin IndexError, sin LLM,
    sin pregunta persistida)."""
    import json as _json
    import sqlite3
    from app.examiner.service import ExaminerEngine
    from app.retrieval.service import RetrievalService
    svc = _svc(tmp_path)
    sid, uid = "num-nofid", "concept:magnitud"
    con = sqlite3.connect("file:%s?mode=ro" % GENDB, uri=True)
    try:
        seed_qid = con.execute("SELECT question_id FROM questions WHERE "
                               "topic=2 LIMIT 1").fetchone()[0]
    finally:
        con.close()
    con = svc.store.connect()
    try:
        con.execute("INSERT OR IGNORE INTO students(student_id, created_at)"
                    " VALUES(?,?)", (sid, "2026-01-01T00:00:00+00:00"))
        con.execute("INSERT INTO attempts(attempt_id,student_id,question_id,"
                    "question_version,exam_id,answer,created_at)"
                    " VALUES(?,?,?,?,?,?,?)",
                    ("att-num-1", sid, seed_qid, "4.0", "", "x",
                     "2026-06-01T09:00:00+00:00"))
        con.execute(
            "INSERT INTO mastery_states(mastery_id,student_id,"
            "knowledge_unit_id,unit_kind,score,confidence,attempt_count,"
            "correct_count,incorrect_count,last_attempt,last_correct,"
            "error_counts_json,status,policy_version)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("ms-num-concept", sid, uid, "concept", 0.55, 0.5, 4, 2, 2,
             "2026-06-01T09:00:00+00:00", "",
             _json.dumps({"UNIT_ERROR": 2}), "DEVELOPING",
             "mastery-policy-v1"))
        for i, ts in enumerate(("2026-06-01T09:00:00+00:00",
                                "2026-06-01T10:00:00+00:00")):
            con.execute(
                "INSERT INTO mastery_events(event_id,student_id,question_id,"
                "attempt_id,correction_id,knowledge_unit_id,unit_kind,"
                "old_score,new_score,old_confidence,new_confidence,reason,"
                "evidence_json,policy_version,created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("ev-num-%d" % i, sid, seed_qid, "att-num-1",
                 "corr-num-1", uid, "concept", 0.5, 0.55, 0.5, 0.5,
                 "seed",
                 _json.dumps({"signal": 0.0,
                              "root_errors": ["UNIT_ERROR"]}),
                 "mastery-policy-v1", ts))
        con.commit()
    finally:
        con.close()
    calc = PriorityCalculator(svc)
    prios = calc.calculate(sid, limit=10, now="2026-06-01T12:00:00+00:00")
    top = [p for p in prios if p.knowledge_unit_id == uid]
    assert top and top[0].recommended_action == "REINFORCE"
    assert any(r.startswith("raiz:") or r.startswith("raiz_repetida:")
               for r in top[0].reasons)
    sel = LearningPathSelector(svc)
    path = sel.select(sid, limit=3, now="2026-06-01T12:00:00+00:00")
    assert path and path[0].knowledge_unit_id == uid
    spec = sel.to_spec(path[0], seed=7)
    assert spec.type == "NUMERICAL" and spec.formula_ids == ()
    eng = ExaminerEngine(
        RetrievalService(KB, str(ROOT / "data" / "index")), KB,
        str(tmp_path / "q-loop.sqlite"))
    assert eng.store.count() == 0
    q, log = eng.generate(topic=spec.topic, section=spec.section,
                          question_type="NUMERICAL",
                          difficulty=spec.difficulty, seed=7)
    assert q is None
    assert log.get("rejected") == "NO_EVIDENCE_OR_GENERATION_FAILED"
    assert eng.store.count() == 0
    loop = AdaptiveLoop(svc)
    out = loop.step(sid, eng, limit=3, seed=7,
                    now="2026-06-01T12:00:00+00:00")
    assert out["question"] is None
    assert out["generate_log"].get("rejected") == \
        "NO_EVIDENCE_OR_GENERATION_FAILED"
    assert isinstance(out["recommendations"], list) and out["recommendations"]
    assert eng.store.count() == 0
