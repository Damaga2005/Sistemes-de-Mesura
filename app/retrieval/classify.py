"""Clasificacion determinista y conservadora del tipo de consulta (ca/es).
Sin LLM. Fallback GENERAL cuando no hay evidencia suficiente.
"""
from __future__ import annotations

import re

from .normalize_query import has_math

_PATTERNS: list[tuple[str, list[str]]] = [
    ("DEFINITION", [r"qu[eè]\s+[eé]s\b", r"defineix", r"\bdefine\b", r"definici[óo]",
                    r"en qu[eè] consisteix", r"que significa ser\b"]),
    ("FORMULA", [r"f[óo]rmula", r"com es calcula", r"c[óo]mo se calcula", r"\bcalcula\b",
                 r"expressi[óo]", r"expresi[oó]n", r"equaci[óo]", r"k\s*=\s*2", r"k\s*=\s*3"]),
    ("VARIABLE", [r"qu[eè] significa\b", r"que significa\b", r"significat de\b",
                  r"significado de\b", r"variable\b"]),
    ("UNIT", [r"unitat", r"unidad", r"unitats", r"unidades", r"\bdimensional\b"]),
    ("COMPARISON", [r"difer[eè]ncia", r"diferencia", r"versus\b", r"\bvs\b",
                    r"compara", r"distingeix", r"enfront de\b"]),
    ("VISUAL", [r"figura\b", r"esquema\b", r"gr[àa]fic", r"diagrama\b", r"imatge\b",
                r"imagen\b", r"circuit\b", r"corba\b", r"curva\b"]),
    ("EXAMPLE", [r"exemple\b", r"ejemplo\b", r"cas pr[àa]ctic", r"exercici resolt"]),
    ("PROCEDURE", [r"com es fa\b", r"c[óo]mo se hace", r"passos\b", r"pasos\b",
                   r"procediment\b", r"procedimiento\b", r"m[èe]tode\b", r"metodo\b"]),
    ("ERROR", [r"\berror\b", r"errada\b", r"fallada\b", r"fals\b", r"equivocaci"]),
    ("UNCERTAINTY", [r"incert", r"incertidumbre", r"gum\b", r"cobertura\b", r"tipus [ab]\b",
                     r"tipo [ab]\b", r"welch", r"student\b"]),
    ("TOPIC_SPECIFIC", [r"\btema\s*\d+", r"\bunitat\s*\d+", r"\bcap[íi]tol\s*\d+"]),
]

_TECHNICAL_TERM = re.compile(r"[a-zà-ÿ]{4,}", re.I)


def classify(query: str) -> str:
    low = query.lower()
    hits = [name for name, pats in _PATTERNS if any(re.search(p, low) for p in pats)]
    if "TOPIC_SPECIFIC" in hits and len(hits) > 1:
        hits.remove("TOPIC_SPECIFIC")
        return hits[0] + "+TOPIC"
    if hits:
        return hits[0]
    if has_math(query):
        return "FORMULA"
    if _TECHNICAL_TERM.search(query) and len(low.split()) <= 3:
        return "CONCEPT"
    return "GENERAL"
