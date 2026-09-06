"""Adaptador Recommendation -> Examiner (Bloque B, §14). Flujo fino.

Recommendation -> QuestionBlueprint -> ExaminerEngine.generate().
El Examiner sigue siendo responsable de retrieval, evidencia, generacion,
validacion, formula, calculo y provenance: aqui no se duplica nada.

Limite honesto documentado: el Examiner no tiene filtro por concepto, asi
que `target_concepts` viaja como provenance + routing de tipo (CONCEPTUAL),
no como filtro de generacion.
"""
from __future__ import annotations

from app.examiner.models import (
    DIFFICULTIES,
    QUESTION_ORIGINS,
    QUESTION_TYPES,
    QuestionBlueprint,
)

from .models import Recommendation
from .path import strategy_for


def learning_objective_for(rec: Recommendation) -> str:
    """Plantilla determinista, no LLM, no fuente de decision."""
    return "%s:%s" % (rec.action, rec.knowledge_unit_id)


def to_blueprint(rec: Recommendation, *, seed: int = 0) -> QuestionBlueprint:
    if rec.target_topic is None:
        raise ValueError("sin tema resoluble para %r: no invento tema"
                         % rec.knowledge_unit_id)
    qtype = strategy_for(rec.action, rec.unit_kind, rec.reason_codes)
    if qtype not in QUESTION_TYPES:
        raise ValueError("tipo no válido: %r" % qtype)
    if rec.difficulty not in DIFFICULTIES:
        raise ValueError("dificultad no válida: %r" % rec.difficulty)
    return QuestionBlueprint(
        topic=rec.target_topic, section=rec.target_section or "",
        question_type=qtype, difficulty=rec.difficulty,
        learning_objective=learning_objective_for(rec),
        formula_ids=list(rec.target_formulas),
        concept_terms=list(rec.target_concepts), seed=seed)


def to_generate_kwargs(rec: Recommendation, *, seed: int = 0,
                       origin: str = "GENERATED") -> dict:
    """Kwargs directos para ExaminerEngine.generate()."""
    if origin not in QUESTION_ORIGINS:
        raise ValueError("origin no válido: %r" % origin)
    bp = to_blueprint(rec, seed=seed)
    return {"topic": bp.topic, "section": bp.section,
            "question_type": bp.question_type, "difficulty": bp.difficulty,
            "formula_id": bp.formula_ids[0] if bp.formula_ids else "",
            "seed": seed, "origin": origin}
