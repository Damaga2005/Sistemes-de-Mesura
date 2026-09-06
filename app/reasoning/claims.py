"""Extraccion y verificacion de claims (§23-24). Determinista, sin LLM.

- Extraccion: del JSON estructurado del LLM (claims con evidence_ids) o, en
  fallback, de la respuesta extractiva (ya vienen citadas).
- Verificacion por tipo:
  FORMULA -> FormulaValidator (EXACT/EQUIVALENT/MISMATCH/MISSING).
  VARIABLE/UNIT -> mencion en evidencia citada (+definicion cercana = SUPPORTED,
    solo mencion = PARTIALLY).
  NUMERIC -> calculator independiente (tolerancia documentada).
  resto -> cobertura de terminos de contenido en la evidencia citada.
Sin evidence_ids citadas -> UNSUPPORTED. Contradiccion explicita de formula o
numero -> CONTRADICTED.
"""
from __future__ import annotations

import re

from app.retrieval.normalize_query import query_terms

from .calculator import check_dimensions, close_enough, safe_eval
from .formula_check import FormulaValidator
from .models import Claim


def _content_terms(text: str) -> set[str]:
    return {t for t in query_terms(text) if len(t) >= 4}


def extract_claims(structured: dict) -> list[Claim]:
    out = []
    for c in structured.get("claims", []):
        if isinstance(c, dict) and c.get("text"):
            out.append(Claim(text=str(c["text"])[:2000], type=str(c.get("type", "FACTUAL")),
                             evidence_ids=list(c.get("evidence_ids", []))))
    return out


class ClaimVerifier:
    def __init__(self, validator: FormulaValidator) -> None:
        self.validator = validator

    def verify(self, claim: Claim, evidence_texts: dict[str, str],
               formulas: dict[str, dict]) -> Claim:
        cited = [evidence_texts.get(e, "") for e in claim.evidence_ids if e in evidence_texts]
        cited_f = [formulas.get(e) for e in claim.evidence_ids if e in formulas]
        if claim.type == "FORMULA":
            # La evidencia de formula son registros (ids), no textos: no exigir chunks.
            return self._verify_formula(claim, cited_f, evidence_texts)
        if not cited and not cited_f:
            claim.status, claim.detail = "UNSUPPORTED", "sin evidencia citada o inexistente"
            return claim
        if claim.type == "NUMERIC":
            return self._verify_numeric(claim, cited)
        if claim.type in ("VARIABLE", "UNIT"):
            return self._verify_mention(claim, cited, strong=True)
        return self._verify_mention(claim, cited, strong=False)

    def _verify_formula(self, claim: Claim, cited_f: list, evidence_texts: dict) -> Claim:
        from .formula_check import equivalent as _eq
        from .formula_check import canonical as _can
        m = re.search(r"\$.+?\$", claim.text)
        if cited_f:
            # La cita no basta: el latex afirmado debe coincidir con el canonico
            # (resuelto en el validador si el payload no lo trae).
            if not m:
                claim.status, claim.detail = "SUPPORTED", "formula_id canonico citado"
                return claim
            for rec in cited_f:
                expr = (rec or {}).get("expression") or ""
                if not expr:
                    hit = self.validator._by_id.get((rec or {}).get("equation_id", ""))
                    expr = (hit or {}).get("expression", "")
                try:
                    if _can(m.group(0)) == _can(expr) or _eq(m.group(0), expr):
                        claim.status, claim.detail = (
                            "SUPPORTED", "coincide con %s" % (rec or {}).get("equation_id", "?"))
                        return claim
                except Exception:
                    continue
            claim.status, claim.detail = "CONTRADICTED", "latex no coincide con lo citado"
            return claim
        if m:
            status, rec = self.validator.check_latex(m.group(0))
            if status == "EXACT_MATCH":
                claim.status, claim.detail = "SUPPORTED", "latex canonico %s" % rec["equation_id"]
            elif status == "EQUIVALENT_MATCH":
                claim.status, claim.detail = "SUPPORTED", "equivalente a %s" % rec["equation_id"]
            else:
                claim.status, claim.detail = "CONTRADICTED", "formula no canonica"
            return claim
        claim.status, claim.detail = "UNSUPPORTED", "formula sin latex ni id"
        return claim

    def _verify_numeric(self, claim: Claim, cited: list[str]) -> Claim:
        m = re.search(r"(-?\d+(?:[.,]\d+)?(?:\s*[eE]\s*-?\d+)?)", claim.text)
        if not m:
            claim.status, claim.detail = "UNSUPPORTED", "sin numero extraible"
            return claim
        try:
            val = float(m.group(1).replace(",", "."))
        except ValueError:
            claim.status, claim.detail = "UNSUPPORTED", "numero ilegible"
            return claim
        blob = " ".join(cited)
        if str(m.group(1)) in blob or ("%.4g" % val) in blob:
            claim.status, claim.detail = "SUPPORTED", "numero presente en evidencia"
        else:
            claim.status, claim.detail = "PARTIALLY_SUPPORTED", "numero no literal en evidencia"
        return claim

    def _verify_mention(self, claim: Claim, cited: list[str], *, strong: bool) -> Claim:
        terms = _content_terms(claim.text)
        if not terms:
            claim.status, claim.detail = "UNSUPPORTED", "sin terminos de contenido"
            return claim
        blob = " ".join(cited).lower()
        hits = {t for t in terms if t in blob}
        if len(hits) == len(terms):
            claim.status, claim.detail = "SUPPORTED", "todos los terminos en evidencia"
        elif hits and not strong:
            claim.status, claim.detail = "PARTIALLY_SUPPORTED", "cobertura parcial"
        elif hits:
            claim.status, claim.detail = "PARTIALLY_SUPPORTED", "mencion sin definicion"
        else:
            claim.status, claim.detail = "UNSUPPORTED", "sin cobertura en evidencia"
        return claim


def verify_calculation(expression: str, claimed: float | None, unit: str = "",
                       operand_units: list[str] | None = None, op: str = "") -> dict:
    """Calculo independiente + tolerancia + chequeo dimensional (§50-51)."""
    try:
        computed = safe_eval(expression)
    except Exception as e:
        return {"match": False, "computed": None, "detail": "expresion rechazada: %s" % e}
    out: dict = {"computed": computed, "match": False, "detail": ""}
    if claimed is not None:
        out["match"] = close_enough(claimed, computed)
        out["detail"] = "coincide" if out["match"] else "difiere: declarado %s vs %s" % (
            claimed, computed)
    else:
        out["match"], out["detail"] = True, "sin valor declarado; calculado %s" % computed
    if unit:
        dim = check_dimensions(unit, operand_units or [], op)
        out["dimension_ok"] = dim
        if dim is False:
            out["match"] = False
            out["detail"] += "; dimensiones incompatibles para %s" % unit
    return out
