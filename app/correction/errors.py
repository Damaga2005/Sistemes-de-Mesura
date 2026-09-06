"""Taxonomia de errores + severidad + causa raiz (§22-25).

ROOT_CAUSE vs DERIVED: un error de formula que arrastra calculo y resultado
cuenta como 1 raiz + 2 derivados (para mastery). Reglas documentadas, no
hardcode magico: tabla explícita abajo.
"""
from __future__ import annotations

from .models import DetectedError

# error -> (severidad por defecto, es_raiz_tipica)
SEVERITY_TABLE = {
    "FORMULA_ERROR": ("MAJOR", True),
    "WRONG_METHOD": ("MAJOR", True),
    "CONCEPT_ERROR": ("MAJOR", True),
    "VARIABLE_ERROR": ("MODERATE", True),
    "UNIT_ERROR": ("MODERATE", True),
    "DIMENSION_ERROR": ("MODERATE", True),
    "CALCULATION_ERROR": ("MODERATE", False),
    "ARITHMETIC_ERROR": ("MODERATE", False),
    "ALGEBRA_ERROR": ("MODERATE", False),
    "SIGN_ERROR": ("MODERATE", False),
    "ROUNDING_ERROR": ("MINOR", False),
    "REASONING_ERROR": ("MODERATE", True),
    "INTERPRETATION_ERROR": ("MODERATE", False),
    "INCOMPLETE_ANSWER": ("MODERATE", False),
    "AMBIGUOUS_ANSWER": ("MODERATE", False),
    "NO_JUSTIFICATION": ("MINOR", False),
    "WRONG_FINAL_RESULT": ("MODERATE", False),
}

# Un error raiz explica estos derivados (propagacion documentada).
PROPAGATION = {
    "FORMULA_ERROR": {"CALCULATION_ERROR", "ARITHMETIC_ERROR", "WRONG_FINAL_RESULT",
                      "UNIT_ERROR", "DIMENSION_ERROR"},
    "WRONG_METHOD": {"CALCULATION_ERROR", "WRONG_FINAL_RESULT", "REASONING_ERROR"},
    "VARIABLE_ERROR": {"CALCULATION_ERROR", "WRONG_FINAL_RESULT"},
    "CONCEPT_ERROR": {"REASONING_ERROR", "INTERPRETATION_ERROR", "WRONG_FINAL_RESULT"},
}


def classify(error_type: str, criterion: str = "", evidence: str = "") -> DetectedError:
    sev, root = SEVERITY_TABLE.get(error_type, ("MODERATE", False))
    return DetectedError(error_type=error_type, severity=sev, criterion=criterion,
                         evidence=evidence, root_cause=root)


def resolve_roots(errors: list[DetectedError]) -> list[DetectedError]:
    """Marca DERIVED_ERROR: si hay una raiz que lo explica, no es independiente."""
    roots = {e.error_type for e in errors if e.root_cause}
    for e in errors:
        if e.root_cause:
            continue
        for r, derived in PROPAGATION.items():
            if r in roots and e.error_type in derived:
                e.derived_from = r
                break
    return errors
