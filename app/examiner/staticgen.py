"""Generadores deterministicos (sin LLM): V/F, MCQ de formula, numericos,
respuesta corta y encadenados. Reproducibles por seed. Todo lo afirmado viene
de la evidencia; lo falso se construye por sustitucion verificada como no
soportada (con la afirmacion verdadera citada como justificacion).
"""
from __future__ import annotations

import random
import re
import sqlite3

from app.reasoning.calculator import check_dimensions

from . import numerical as NUM


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+", text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 40]


def _key_terms(sentence: str, minimum: int = 5) -> list[str]:
    toks = re.findall(r"[A-Za-zÀ-ÿ][a-zà-ÿ]{%d,}" % (minimum - 1), sentence)
    seen, out = set(), []
    for t in toks:
        low = t.lower()
        if low not in seen and low not in {"aquest", "aquesta", "entre", "sobre", "mitjançant"}:
            seen.add(low)
            out.append(t)
    return out


def gen_true_false(kb_path: str, topic: int, section: str, seed: int = 0) -> dict | None:
    """V/F desde frases de definicion/explicacion. FALSE por sustitucion de
    concepto verificada como no soportada en el chunk origen."""
    rng = random.Random(seed)
    con = sqlite3.connect("file:%s?mode=ro" % kb_path, uri=True)
    try:
        chunks = con.execute(
            "SELECT c.id, c.text, c.source_path, s.h2 FROM chunks c "
            "LEFT JOIN sections s ON s.id=c.section_id "
            "WHERE c.topic=? AND c.source_type='html' AND c.content_type IN "
            "('definition','explanation') AND length(c.text) > 200 "
            "AND (? = '' OR s.h2 = ?) ORDER BY c.id", (topic, section, section)).fetchall()
        concepts = [r[0] for r in con.execute(
            "SELECT DISTINCT term_ca FROM concepts WHERE topic != ? ORDER BY term_ca",
            (topic,)).fetchall()]
    finally:
        con.close()
    cands = []
    for cid, text, spath, h2 in chunks:
        for sent in _sentences(text)[:3]:
            terms = _key_terms(sent)
            if len(terms) >= 2:
                cands.append((cid, sent, terms, spath, h2 or ""))
    if not cands:
        return None
    cid, sent, terms, spath, h2 = cands[seed % len(cands)]
    if rng.random() < 0.5:
        return {"statement": sent, "truth": True, "evidence": cid,
                "text": next(t for i, t, p, h in chunks if i == cid),
                "explanation": "Afirmació literal del material (%s)." % spath,
                "source_path": spath, "section": h2}
    for term in terms:
        for other in concepts:
            if other.lower() not in sent.lower() and len(other) > 4:
                false_sent = sent.replace(term, other, 1)
                if false_sent != sent and other.lower() not in sent.lower():
                    return {"statement": false_sent, "truth": False,
                            "evidence": cid,
                            "text": next(t for i, t, p, h in chunks if i == cid),
                            "explanation": "Fals: el material diu «%s»." % sent[:220],
                            "source_path": spath, "section": h2,
                            "swapped": (term, other)}
    return None


def gen_formula_mcq(rec: dict, seed: int = 0) -> dict:
    """MCQ: enunciado desde la seccion + canonica + 3 distractores validados."""
    from .distractors import build_distractors
    section = (rec["section_h2"] or "").strip()
    stem = ("Quina expressió permet calcular %s?" % section if section
            else "Quina expressió és la canònica (%s)?" % rec["equation_id"])
    distractors = build_distractors("", rec["equation_id"], rec["expression"], seed=seed, n=3)
    options = [{"text": rec["expression"], "correct": True, "distractor_reason": "",
                "formula_id": rec["equation_id"]}]
    options += [{"text": d["text"], "correct": False,
                 "distractor_reason": d["distractor_reason"], "formula_id": None}
                for d in distractors]
    rng = random.Random(seed)
    rng.shuffle(options)
    return {"stem": stem, "options": options,
            "correct_answer": rec["expression"], "solution_steps": [
                "Localitzar la secció «%s»." % section,
                "Identificar la fórmula canònica %s." % rec["equation_id"],
                "Descartar variants amb signe/factor/símbols alterats."]}


def gen_numerical(rec: dict, seed: int = 0) -> dict | None:
    """Numerico: formula -> python -> valores seed -> solve verificado."""
    try:
        py_expr, mapping = NUM.to_python(rec["expression"])
    except ValueError:
        return None
    if not re.search(r"[-+*/%()]|sqrt|log|ln|exp|sin|cos", py_expr):
        return None  # sin computo (simbolo solo): no es ejercicio (§18)
    symbols = list(mapping)
    if not symbols:
        return None
    values = NUM.generate_values(symbols, seed, {})
    py_vals = {mapping[s]: v["value"] for s, v in values.items()}
    ok, msg = NUM.check_denominators(py_expr, py_vals)
    if not ok:
        # Reintento determinista con otra semilla derivada (dominio valido).
        values = NUM.generate_values(symbols, seed + 7919, {})
        py_vals = {mapping[s]: v["value"] for s, v in values.items()}
        ok, msg = NUM.check_denominators(py_expr, py_vals)
        if not ok:
            return None
    try:
        result = NUM.solve(py_expr, py_vals)
    except ValueError:
        return None
    given = ", ".join("%s = %s" % (s, v["value"]) for s, v in values.items())
    target = re.split(r"=", rec["expression"].strip().strip("$"), maxsplit=1)[0].strip() or "resultat"
    return {"given": given, "py_expr": py_expr, "mapping": mapping,
            "values": values, "result": result, "target": target,
            "steps": ["Dades: %s." % given,
                      "Fórmula canònica %s." % rec["equation_id"],
                      "Substitució en %s." % py_expr,
                      "Càlcul determinista = %s." % result]}


def gen_short_answer(chunk: dict, seed: int = 0) -> dict | None:
    """Respuesta corta: 'Defineix X' desde bloque de definicion."""
    sents = _sentences(chunk["text"])
    terms = _key_terms(" ".join(sents[:2]))
    if not sents or not terms:
        return None
    term = terms[seed % len(terms)]
    return {"prompt": "Defineix «%s» segons el material." % term,
            "expected_answer": sents[0][:600],
            "required_concepts": terms[:5],
            "evidence": chunk["chunk_id"]}


def find_chains(kb_path: str, topic: int, seed: int = 0, limit: int = 40) -> list[dict]:
    """Cadenas F1->F2 ordenadas deterministicamente (hasta `limit`).

    find_chain() devuelve la primera (compatibilidad).
    """
    from app.retrieval.formula import symbols_of
    con = sqlite3.connect("file:%s?mode=ro" % kb_path, uri=True)
    try:
        rows = con.execute(
            "SELECT equation_id, expression, section_h2, source_path FROM formulas "
            "WHERE topic=? AND expression LIKE '%=%' ORDER BY equation_id",
            (topic,)).fetchall()
    finally:
        con.close()
    parsed = []
    for eid, expr, h2, spath in rows:
        core = expr.strip()[1:-1] if expr.strip().startswith("$") else expr
        if core.count("=") != 1:
            continue
        lhs, rhs = (p.strip() for p in core.split("=", 1))
        if re.fullmatch(r"[A-Za-z](?:_\{[^}]*\}|_[A-Za-z0-9])?", lhs):
            rsyms = {s for s in symbols_of("$" + rhs + "$") if not s.startswith("base:")}
            if rsyms:
                parsed.append((eid, lhs, rsyms, expr, h2, spath))
    cands = []
    for i, (e1, out1, _, _, _, _) in enumerate(parsed):
        for j, (e2, _, rsyms2, _, _, _) in enumerate(parsed):
            if i != j and out1 in rsyms2:
                cands.append((e1, e2))
    cands = sorted(set(cands))
    chains = [{"first": a, "second": b} for a, b in cands[:limit]]
    if seed:
        rng = random.Random(seed)
        rng.shuffle(chains)
    return chains


def find_chain(kb_path: str, topic: int, seed: int = 0) -> dict | None:
    chains = find_chains(kb_path, topic, seed=0, limit=8)
    if not chains:
        return None
    if seed:
        rng = random.Random(seed)
        return rng.choice(chains)
    return chains[0]
