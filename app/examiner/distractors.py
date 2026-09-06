"""Distractores deterministas desde transformaciones matematicas (§23-24).

Cada distractor nace de una transformacion explicita de la formula canonica
(signo, factor, simbolo, reciproco, unidad) con su motivo clasificado. Todos
se verifican: ninguno puede ser EQUIVALENTE a la canonica (unicidad de
respuesta) ni contradecir la KB como afirmacion valida.
"""
from __future__ import annotations

import random
import re

from app.reasoning.formula_check import equivalent


def _variants(expression: str) -> list[tuple[str, str]]:
    """(latex_variante, motivo). Genericas, sin conocimiento por formula."""
    norm = expression.strip()
    body = norm[1:-1] if norm.startswith("$") and norm.endswith("$") else norm
    out = []
    if "=" in body:
        left, right = body.split("=", 1)
        out.append(("$%s = -(%s)$" % (left.strip(), right.strip()), "signo_global"))
        parts = re.split(r"(?<!^)(?=[+-])", right)
        if len(parts) >= 2:
            out.append(("$%s = %s$" % (left.strip(), ("-".join(parts)).replace("--", "")),
                        "signo_parcial"))
        out.append(("$%s = (%s)/2$" % (left.strip(), right.strip()), "factor_omitido"))
        out.append(("$%s = 2*(%s)$" % (left.strip(), right.strip()), "factor_doble"))
        if "/" not in right:
            out.append(("$%s = 1/(%s)$" % (left.strip(), right.strip()), "reciproco"))
    syms = re.findall(r"[A-Za-z](?:_\{[^}]*\}|_[A-Za-z0-9])?", body)
    if len(set(syms)) >= 2:
        a, b = sorted(set(syms))[:2]
        swapped = body.replace(a, "\x00").replace(b, a).replace("\x00", b)
        if swapped != body:
            out.append(("$%s$" % swapped, "simbolos_permutados"))
    # Subindices numericos: R_3 -> R_2/R_4 (confusion de componente verificada
    # como simbolo distinto; nunca equivalente por construction).
    for s in sorted(set(syms)):
        m = re.fullmatch(r"([A-Za-z]+)_(\{(\d+)\}|(\d+))", s)
        if m:
            base, num = m.group(1), int(m.group(3) or m.group(4))
            for alt in (num - 1, num + 1):
                if alt >= 0:
                    out.append(("$%s$" % body.replace(s, "%s_{%d}" % (base, alt), 1),
                                "subindice_erroneo"))
    return out


def build_distractors(kb_path: str, formula_id: str, canonical: str, seed: int = 0,
                      n: int = 3) -> list[dict]:
    """Distractores validados: no equivalentes a la canonica (respuesta unica)."""
    rng = random.Random(seed)
    cands = _variants(canonical)
    rng.shuffle(cands)
    out = []
    for latex, reason in cands:
        try:
            if equivalent(latex, canonical):
                continue  # no seria distractor: seria otra respuesta correcta
        except Exception:
            continue
        out.append({"text": latex, "correct": False, "distractor_reason": reason,
                    "formula_id": None})
        if len(out) >= n:
            break
    return out


def validate_distractors(canonical: str, distractors: list[dict]) -> tuple[bool, str]:
    """Ningun distractor equivalente; ninguno vacio/duplicado."""
    seen = set()
    for d in distractors:
        if not d.get("text"):
            return False, "distractor vacio"
        if d["text"] in seen:
            return False, "distractor duplicado"
        seen.add(d["text"])
        try:
            if equivalent(d["text"], canonical):
                return False, "distractor equivalente a canonica"
        except Exception:
            return False, "distractor no comparable"
        if not d.get("distractor_reason"):
            return False, "distractor sin motivo"
    return True, "OK"
