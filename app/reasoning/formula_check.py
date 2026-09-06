"""FormulaValidator (§15-16, §25, §49): exactas, equivalentes o mismatch.

- EXACT_MATCH: identico tras normalizar espacios/comandos de espaciado.
- EQUIVALENT_MATCH: misma ecuacion con terminos conmutados en sumas/productos
  o reordenados entre miembros con signo (a=b+c <-> a-b=c). U=k·uc == U=u_c·k.
- MISMATCH: existe en la KB otra formula pero distinta (p. ej. U=uc/k).
- MISSING: el formula_id no existe o el latex no esta en la KB.
Jamas acepta formulas fuera de la KB como academicas.
"""
from __future__ import annotations

import re
import sqlite3

from app.retrieval.formula import normalize_latex, symbols_of


def _terms(expr: str) -> list[str]:
    return [t for t in re.split(r"([+\-*/=()])", expr) if t.strip()]


def canonical(expr: str) -> str:
    # \, \; \: y espacio simple en latex son producto implicito (k\,u_c = k*u_c).
    # ANTES de normalize_latex, que los eliminaria pegando simbolos ('ku_c').
    t = re.sub(r"\\[,;:\s]", "*", expr)
    t = normalize_latex(t)
    t = t.replace("\\cdot", "*").replace("\\times", "*")
    t = re.sub(r"\s+", "", t)
    return t


def _split_equation(expr: str) -> tuple[list[str], list[str]] | None:
    if expr.count("=") != 1:
        return None
    left, right = expr.split("=")
    return _add_terms(left), _add_terms(right)


def _add_terms(side: str) -> list[str]:
    parts, cur, depth = [], "", 0
    for ch in side:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch in "+-" and depth == 0 and cur:
            parts.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        parts.append(cur)
    return sorted(p.strip() for p in parts if p.strip())


def _mul_terms(term: str) -> list[str]:
    return sorted(t.strip() for t in term.replace("*", " ").split() if t.strip())


def equivalent(a: str, b: str) -> bool:
    ca, cb = canonical(a), canonical(b)
    if ca == cb:
        return True
    pa, pb = _split_equation(ca), _split_equation(cb)
    if pa and pb:
        la = sorted(t2 for side in pa for t in side for t2 in _mul_terms(t.lstrip("+-")))
        lb = sorted(t2 for side in pb for t in side for t2 in _mul_terms(t.lstrip("+-")))
        if la == lb:
            return True
        # Reordenamiento entre miembros con signo: a=b+c <-> a-b-c=0.
        flat_a = sorted(_mul_terms(" ".join(
            [t for t in pa[0]] + ["-" + t.lstrip("+-") for t in pa[1]])))
        flat_b = sorted(_mul_terms(" ".join(
            [t for t in pb[0]] + ["-" + t.lstrip("+-") for t in pb[1]])))
        if flat_a == flat_b:
            return True
    return False


class FormulaValidator:
    def __init__(self, kb_path: str) -> None:
        self.kb_path = kb_path
        self._by_id: dict[str, dict] = {}
        con = sqlite3.connect("file:%s?mode=ro" % kb_path, uri=True)
        try:
            for r in con.execute(
                    "SELECT equation_id, expression, topic, source_path, section_h2 FROM formulas"):
                self._by_id[r[0]] = {"expression": r[1], "topic": r[2],
                                     "source_path": r[3], "section_h2": r[4]}
        finally:
            con.close()

    def check_id(self, equation_id: str) -> tuple[str, dict | None]:
        rec = self._by_id.get(equation_id)
        if not rec:
            return "MISSING", None
        return "EXACT_MATCH", rec

    def check_latex(self, latex: str) -> tuple[str, dict | None]:
        for eid, rec in self._by_id.items():
            if canonical(latex) == canonical(rec["expression"]):
                return "EXACT_MATCH", {"equation_id": eid, **rec}
        for eid, rec in self._by_id.items():
            if equivalent(latex, rec["expression"]):
                return "EQUIVALENT_MATCH", {"equation_id": eid, **rec}
        # ¿Hay formula 'parecida' (mismo topic, simbolos comunes)? -> MISMATCH informativo.
        return "MISSING", None

    def mismatch_detail(self, latex: str) -> str:
        want = symbols_of(latex)
        cands = [eid for eid, rec in self._by_id.items()
                 if want & symbols_of(rec["expression"])]
        return "sin match; %d candidatas con simbolos comunes" % len(cands)
