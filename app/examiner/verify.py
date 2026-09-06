"""Validador de preguntas (§28-33): la candidata del LLM o del generador
determinista solo llega a VALID si pasa TODO. Rechazar es correcto (§66).
"""
from __future__ import annotations

import re
import sqlite3

from app.reasoning.claims import ClaimVerifier
from app.reasoning.formula_check import FormulaValidator

from .models import Question


def _kb_has(kb_path: str, table: str, id_value: str, col: str = "id") -> bool:
    con = sqlite3.connect("file:%s?mode=ro" % kb_path, uri=True)
    try:
        return con.execute("SELECT 1 FROM %s WHERE %s=?" % (table, col),
                           (id_value,)).fetchone() is not None
    finally:
        con.close()


class QuestionValidator:
    def __init__(self, kb_path: str) -> None:
        self.kb_path = kb_path
        self.formulas = FormulaValidator(kb_path)
        self.claims = ClaimVerifier(self.formulas)

    def validate(self, q: Question, evidence_texts: dict[str, str],
                 formulas: dict[str, dict]) -> Question:
        reasons: list[str] = []
        checks: dict = {}
        # 1. Evidencia y provenance.
        if not q.evidence_refs:
            reasons.append("NO_EVIDENCE")
        checks["evidence"] = bool(q.evidence_refs)
        missing_ev = [e for e in q.evidence_refs if e not in evidence_texts]
        if missing_ev:
            reasons.append("PROVENANCE_INCOMPLETE")
        checks["provenance"] = not missing_ev
        # Coherencia topica: la MAYORIA de la evidencia debe ser del tema de la
        # pregunta (el caso todo-T9-para-T2 se rechaza; contexto transversal
        # minoritario —comparaciones del propio material— se admite y registra).
        ev_topics: list = []
        if q.evidence_refs:
            con2 = sqlite3.connect("file:%s?mode=ro" % self.kb_path, uri=True)
            try:
                rows = con2.execute(
                    "SELECT topic FROM chunks WHERE id IN (%s)" % ",".join(
                        "?" * len(q.evidence_refs)), tuple(q.evidence_refs)).fetchall()
                ev_topics = [r[0] for r in rows]
            finally:
                con2.close()
        foreign = sum(1 for t in ev_topics if t != q.topic)
        mismatch = bool(ev_topics) and foreign * 2 > len(ev_topics)
        if mismatch:
            reasons.append("EVIDENCE_TOPIC_MISMATCH")
        checks["topic_coherence"] = not mismatch
        # 2. Formulas: existen, canonicas o equivalentes validadas.
        form_ok = True
        for fid in q.formula_ids:
            status, _ = self.formulas.check_id(fid)
            if status != "EXACT_MATCH":
                form_ok = False
                reasons.append("FORMULA_NOT_FOUND:%s" % fid)
        for c in q.claims:
            if c.type == "FORMULA":
                m = re.search(r"\$.+?\$", c.text)
                if m and not any(c.evidence_ids):
                    st, _ = self.formulas.check_latex(m.group(0))
                    if st == "MISSING":
                        form_ok = False
                        reasons.append("FORMULA_MISMATCH")
        checks["formula"] = form_ok
        # 3. Claims.
        bad = 0
        for c in q.claims:
            self.claims.verify(c, evidence_texts, formulas)
            if c.status in ("UNSUPPORTED", "CONTRADICTED"):
                bad += 1
                reasons.append("UNSUPPORTED_CLAIM" if c.status == "UNSUPPORTED"
                               else "CONTRADICTED_CLAIM")
        checks["claims"] = bad == 0
        # 4. Calculo (si hay): re-calculo independiente ya hecho en numerical;
        # aqui se exige bandera de verificacion.
        calc_ok = True
        calc = q.solution.calculation
        if calc and not calc.get("verified"):
            calc_ok = False
            reasons.append("CALCULATION_ERROR")
        checks["calculation"] = calc_ok
        # 5. Unidades/dimensiones conocidas o ausencia honesta.
        unit_ok = True
        if q.units.get("__status__") == "UNIT_VALIDATION_UNAVAILABLE":
            checks["units"] = "unavailable"
        elif q.units.get("__dimension_ok__") is False:
            unit_ok = False
            reasons.append("DIMENSION_ERROR")
        else:
            checks["units"] = True
        if not unit_ok:
            reasons.append("UNIT_UNSUPPORTED")
        # 6. MCQ: exactamente 1 correcta y no equivalente a la canonica.
        if q.type == "MULTIPLE_CHOICE":
            correct = [o for o in q.options if o.correct]
            if len(correct) != 1:
                reasons.append("AMBIGUOUS")
            checks["unique_answer"] = len(correct) == 1
        else:
            checks["unique_answer"] = True
        # 7. Ambiguedad explicita del generador.
        if q.validation.reasons and "AMBIGUOUS" in q.validation.reasons:
            reasons.append("AMBIGUOUS")
        # 8. Score de evidencia.
        n_ev = len(q.evidence_refs)
        ev_score = "fully_supported" if (n_ev >= 1 and not missing_ev) else (
            "partially_supported" if n_ev >= 1 else "unsupported")
        # Veredicto.
        fatal = {"NO_EVIDENCE", "PROVENANCE_INCOMPLETE", "EVIDENCE_TOPIC_MISMATCH",
                 "FORMULA_NOT_FOUND",
                 "FORMULA_MISMATCH", "UNSUPPORTED_CLAIM", "CONTRADICTED_CLAIM",
                 "CALCULATION_ERROR", "DIMENSION_ERROR", "UNIT_UNSUPPORTED", "AMBIGUOUS"}
        if any(r.split(":")[0] in fatal for r in reasons):
            status = "INVALID"
        elif reasons:
            status = "NEEDS_REVIEW"
        else:
            status = "VALID"
        q.validation.status = status
        q.validation.reasons = sorted(set(reasons))
        q.validation.evidence_score = ev_score
        q.validation.checks = checks
        return q
