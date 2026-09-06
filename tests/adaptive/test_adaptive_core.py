"""Tests Fase 6 Bloque A: Adaptive Core (priority + difficulty + path).

20 casos del benchmark (una sola fuente de verdad:
data/evaluation/adaptive_core_benchmark.jsonl) + invariantes de
determinismo, conservadurismo de dificultad, trazabilidad y aislamiento.
Sin LLM, sin UI, sin Fase 7. Toda DB real solo se abre en lectura.
"""
import hashlib
import inspect
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.adaptive.difficulty import DifficultySelector  # noqa: E402
from app.adaptive.models import LearningPathItem  # noqa: E402
from app.adaptive.path import LearningPathSelector  # noqa: E402
from app.adaptive.priority import PriorityCalculator  # noqa: E402
from app.adaptive_benchmark import load_cases, run_case  # noqa: E402
from app.student.policy import DIFFICULTY_POLICY, PRIORITY_POLICY  # noqa: E402
from app.student.service import StudentService  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
GENDB = str(ROOT / "data" / "generated" / "questions.sqlite")
EVALDB = str(ROOT / "data" / "evaluation" / "eval.sqlite")

CASES = {c["case_id"]: c for c in load_cases()}


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _seed_minimal(svc, sid="t"):
    con = svc.store.connect()
    try:
        con.execute("INSERT INTO students(student_id, created_at) VALUES(?,?)",
                    (sid, "2026-01-01T00:00:00+00:00"))
        for uid, kind, score, n, status in [
                ("formula:eq-02-0034", "formula", 0.3, 2, "EMERGING"),
                ("concept:prova", "concept", 0.5, 2, "DEVELOPING"),
                ("topic:T02", "topic", 0.4, 2, "DEVELOPING")]:
            con.execute(
                "INSERT INTO mastery_states(mastery_id,student_id,"
                "knowledge_unit_id,unit_kind,score,confidence,attempt_count,"
                "correct_count,incorrect_count,error_counts_json,status,"
                "policy_version) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                ("ms-" + uid.replace(":", "-"), sid, uid, kind, score, 0.4,
                 n, 1, 1, "{}", status, "mastery-policy-v1"))
        con.commit()
    finally:
        con.close()


# ---------- 20 casos del benchmark ----------
@pytest.mark.parametrize("case_id", sorted(CASES), ids=sorted(CASES))
def test_benchmark_case(tmp_path, case_id):
    ok, detail = run_case(CASES[case_id], tmp_path)
    assert ok, "%s: %r" % (case_id, detail.get("fails"))


# ---------- invariantes de politica ----------
def test_policy_weights_sum_one():
    p = PRIORITY_POLICY.parameters
    assert abs(p["w_mastery"] + p["w_error"] + p["w_recency"] - 1.0) < 1e-9


def test_exploration_epsilon_in_range():
    eps = PRIORITY_POLICY.parameters["exploration_epsilon"]
    assert 0.0 < eps < 1.0


def test_outputs_cite_versioned_policies(tmp_path):
    svc = StudentService(KB, GENDB, str(tmp_path / "s.sqlite"))
    _seed_minimal(svc)
    pr = PriorityCalculator(svc).calculate("t", limit=10)[0]
    assert (pr.policy_id, pr.policy_version) == (
        PRIORITY_POLICY.policy_id, PRIORITY_POLICY.version)
    item = LearningPathSelector(svc).select("t", limit=1)[0]
    assert item.knowledge_unit_id == pr.knowledge_unit_id
    assert item.priority == pr.priority_score
    d = DifficultySelector().select(mastery=0.5, confidence=0.5,
                                    attempt_count=3)
    assert (d["policy_id"], d["policy_version"]) == (
        DIFFICULTY_POLICY.policy_id, DIFFICULTY_POLICY.version)


# ---------- conservadurismo de dificultad (barrido) ----------
LEVELS = ["EASY", "MEDIUM", "HARD", "EXPERT"]
ACTIONS = ["REVIEW", "PRACTICE", "REINFORCE", "CHALLENGE", "MAINTAIN"]
STATUSES = ["EMERGING", "DEVELOPING", "PROFICIENT", "MASTERED"]


def test_difficulty_never_steps_more_than_one():
    sel = DifficultySelector()
    for m in (0.0, 0.3, 0.5, 0.7, 0.9, 1.0):
        for conf in (0.0, 0.4, 0.5, 0.9):
            for n in (2, 3, 5, 8):
                for cur in LEVELS:
                    for act in ACTIONS:
                        for st in STATUSES:
                            hist = [{"difficulty": cur, "signal": 1.0}] * 4
                            got = sel.select(
                                mastery=m, confidence=conf, attempt_count=n,
                                history=hist, current_difficulty=cur,
                                recommended_action=act, status=st)["difficulty"]
                            assert LEVELS.index(got) - LEVELS.index(cur) <= 1, (
                                m, conf, n, cur, act, st, got)


def test_at_risk_always_easy():
    sel = DifficultySelector()
    for m in (0.0, 0.5, 0.95):
        for conf in (0.0, 1.0):
            for n in (0, 1, 5, 10):
                for cur in ([""] + LEVELS):
                    got = sel.select(
                        mastery=m, confidence=conf, attempt_count=n,
                        history=[{"difficulty": "HARD", "signal": 1.0}] * 4,
                        current_difficulty=cur,
                        recommended_action="CHALLENGE",
                        status="AT_RISK")["difficulty"]
                    assert got == "EASY", (m, conf, n, cur, got)


def test_low_evidence_always_easy():
    sel = DifficultySelector()
    for n in (0, 1):
        got = sel.select(mastery=0.9, confidence=0.9, attempt_count=n,
                         history=[{"difficulty": "HARD", "signal": 1.0}] * 4,
                         current_difficulty="HARD",
                         recommended_action="CHALLENGE",
                         status="MASTERED")["difficulty"]
        assert got == "EASY", (n, got)


# ---------- contratos de seleccion ----------
def test_limit_zero_is_empty(tmp_path):
    svc = StudentService(KB, GENDB, str(tmp_path / "s.sqlite"))
    _seed_minimal(svc)
    assert LearningPathSelector(svc).select("t", limit=0) == []


def test_unit_kind_filter_respected(tmp_path):
    svc = StudentService(KB, GENDB, str(tmp_path / "s.sqlite"))
    _seed_minimal(svc)
    prios = PriorityCalculator(svc).calculate("t", limit=10,
                                              unit_kind="formula")
    assert prios and all(p.unit_kind == "formula" for p in prios)


def test_seed_accepted_but_order_stable(tmp_path):
    svc = StudentService(KB, GENDB, str(tmp_path / "s.sqlite"))
    _seed_minimal(svc)
    calc = PriorityCalculator(svc)
    a = [p.knowledge_unit_id for p in calc.calculate("t", limit=10, seed=1)]
    b = [p.knowledge_unit_id for p in calc.calculate("t", limit=10, seed=999)]
    assert a == b


def test_spec_abstains_without_resolvable_topic():
    sel = LearningPathSelector.__new__(LearningPathSelector)
    item = LearningPathItem(knowledge_unit_id="concept:inexistente",
                            unit_kind="concept", priority=10.0,
                            action="PRACTICE", difficulty="EASY",
                            target_topic=None)
    with pytest.raises(ValueError):
        sel.to_spec(item, seed=7)


# ---------- aislamiento y pureza ----------
def test_real_dbs_unchanged_by_selection(tmp_path):
    kb_before, gen_before, eval_before = _sha(KB), _sha(GENDB), _sha(EVALDB)
    svc = StudentService(KB, GENDB, str(tmp_path / "s.sqlite"))
    _seed_minimal(svc)
    sel = LearningPathSelector(svc)
    items = sel.select("t", limit=5, seed=7)
    assert items
    sel.to_spec(items[0], seed=7)
    assert _sha(KB) == kb_before
    assert _sha(GENDB) == gen_before
    assert _sha(EVALDB) == eval_before


def test_adaptive_modules_do_not_reference_eval():
    for name in ("models.py", "priority.py", "difficulty.py", "path.py",
                 "__init__.py"):
        src = (ROOT / "app" / "adaptive" / name).read_text(encoding="utf-8")
        assert "eval.sqlite" not in src, name


def test_no_llm_in_adaptive():
    import app.adaptive.difficulty as _d
    import app.adaptive.path as _p
    import app.adaptive.priority as _pr
    for mod in (_d, _p, _pr):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        for token in ("LLMProvider", "Gemini", "gemini", "openai", "OpenAI",
                      "anthropic", "llm_client", "EmbeddingProvider"):
            assert token not in src, (mod.__name__, token)
    for cls in (PriorityCalculator, DifficultySelector, LearningPathSelector):
        params = set(inspect.signature(cls.__init__).parameters)
        assert not (params & {"llm", "provider", "model"}), cls.__name__


def test_benchmark_results_artifact_is_fresh():
    res = json.loads((ROOT / "data" / "evaluation"
                      / "adaptive_core_results.json").read_text(
                          encoding="utf-8"))
    assert res["policy"] == "priority-policy@v1+difficulty-policy@v1"
    assert len(res["cases"]) == 20
    assert all(not c["fails"] for c in res["cases"])
