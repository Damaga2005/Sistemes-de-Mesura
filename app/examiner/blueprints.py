"""QuestionBlueprint: se construye DESPUES de verificar evidencia (§10).

Entradas: topic, section?, type, difficulty?, formula_id?, seed.
La evidencia manda: si falta, blueprint None + motivo (el caller RECHAZA,
nunca genera). Dificultad desde rasgos observables.
"""
from __future__ import annotations

from app.retrieval.formula import symbols_of

from . import evidence as EV
from .models import QuestionBlueprint, difficulty_for


def _symbols(expression: str) -> list[str]:
    return sorted({s for s in symbols_of(expression) if not s.startswith("base:")},
                  key=lambda s: (len(s), s))


def build_blueprint(retriever, kb_path: str, *, topic: int, section: str = "",
                    question_type: str, difficulty: str = "", formula_id: str = "",
                    seed: int = 0) -> tuple[QuestionBlueprint | None, str, dict]:
    """Devuelve (blueprint|None, motivo, evidencia_resumen)."""
    formulas, variables, units, conditions = [], [], {}, []
    if formula_id:
        try:
            rec = EV.formula_record(kb_path, formula_id)
        except EV.EvidenceError as e:
            return None, str(e), {}
        if rec["topic"] != topic:
            return None, "FORMULA_NOT_FOUND: %s no es del Tema %d" % (formula_id, topic), {}
        formulas = [formula_id]
        variables = [s for s in _symbols(rec["expression"]) if len(s) <= 12][:8]
        section = section or rec["section_h2"] or rec.get("h1", "") or rec.get("doc_title", "")
    query = section or ("Tema %d" % topic)
    # Nota: el formula_id NUNCA va al texto de query (eq-02-0034 contaminaria
    # con tokens 'eq/0034'); viaja en el campo formula_ids + union exacta.
    try:
        pack = EV.evidence_for_blueprint(retriever, kb_path, query, topic)
    except EV.EvidenceError as e:
        return None, str(e), {}
    steps = {"FORMULA": 1, "NUMERICAL": 3, "MULTI_STEP": 4, "MULTIPLE_CHOICE": 2,
             "TRUE_FALSE": 1, "THEORY": 1, "CONCEPTUAL": 2, "SHORT_ANSWER": 1,
             "OPEN": 2}.get(question_type, 1)
    diff = difficulty or difficulty_for(len(formulas), len(variables), steps,
                                        question_type == "MULTIPLE_CHOICE")
    objective = "%s [%s/%s]" % (section or ("Tema %d" % topic), question_type, diff)
    bp = QuestionBlueprint(topic=topic, section=section, question_type=question_type,
                           difficulty=difficulty or diff, learning_objective=objective,
                           formula_ids=formulas, concept_terms=[],
                           variables=variables, units=units, conditions=conditions,
                           expected_reasoning_steps=["recuperar evidencia"] * steps,
                           answer_constraints=[], seed=seed)
    ev = {"chunks": len(pack.results), "formulas": len(pack.formulas),
          "primary": [r["chunk_id"] for r in pack.primary_evidence]}
    return bp, "OK", ev
