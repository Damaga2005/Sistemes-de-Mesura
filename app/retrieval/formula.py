"""FormulaRetriever: las formulas son conocimiento de primera clase (§12-13)."""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from .normalize_query import STOPWORDS, query_terms

SYMBOL_RE = re.compile(
    r"\\[a-zA-Z]+|[α-ωΑ-Ω]|μ|σ|Ω|[A-Za-z]+(?:_\{[^}]*\}|_[A-Za-z0-9])?(?:\^\{[^}]*\}|\^[A-Za-z0-9])?"
)
_WORDCHAR = re.compile(r"[A-Za-zÀ-ÿ']")

# Stopwords multi-letra jamas son simbolos ('de(sensor)' no es 'de'+sensor).
SYMBOL_STOPWORDS = {w for w in STOPWORDS if len(w) > 1}


def is_math_symbol(sym: str) -> bool:
    """Solo simbolos reales; las palabras funcionales/técnicas van por texto.

    Se conserva: 1 letra (U, k), 2 letras no-funcionales (uc, ac, dc),
    y todo lo con _ ^ \\ digito, griega o mayuscula (u_c, NTC, B_eq, 2qI).
    Se excluye: stopwords ('de','la') y palabras minusculas largas
    ('calcula','termistor' -> canal lexico).
    """
    core = sym[5:] if sym.startswith("base:") else sym
    if not core or core.lower() in SYMBOL_STOPWORDS:
        return False
    if core in ("d", "l"):
        # Residuo de elisiones catalanas ya partidas ('d un sensor') y de
        # posesivos; como variable aislada es despreciable (dx/dt se conservan).
        return False
    if len(core) <= 2:
        return True
    return bool(re.search(r"[_^\\0-9α-ωΑ-ΩμσΩ]", core) or core != core.lower())


@dataclass
class FormulaHit:
    equation_id: str
    score: float
    matched_symbols: list[str]


def normalize_latex(expr: str) -> str:
    t = expr.strip()
    if t.startswith("$") and t.endswith("$"):
        t = t[1:-1]
    t = re.sub(r"\s+", "", t)
    t = t.replace("\\,", "").replace("\\ ", "").replace("\\;", "")
    return t


def base_symbol(sym: str) -> str:
    """Forma base plegada: u_c -> uc, V_{out} -> vout? No: conserva caso, quita _^{}."""
    t = re.sub(r"[_{}^\\]", "", sym)
    return t


def base_key(sym: str) -> str:
    """Clave insensible a caso para multi-letra (IB==ib), sensible para 1 letra (U!=u)."""
    b = base_symbol(sym)
    return b.lower() if len(b) > 1 else b


def symbols_of(expr: str) -> set[str]:
    out = set()
    for m in SYMBOL_RE.finditer(expr):
        s = m.group(0)
        if s.startswith("\\") and len(s) > 3 and not any(c in s for c in "_^"):
            continue  # comandos de espaciado/estilo, no símbolos
        if len(s) == 1:
            # Letras sueltas solo si estan aisladas por ambos lados: la 'l' de
            # "l'arròs" o la 's' de "arròs" son fragmentos, no variables.
            prev = expr[m.start() - 1] if m.start() > 0 else " "
            nxt = expr[m.end()] if m.end() < len(expr) else " "
            if _WORDCHAR.match(prev) or _WORDCHAR.match(nxt):
                continue
        if not is_math_symbol(s):
            continue
        out.add(s)
        out.add("base:" + base_symbol(s))  # siempre: plegado uc<->u_c (conserva caso)
    return out


def query_symbols(query: str) -> set[str]:
    syms = set(symbols_of(query))
    extra = set()
    for s in list(syms):
        if not s.startswith("base:"):
            b = base_symbol(s)
            if b != s:
                extra.add("base:" + b)
    syms |= extra
    for tok in query_terms(query, remove_stopwords=False):
        if not re.fullmatch(r"[a-zA-Z]_[a-zA-Z0-9{}^\\]+|[a-zA-Z]", tok):
            continue
        if len(tok) == 1 and not _isolated(query, tok):
            continue  # articulo/fragmento ("l'arròs"), no variable
        syms.add(tok)
    return syms


def _isolated(query: str, tok: str) -> bool:
    for m in re.finditer(re.escape(tok), query):
        prev = query[m.start() - 1] if m.start() > 0 else " "
        nxt = query[m.end()] if m.end() < len(query) else " "
        if not (_WORDCHAR.match(prev) or _WORDCHAR.match(nxt)):
            return True
    return False


class FormulaIndex:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.universe: set[str] = set()

    def build(self, kb_path: str) -> dict:
        con = sqlite3.connect("file:%s?mode=ro" % kb_path, uri=True)
        try:
            self.rows = [
                {"equation_id": r[0], "expression": r[1], "norm": normalize_latex(r[1]),
                 "symbols": sorted(symbols_of(r[1])), "topic": r[2],
                 "source_path": r[3], "section_h2": r[4]}
                for r in con.execute(
                    "SELECT equation_id, expression, topic, source_path, section_h2 FROM formulas")
            ]
        finally:
            con.close()
        self.rows.sort(key=lambda r: r["equation_id"])
        for r in self.rows:
            self.universe.update(r["symbols"])
        return {"formulas": len(self.rows)}

    def math_universe(self) -> set[str]:
        """Subconjunto matematico del universo: excluye palabras de prosa
        (p. ej. de formulas unicode-sub-sup que contienen texto)."""
        out = set()
        for s in self.universe:
            core = s[5:] if s.startswith("base:") else s
            if len(core) <= 2 or re.search(r"[_^\\0-9α-ωΑ-ΩμσΩ]", core) or core != core.lower():
                out.add(s)
        return out

    def search(self, query: str, limit: int = 20) -> list[FormulaHit]:
        # Señal matematica (universo) + palabras de contenido (secciones).
        # Las funcionales ('de','la') se excluyen: eran polvo que disparaba
        # falsos 'strong' (caso 'teoria de cordes'). Las tecnicas ('incertesa',
        # 'termistor') se conservan: sostienen queries de palabras (RF01).
        qsyms = {s for s in query_symbols(query) if s.lower() not in SYMBOL_STOPWORDS}
        qnorm = normalize_latex(query)
        qwords = {w for w in query_terms(query) if w not in SYMBOL_STOPWORDS}
        out: list[FormulaHit] = []
        for r in self.rows:
            fsyms = set(r["symbols"])
            inter = qsyms & fsyms
            exact = {s for s in inter if not s.startswith("base:")}
            base_only = {s for s in inter if s.startswith("base:")}
            # Un base match solo cuenta si no hay ya match exacto del mismo símbolo.
            base_only = {s for s in base_only
                         if not any(s[5:] == base_symbol(e) and e in qsyms for e in exact)}
            score = 0.0
            if exact:
                score += len(exact) / max(len([s for s in qsyms if not s.startswith("base:")]), 1) * 0.7
                score += len(exact) / max(len([s for s in fsyms if not s.startswith("base:")]), 1) * 0.3
            if base_only:
                n_base_q = len([s for s in qsyms if s.startswith("base:")])
                score += 0.5 * len(base_only) / max(n_base_q, 1)
            if qnorm and len(qnorm) >= 3 and qnorm in r["norm"]:
                score += 0.5
            if qwords:
                sec = set(query_terms(r["section_h2"] or ""))
                if qwords & sec:
                    score += 0.15 * len(qwords & sec) / len(qwords)
            if score > 0:
                out.append(FormulaHit(r["equation_id"], round(score, 4),
                                      sorted(exact | base_only)))
        out.sort(key=lambda x: (-x.score, x.equation_id))
        return out[:limit]

    def lookup(self, symbols: set[str], qwords: set[str], limit: int = 20) -> list[dict]:
        """Cobertura exacta de simbolos (database-style, determinista).

        Devuelve formulas ordenadas por cobertura de los simbolos consultados
        y solape con la seccion. General: sin reglas por query.
        """
        qsyms = {s for s in symbols if not s.startswith("base:")}
        qbase = {s[5:] for s in symbols if s.startswith("base:")}
        out = []
        for r in self.rows:
            fsyms = set(r["symbols"])
            fbase = {s[5:] if s.startswith("base:") else s for s in fsyms}
            exact = {s for s in qsyms if s in fsyms}
            base = {b for b in qbase if b in fbase} - {base_symbol(e) for e in exact}
            denom = len(qsyms) or 1
            cov = (len(exact) + 0.6 * len(base)) / denom
            sec = set(query_terms(r["section_h2"] or ""))
            overlap = len(qwords & sec) / len(qwords) if qwords else 0.0
            if cov > 0:
                out.append({"equation_id": r["equation_id"], "coverage": round(cov, 4),
                            "overlap": round(overlap, 4),
                            "score": round(cov * 0.7 + overlap * 0.3, 4)})
        out.sort(key=lambda x: (-x["coverage"], -x["overlap"], x["equation_id"]))
        return out[:limit]

    @staticmethod
    def covers(symbols: set[str], expression: str) -> bool:
        """¿Cubre la formula TODOS los simbolos consultados? (union al pack).

        Plegado insensible a caso multi-letra (IB==ib) pero sensible en 1 letra
        (U!=u). General: sin listas por formula."""
        def keys(syms):
            out = set()
            for s in syms:
                core = s[5:] if s.startswith("base:") else s
                if core:
                    out.add(base_key(core))
            return out
        qkeys = keys(symbols)
        if not qkeys:
            return False
        return qkeys <= keys(symbols_of(expression))
