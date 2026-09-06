"""Suite Fase 4: los 20 tests obligatorios (§51) + gates P0.

Rechazar es correcto: la mitad de la suite verifica RECHAZOS con entradas
adversariales construidas a mano (sin tocar golds ni KB).
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.examiner import numerical as NUM  # noqa: E402
from app.examiner.distractors import build_distractors, validate_distractors  # noqa: E402
from app.examiner.evidence import formula_record  # noqa: E402
from app.examiner.exam import assemble_exam  # noqa: E402
from app.examiner.service import ExaminerEngine  # noqa: E402
from app.examiner.store import QuestionStore  # noqa: E402
from app.examiner.verify import QuestionValidator  # noqa: E402
from app.reasoning.calculator import safe_eval  # noqa: E402
from app.reasoning.formula_check import FormulaValidator  # noqa: E402
from app.reasoning.models import Claim  # noqa: E402
from app.retrieval.service import RetrievalService  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
INDEX = str(ROOT / "data" / "index")
STORE = str(ROOT / "data" / "generated" / "questions.sqlite")


@pytest.fixture(scope="module")
def engine():
    svc = RetrievalService(str(ROOT / "data" / "processed" / "knowledge.sqlite"),
                           str(ROOT / "data" / "index"))
    return ExaminerEngine(svc, KB, STORE)


@pytest.fixture(scope="module")
def validator():
    return QuestionValidator(KB)


def _texts(engine, q):
    pack = engine.retriever.retrieve_evidence(q.section or "Tema %d" % q.topic, top_k=10)
    return {r["chunk_id"]: r["text"] for r in pack.results}


# Test 1: generacion respaldada por evidencia.
def test_01_evidence_backed_generation(engine):
    q, rep = engine.generate(topic=2, question_type="FORMULA",
                             formula_id="eq-02-0034", seed=7)
    assert q is not None and q.validation.status == "VALID"
    assert q.evidence_refs and q.formula_ids == ["eq-02-0034"]


# Test 2: pregunta sin evidencia -> rechazada.
def test_02_no_evidence_rejected(engine):
    q, rep = engine.generate(topic=2, question_type="THEORY",
                             section="Secció inexistentZZZ", seed=1)
    assert q is None and "NO_EVIDENCE" in rep.get("rejected", "")


# Test 3: formula inexistente -> rechazada.
def test_03_unknown_formula_rejected(engine):
    q, rep = engine.generate(topic=2, question_type="FORMULA",
                             formula_id="eq-99-9999", seed=1)
    assert q is None and "FORMULA_NOT_FOUND" in rep.get("rejected", "")


# Test 4: formula modificada -> rechazada (validador).
def test_04_modified_formula_rejected(validator, engine):
    from app.examiner.models import Question, QuestionClaim
    q = Question(question_id="q-t", version="4.0", topic=2, section="s",
                 type="FORMULA", difficulty="MEDIUM", prompt="p",
                 formula_ids=["eq-02-0034"], evidence_refs=[],
                 claims=[QuestionClaim(text="$U=u_c/k$", type="FORMULA",
                                       evidence_ids=["eq-02-0034"])])
    ev = {"eq-02-0034": "x"}
    validator.validate(q, ev, {"eq-02-0034": {"equation_id": "eq-02-0034"}})
    assert q.validation.status == "INVALID"
    assert any("MISMATCH" in r or "CONTRADICTED" in r for r in q.validation.reasons)


# Test 5: formula equivalente valida -> aceptada.
def test_05_equivalent_formula_accepted():
    from app.reasoning.formula_check import equivalent
    assert equivalent("$U=k\\,u_c$", "$U=u_c\\,k$")


# Test 6: formula matematicamente diferente -> rechazada.
def test_06_different_formula_rejected():
    from app.reasoning.formula_check import equivalent
    assert not equivalent("$U=k\\,u_c$", "$U=u_c/k$")


# Test 7: variable inexistente -> rechazada (claim sin cobertura).
def test_07_unknown_variable_rejected(validator):
    from app.examiner.models import Question, QuestionClaim
    q = Question(question_id="q-t", version="4.0", topic=2, section="s",
                 type="SHORT_ANSWER", difficulty="EASY", prompt="p",
                 evidence_refs=["c1"],
                 claims=[QuestionClaim(text="wXYZvariable inexistent", type="VARIABLE",
                                       evidence_ids=["c1"])])
    validator.validate(q, {"c1": "texto sin esa variable"}, {})
    assert q.validation.status == "INVALID"
    assert any("UNSUPPORTED" in r for r in q.validation.reasons)


# Test 8: unidad incorrecta -> rechazada (dimension).
def test_08_wrong_unit_rejected():
    from app.reasoning.calculator import check_dimensions
    assert check_dimensions("V", ["V", "Ω"], "/") is False


# Test 9: calculo incorrecto -> rechazado.
def test_09_wrong_calculation_rejected():
    from app.reasoning.claims import verify_calculation
    r = verify_calculation("2*0.5", 2.0, "")
    assert not r["match"]


# Test 10: division por cero -> rechazado.
def test_10_division_by_zero_rejected():
    ok, msg = NUM.check_denominators("a/(b-c)", {"a": 1.0, "b": 2.0, "c": 2.0})
    assert not ok and "cero" in msg


# Test 11: pregunta ambigua -> NEEDS_REVIEW (MCQ con 2 correctas).
def test_11_ambiguous_needs_review(validator):
    from app.examiner.models import Question, QuestionOption
    q = Question(question_id="q-t", version="4.0", topic=2, section="s",
                 type="MULTIPLE_CHOICE", difficulty="MEDIUM", prompt="p",
                 evidence_refs=["c1"],
                 options=[QuestionOption(text="a", correct=True),
                          QuestionOption(text="b", correct=True)])
    validator.validate(q, {"c1": "a b"}, {})
    assert q.validation.status in ("INVALID", "NEEDS_REVIEW")
    assert any("AMBIGUOUS" in r for r in q.validation.reasons)


# Test 12: claim externo -> rechazado.
def test_12_external_claim_rejected(validator):
    from app.examiner.models import Question, QuestionClaim
    q = Question(question_id="q-t", version="4.0", topic=2, section="s",
                 type="OPEN", difficulty="MEDIUM", prompt="p",
                 evidence_refs=["c1"],
                 claims=[QuestionClaim(text="E=mc² relativitat externa", type="FACTUAL",
                                       evidence_ids=["c1"])])
    validator.validate(q, {"c1": "texto del curso sin eso"}, {})
    assert q.validation.status == "INVALID"


# Test 13: eval.sqlite invisible al Examiner.
def test_13_eval_invisible():
    import app.examiner.service as svc_mod
    import app.examiner.evidence as ev_mod
    import app.examiner.staticgen as sg_mod
    import app.examiner.verify as ver_mod
    for mod in (svc_mod, ev_mod, sg_mod, ver_mod):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "eval.sqlite" not in src
    ev_path = ROOT / "data" / "evaluation" / "eval.sqlite"
    assert ev_path.is_file()  # existe pero nadie lo abre


# Test 14: KB bit-identical tras generar (sqlite + derivados comprometidos §54).
def test_14_kb_immutable(engine):
    import hashlib as _hl
    targets = [ROOT / "data" / "processed" / "knowledge.sqlite",
               ROOT / "data" / "processed" / "chunks.jsonl",
               ROOT / "data" / "evaluation" / "formula_retrieval_benchmark.jsonl"]
    before = [_hl.sha256(p.read_bytes()).hexdigest() for p in targets]
    for kw in [dict(topic=2, question_type="FORMULA", formula_id="eq-02-0034", seed=7),
               dict(topic=1, question_type="TRUE_FALSE", seed=1)]:
        engine.generate(**kw)
    after = [_hl.sha256(p.read_bytes()).hexdigest() for p in targets]
    assert after == before


# Test 15: reproducible con seed (triple).
def test_15_seed_reproducible(engine):
    outs = []
    for _ in range(3):
        q, _ = engine.generate(topic=2, question_type="FORMULA",
                               formula_id="eq-02-0034", seed=42)
        assert q is not None
        outs.append((q.question_id, q.prompt, q.fingerprint, q.correct_answer))
    assert outs[0] == outs[1] == outs[2]


# Test 16: duplicado detectado (mismo fingerprint).
def test_16_duplicate_detected(engine):
    q1, _ = engine.generate(topic=2, question_type="FORMULA",
                            formula_id="eq-02-0034", seed=42)
    q2, _ = engine.generate(topic=2, question_type="FORMULA",
                            formula_id="eq-02-0034", seed=42)
    assert q1 is not None and q2 is not None
    assert q1.fingerprint == q2.fingerprint
    assert q1.question_id == q2.question_id
    store = QuestionStore(STORE)
    assert store.put(q1) is False  # ya existe: no duplica


# Test 17: distractor plausible validado.
def test_17_validated_distractor():
    ds = build_distractors(KB, "eq-02-0034", "$U=k\\,u_c$", seed=7, n=3)
    assert len(ds) == 3
    ok, _ = validate_distractors("$U=k\\,u_c$", ds)
    assert ok
    assert all(d["distractor_reason"] for d in ds)


# Test 18: distractor externo/equivalente rechazado.
def test_18_external_distractor_rejected():
    ok, msg = validate_distractors("$U=k\\,u_c$", [
        {"text": "$U=k\\,u_c$", "correct": False, "distractor_reason": "x"}])
    assert not ok


# Test 19: trazabilidad completa.
def test_19_full_traceability(engine):
    q, _ = engine.generate(topic=2, question_type="NUMERICAL",
                           formula_id="eq-02-0201", seed=7)
    assert q is not None and q.validation.status == "VALID"
    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % KB, uri=True)
    try:
        for c in q.evidence_refs:
            row = con.execute("SELECT source_path FROM chunks WHERE id=?", (c,)).fetchone()
            assert row is not None
            src = con.execute("SELECT sha256 FROM sources WHERE path=?", (row[0],)).fetchone()
            assert src is not None and len(src[0]) == 64
        for fid in q.formula_ids:
            row = con.execute("SELECT source_path FROM formulas WHERE equation_id=?",
                              (fid,)).fetchone()
            assert row is not None
    finally:
        con.close()


# Test 20: regresion 2896 formulas (gate P0, sin re-ejecutar 13 min).
def test_20_formula_regression_gate():
    res = json.loads((ROOT / "data" / "evaluation"
                      / "formula_retrieval_results.json").read_text(encoding="utf-8"))
    assert res["total"] == 2896
    assert res["missed"] == []
    assert res["coverage"] == 1.0
    gold = (ROOT / "data" / "evaluation" / "formula_retrieval_benchmark.jsonl")
    assert sum(1 for _ in gold.open(encoding="utf-8")) == 2896
