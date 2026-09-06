"""Tests Fase 7 Bloque 2: Exam Session Core.

20 casos del benchmark (fuente unica:
data/evaluation/exam_session_core_benchmark.jsonl) + matriz pura de
validacion y maquina de estados + invariantes (sin adaptive, sin LLM,
legado intacto). Sin UI, sin grading, sin Fase 8.
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.exam.models import (  # noqa: E402
    EXAM_SPEC_VERSION,
    ExamBlueprint,
    ExamError,
    SnapshotInvalid,
    TRANSITIONS,
    transition,
)
from app.exam_session_benchmark import load_cases, run_case  # noqa: E402

CASES = {c["case_id"]: c for c in load_cases()}

VALID_BP = {"title": "T", "version": "1", "seed": 7,
            "duration_seconds": 600, "question_count": 3, "topics": [2],
            "types": {"TRUE_FALSE": 2, "FORMULA": 1},
            "difficulty": {"EASY": 1.0},
            "required_formula_ids": ["eq-02-0034"],
            "exam_kind": "MOCK_EXAM"}


# ---------- 20 casos del benchmark ----------
@pytest.mark.parametrize("case_id", sorted(CASES), ids=sorted(CASES))
def test_benchmark_case(tmp_path, case_id):
    ok, detail = run_case(CASES[case_id], tmp_path)
    assert ok, "%s: %r" % (case_id, detail.get("fails"))


# ---------- blueprint: matriz pura ----------
def _bp(**kw):
    d = dict(VALID_BP)
    d.update(kw)
    return ExamBlueprint.from_dict(d)


def test_blueprint_valid_pure():
    assert _bp().validate() == []
    assert _bp().exam_id().startswith("exm-")
    assert _bp().exam_id() == _bp().exam_id()
    assert _bp(version="2").exam_id() != _bp().exam_id()


@pytest.mark.parametrize("kw,msg", [
    ({"title": ""}, "title"),
    ({"question_count": 0}, "question_count"),
    ({"topics": []}, "topics"),
    ({"topics": ["2"]}, "topics"),
    ({"types": {"NOPE": 3}}, "tipo desconocido"),
    ({"types": {"TRUE_FALSE": 1}}, "suma de tipos"),
    ({"difficulty": {"EASY": 0.5}}, "sumar 1.0"),
    ({"difficulty": {"HARD2": 1.0}}, "dificultad desconocida"),
    ({"duration_seconds": 0}, "duration_seconds"),
    ({"ordering_policy": "azar"}, "ordering desconocido"),
    ({"exam_kind": "FINAL"}, "exam_kind desconocido"),
    ({"policy_version": "exam-spec-v99"}, "policy debe ser"),
    ({"scoring": {"default_points": 0}}, "default_points"),
    ({"scoring": {"required_default": "si"}}, "required_default"),
    ({"concept_requirements": [{"x": 1}]}, "concept_requirements"),
])
def test_blueprint_invalid_pure(kw, msg):
    errs = _bp(**kw).validate()
    assert any(msg in e for e in errs), (kw, errs)


def test_blueprint_sections_int_keys():
    bp = ExamBlueprint.from_dict({**VALID_BP, "sections": {"2": ["3E"]}})
    assert bp.sections == {2: ["3E"]}
    assert bp.validate() == []


# ---------- maquina de estados: exhaustiva ----------
def test_transition_table_shape():
    assert set(TRANSITIONS) == {"CREATED", "READY", "IN_PROGRESS", "EXPIRED",
                                "CANCELLED", "SUBMITTED", "GRADED"}
    assert "PAUSED" not in TRANSITIONS


def test_all_valid_transitions():
    assert transition("CREATED", "READY") == "READY"
    assert transition("CREATED", "CANCELLED") == "CANCELLED"
    assert transition("READY", "IN_PROGRESS") == "IN_PROGRESS"
    assert transition("READY", "CANCELLED") == "CANCELLED"
    assert transition("IN_PROGRESS", "SUBMITTED") == "SUBMITTED"
    assert transition("IN_PROGRESS", "EXPIRED") == "EXPIRED"
    assert transition("IN_PROGRESS", "CANCELLED") == "CANCELLED"


@pytest.mark.parametrize("cur,tgt", [
    ("CREATED", "SUBMITTED"), ("CREATED", "IN_PROGRESS"),
    ("CREATED", "EXPIRED"), ("READY", "SUBMITTED"), ("READY", "EXPIRED"),
    ("IN_PROGRESS", "READY"), ("IN_PROGRESS", "CREATED"),
    ("EXPIRED", "IN_PROGRESS"), ("EXPIRED", "SUBMITTED"),
    ("EXPIRED", "CANCELLED"), ("CANCELLED", "IN_PROGRESS"),
    ("CANCELLED", "READY"), ("SUBMITTED", "IN_PROGRESS"),
    ("SUBMITTED", "CANCELLED"), ("SUBMITTED", "EXPIRED"),
    ("GRADED", "IN_PROGRESS"), ("CREATED", "PAUSED"),
    ("IN_PROGRESS", "PAUSED"), ("READY", "READY"),
    ("SUBMITTED", "EXPIRED"), ("GRADED", "SUBMITTED"),
])
def test_invalid_transitions_rejected(cur, tgt):
    with pytest.raises(ExamError):
        transition(cur, tgt)


def test_graded_only_from_submitted_or_expired():
    # B3: GRADED habilitado solo via grading (artefactos completos).
    assert transition("SUBMITTED", "GRADED") == "GRADED"
    assert transition("EXPIRED", "GRADED") == "GRADED"
    for cur in ("CREATED", "READY", "IN_PROGRESS", "CANCELLED", "GRADED"):
        with pytest.raises(ExamError):
            transition(cur, "GRADED")
    with pytest.raises(ExamError):
        transition("NOPE", "READY")
    assert issubclass(SnapshotInvalid, ExamError)


# ---------- invariantes ----------
def test_no_adaptive_no_llm_in_exam():
    tokens = ("PriorityCalculator", "DifficultySelector",
              "LearningPathSelector", "RecommendationBuilder", "LLMProvider",
              "Gemini", "gemini", "openai", "OpenAI", "anthropic",
              "llm_client", "EmbeddingProvider")
    for name in ("models.py", "store.py", "service.py", "__init__.py"):
        src = (ROOT / "app" / "exam" / name).read_text(encoding="utf-8")
        for t in tokens:
            assert not re.search(r"\b%s\b" % t, src), (name, t)


def test_canonical_db_constant_and_legacy_untouched():
    from app.exam.store import CANONICAL_STUDENT_DB
    assert CANONICAL_STUDENT_DB == "data/student/student.sqlite"
    import app.exam.service as _s
    import app.exam.store as _st
    for mod in (_s, _st):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        uses = re.findall(r"""["'][^"'\\n]*processed/students[^"'\\n]*["']""",
                          src)
        assert not uses, (mod.__name__, uses)


def test_results_artifact_fresh():
    import json
    res = json.loads((ROOT / "data" / "evaluation"
                      / "exam_session_results.json").read_text(
                          encoding="utf-8"))
    assert res["spec"] == "exam-spec-v1"
    assert len(res["cases"]) == 20
    assert all(not c["fails"] for c in res["cases"])


def test_exam_spec_version():
    assert EXAM_SPEC_VERSION == "exam-spec-v1"
    assert _bp().policy_id == "exam-spec"
