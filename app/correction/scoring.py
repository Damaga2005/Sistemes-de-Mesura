"""Scoring determinista (§13, §19): la nota sale de rubric+criterios+pesos.

Nunca de `LLM dice 7`. Agregacion reproducible; tolerancias desde la rubrica.
"""
from __future__ import annotations

from .models import CriterionResult


def aggregate(results: list[CriterionResult], max_score: float = 10.0) -> tuple[float, str]:
    """Nota reproducible + estado. CORRECT exige: sin errores implicitos aqui
    (los aporta el caller), todo required a 1.0 y resto >= 0.5 (0.5 = sin
    contraevidencia, p. ej. variables no explicitadas pero no contradichas).
    Asi una respuesta perfecta determinista SI puede ser CORRECT (9.0/10)."""
    total_w = sum(r.max_score for r in results) or 1.0
    score = sum(r.score * r.max_score for r in results) / total_w * max_score
    score = round(score, 2)
    if all(r.score >= 0.999 for r in results if r.required) and \
            all(r.score >= 0.5 for r in results):
        status = "CORRECT"
    elif all(r.score <= 0.001 for r in results):
        status = "INCORRECT"
    else:
        status = "PARTIALLY_CORRECT"
    return score, status


def apply_tolerance(claimed: float, expected: float, atol: float = 1e-9,
                    rtol: float = 1e-6) -> bool:
    return abs(claimed - expected) <= atol + rtol * abs(expected)
