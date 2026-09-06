"""Tests PASO 2 Fase 6: cierre de los 4 gaps (21 tests obligatorios).

Nada adaptativo, nada de UI, nada de Fase 7. Solo contratos.
"""
import hashlib
import json
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.examiner.models import EXAM_KINDS, QUESTION_ORIGINS, Question  # noqa: E402
from app.examiner.service import ExaminerEngine  # noqa: E402
from app.examiner.store import QuestionStore  # noqa: E402
from app.retrieval.service import RetrievalService  # noqa: E402
from app.student.policy import (DIFFICULTY_POLICY, MASTERY_POLICY,  # noqa: E402
                                POLICIES, Policy, SPACING_POLICY, get_policy)
from app.student.service import StudentService  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
INDEX = str(ROOT / "data" / "index")
GENDB = str(ROOT / "data" / "generated" / "questions.sqlite")
EVALDB = str(ROOT / "data" / "evaluation" / "eval.sqlite")


@pytest.fixture(scope="module")
def engine():
    svc = RetrievalService(str(ROOT / "data" / "processed" / "knowledge.sqlite"),
                           str(ROOT / "data" / "index"))
    return ExaminerEngine(svc, KB, GENDB)


def _tmp_store(tmp_path):
    return QuestionStore(tmp_path / "q.sqlite")


# ---------- Origin (1-5) ----------
def test_01_default_origin_is_generated(engine):
    q, _ = engine.generate(topic=2, question_type="TRUE_FALSE", seed=42)
    assert q is not None and q.origin == "GENERATED"


@pytest.mark.parametrize("origin", ["REAL_EXAM", "IMPORTED", "MANUAL"])
def test_02_03_04_origins_accepted(engine, origin):
    q, _ = engine.generate(topic=2, question_type="TRUE_FALSE", seed=42,
                           origin=origin)
    assert q is not None and q.origin == origin


def test_02b_invalid_origin_rejected(engine):
    with pytest.raises(ValueError):
        engine.generate(topic=2, question_type="TRUE_FALSE", seed=42,
                        origin="FORGED")


def test_05_origin_preserves_provenance(engine, tmp_path):
    store = _tmp_store(tmp_path)
    svc = RetrievalService(str(ROOT / "data" / "processed" / "knowledge.sqlite"),
                           str(ROOT / "data" / "index"))
    eng = ExaminerEngine(svc, KB, str(tmp_path / "q.sqlite"))
    q, _ = eng.generate(topic=2, question_type="TRUE_FALSE", seed=42,
                        origin="IMPORTED")
    assert q is not None
    # generate() ya persiste: verificar la fila guardada conserva origin + provenance
    con = sqlite3.connect("file:%s?mode=ro" % eng.store.path, uri=True)
    try:
        row = con.execute("SELECT origin, body_json FROM questions WHERE question_id=?",
                          (q.question_id,)).fetchone()
    finally:
        con.close()
    assert row[0] == "IMPORTED"
    body = json.loads(row[1])
    assert body["origin"] == "IMPORTED"
    assert body["evidence_refs"] and body["source_refs"]


# ---------- Exams (6-8) ----------
def test_06_exam_generated_default(tmp_path):
    store = _tmp_store(tmp_path)
    store.put_exam("ex-1", 1, {}, ["q-1"], {"examiner": "examiner-4.0"})
    assert store.get_exam("ex-1")["kind"] == "GENERATED"


def test_07_exam_real_exam_roundtrip(tmp_path):
    store = _tmp_store(tmp_path)
    store.put_exam("ex-r", 2, {}, ["q-9"], {"examiner": "examiner-4.0"},
                   kind="REAL_EXAM", source="convocatoria 2024")
    got = store.get_exam("ex-r")
    assert got["kind"] == "REAL_EXAM" and got["source"] == "convocatoria 2024"
    assert got["question_ids"] == ["q-9"]


def test_08_real_exam_does_not_touch_kb(tmp_path):
    before = hashlib.sha256(Path(KB).read_bytes()).hexdigest()
    store = _tmp_store(tmp_path)
    store.put_exam("ex-r2", 3, {}, ["q-9"], {}, kind="REAL_EXAM", source="x")
    after = hashlib.sha256(Path(KB).read_bytes()).hexdigest()
    assert before == after


def test_08b_invalid_exam_kind_rejected(tmp_path):
    store = _tmp_store(tmp_path)
    with pytest.raises(ValueError):
        store.put_exam("ex-bad", 1, {}, [], {}, kind="FORGED")


# ---------- Policies (9-12) ----------
def test_09_difficulty_policy_stable():
    assert DIFFICULTY_POLICY.key() == "difficulty-policy@v1"
    # Bloque A: DifficultySelector consume difficulty-policy-v1 -> active.
    # (Paso 2 la dejo en 'reserved' porque aun no estaba implementada.)
    assert DIFFICULTY_POLICY.status == "active"


def test_10_spacing_policy_stable():
    assert SPACING_POLICY.key() == "spacing-policy@v1"
    # Bloque B: spacing-policy-v1 activa con buckets + criticidad + epsilon
    # de categoria (Paso 2 la dejo en 'reserved' sin parametros).
    assert SPACING_POLICY.status == "active"
    p = SPACING_POLICY.parameters
    assert p["buckets_days"] == [1, 7, 30]
    assert 0.0 < p["high_priority_min_score"]


def test_11_policy_serialization_deterministic():
    a = MASTERY_POLICY.dumps()
    b = Policy.loads(a).dumps()
    assert a == b
    assert json.loads(a)["parameters"]["confidence_n"] == 8
    with pytest.raises(Exception):
        MASTERY_POLICY.new_attr = 1  # frozen


def test_12_replay_keeps_historical_versions(tmp_path):
    svc = StudentService(KB, GENDB, str(tmp_path / "s.sqlite"))
    out = svc.submit("synth-pol", "q-7c52a0995094", "V", attempt_id="att-pol-1")
    assert out["correction"]["mastery_policy_version"] == "mastery-policy-v1"
    con = sqlite3.connect("file:%s?mode=ro" % svc.store.path, uri=True)
    try:
        versions = {r[0] for r in con.execute(
            "SELECT DISTINCT policy_version FROM mastery_events").fetchall()}
    finally:
        con.close()
    assert versions == {"mastery-policy-v1"}
    assert get_policy("mastery-policy", "v1").status == "active"
    with pytest.raises(KeyError):
        get_policy("mastery-policy", "v99")


# ---------- Weak units (13-15) ----------
def _seed_ties(svc):
    con = svc.store.connect()
    try:
        con.execute("INSERT OR IGNORE INTO students(student_id, created_at) VALUES(?,?)",
                    ("tie", "2026-01-01T00:00:00+00:00"))
        for uid in ["formula:eq-b", "concept:alfa", "topic:T09"]:
            con.execute(
                "INSERT OR REPLACE INTO mastery_states(mastery_id,student_id,"
                "knowledge_unit_id,unit_kind,score,confidence,attempt_count,"
                "correct_count,incorrect_count,error_counts_json,status,policy_version)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                ("ms-tie-" + uid.replace(":", "-"), "tie", uid, uid.split(":")[0],
                 0.5, 0.5, 3, 1, 2, "{}", "EMERGING", "mastery-policy-v1"))
        con.commit()
    finally:
        con.close()


def test_13_14_15_exact_tie_total_order(tmp_path):
    from app.student.service import StudentService as _SS
    p1 = tmp_path / "s1.sqlite"
    p2 = tmp_path / "s2.sqlite"
    for p in (p1, p2):
        svc = _SS(KB, GENDB, str(p))
        _seed_ties(svc)
    outs = []
    for p in (p1, p2):
        svc = _SS(KB, GENDB, str(p))
        outs.append(svc.get_weak_units("tie", limit=10))
    assert outs[0] == outs[1]
    ids = [r["knowledge_unit_id"] for r in outs[0][:3]]
    assert ids == sorted(ids), ids  # desempate canonico total


# ---------- Skill (16-17) ----------
def test_16_no_fictitious_skills(tmp_path):
    svc = StudentService(KB, GENDB, str(tmp_path / "s.sqlite"))
    for kw in [dict(topic=2, question_type="TRUE_FALSE", seed=1),
               dict(topic=2, question_type="FORMULA", formula_id="eq-02-0034", seed=2),
               dict(topic=9, question_type="SHORT_ANSWER", seed=3)]:
        from app.examiner.service import ExaminerEngine as _EE
        from app.retrieval.service import RetrievalService as _RS
        eng = _EE(_RS(KB, INDEX), KB, GENDB)
        q, _ = eng.generate(**kw)
        if q is not None:
            svc.submit("synth-sk", q.question_id, q.correct_answer or "V",
                       attempt_id="att-sk-%d" % q.topic)
    con = sqlite3.connect("file:%s?mode=ro" % svc.store.path, uri=True)
    try:
        kinds = {r[0] for r in con.execute(
            "SELECT DISTINCT unit_kind FROM mastery_states").fetchall()}
    finally:
        con.close()
    assert "skill" not in kinds


def test_17_effective_contract_is_four_kinds():
    import app.student.models as _m
    src = Path(_m.__file__).read_text(encoding="utf-8")
    assert "topic | section | concept" in src and "FUTURO" in src


# ---------- Isolation (18-19) ----------
def test_18_kb_unchanged(tmp_path):
    before = hashlib.sha256(Path(KB).read_bytes()).hexdigest()
    svc = StudentService(KB, GENDB, str(tmp_path / "s.sqlite"))
    svc.submit("synth-iso", "q-7c52a0995094", "V", attempt_id="att-iso-1")
    after = hashlib.sha256(Path(KB).read_bytes()).hexdigest()
    assert before == after


def test_19_eval_unchanged_and_isolated(tmp_path):
    before = hashlib.sha256(Path(EVALDB).read_bytes()).hexdigest()
    svc = StudentService(KB, GENDB, str(tmp_path / "s.sqlite"))
    svc.submit("synth-iso2", "q-7c52a0995094", "V", attempt_id="att-iso-2")
    after = hashlib.sha256(Path(EVALDB).read_bytes()).hexdigest()
    assert before == after
    import app.student.service as _ss
    import app.correction.service as _cs
    for mod in (_ss, _cs):
        assert "eval.sqlite" not in Path(mod.__file__).read_text(encoding="utf-8")


# ---------- Regression (20) ----------
def test_20_phases_0_to_5_present():
    for rel in ["tests/test_phase0.py", "tests/test_phase1.py",
                "tests/retrieval/test_engine.py", "tests/reasoning/test_integration.py",
                "tests/examiner/test_examiner.py", "tests/correction/test_correction.py",
                "tests/student/test_mastery.py"]:
        assert (ROOT / rel).is_file(), rel


# ---------- Formula gate (21) ----------
def test_21_formula_gate_2896():
    res = json.loads((ROOT / "data" / "evaluation"
                      / "formula_retrieval_results.json").read_text(encoding="utf-8"))
    assert res["total"] == 2896 and res["missed"] == [] and res["coverage"] == 1.0
    # Spot-check vivo con queries del propio gold (no inventadas aqui).
    gold = {}
    for line in (ROOT / "data" / "evaluation"
                 / "formula_retrieval_benchmark.jsonl").read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        gold[d["formula_id"]] = d["acceptable_queries"]
    svc = RetrievalService(str(ROOT / "data" / "processed" / "knowledge.sqlite"),
                           str(ROOT / "data" / "index"))
    for fid in ["eq-02-0034", "eq-04-0058", "eq-09-0022"]:
        hit = any(fid in [f["equation_id"]
                          for f in svc.retrieve_evidence(q, top_k=10).formulas]
                  for q in gold[fid])
        assert hit, fid
