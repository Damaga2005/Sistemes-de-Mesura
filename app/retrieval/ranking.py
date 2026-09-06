"""Ranking con componentes explicados (sin magic scores, §62).

final = W_LEX*lex + W_SEM*sem + W_FORM*form + W_PHRASE*phrase + W_TOPIC*topic
        + W_SECTION*section + source_weight - dup_penalty  (+ topic_multiplier)

Cada componente en [0,1]; `components` expone el desglose para --debug.
"""
from __future__ import annotations

from . import config as cfg
from .normalize_query import query_terms

import re as _re
import unicodedata as _ud

_TOKEN = _re.compile(r"[a-zà-ÿ0-9_μΩσ%°º+\-]+", _re.I)


def _stems(tok: str) -> set[str]:
    """Variantes de matching catalan: sin acentos + plurales -s/-ns.

    Conservador: nunca une 'units' con 'unitats' (unit vs unitat), pero si
    'distribucions' con 'distribució'. Documentado como limitacion: no cubre
    alternancias vocálicas (corbes/corba).
    """
    t = _ud.normalize("NFD", tok.lower())
    t = "".join(c for c in t if _ud.category(c) != "Mn")
    out = {tok.lower(), t}
    if len(t) > 4 and t.endswith("s"):
        out.add(t[:-1])
        if len(t) > 6 and t.endswith("ns"):
            out.add(t[:-2])
    return out


def _tokset(text: str) -> set[str]:
    toks: set[str] = set()
    for w in _TOKEN.findall(text.lower()):
        toks |= _stems(w)
    return toks


def _stem_match(qstems: set[str], toks: set[str]) -> bool:
    """Igualdad de stems o prefijo comun >= 6 (puente flexivo ca: compensar/
    compensació, mesurar/mesura). El umbral 6 preserva fixes previos:
    'unit' vs 'unitat' (4) no colisionan."""
    if qstems & toks:
        return True
    for q in qstems:
        if len(q) < 6:
            continue
        for t in toks:
            if len(t) < 6:
                continue
            if q.startswith(t[:6]) and t.startswith(q[:6]):
                a, b = (q, t) if len(q) <= len(t) else (t, q)
                if b.startswith(a):
                    return True
    return False


def minmax_norm(scores: dict[str, float], *, invert: bool = False) -> dict[str, float]:
    if not scores:
        return {}
    vals = list(scores.values())
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return {k: 1.0 for k in scores}
    out = {}
    for k, v in scores.items():
        n = (v - lo) / (hi - lo)
        out[k] = 1.0 - n if invert else n
    return out


def phrase_score(query: str, text: str) -> float:
    """Cobertura de terminos con limite de palabra (nada de 'units'⊂'unitats').
    Bonus 1.0 si la frase exacta aparece."""
    terms = query_terms(query)
    if not terms:
        return 0.0
    low = text.lower()
    if len(terms) >= 2 and " ".join(terms) in low:
        return 1.0
    toks = set(_TOKEN.findall(low))
    hits = sum(1 for t in terms if t in toks)
    return round(hits / len(terms), 4)


def aligned_scores(variant_map: dict[str, list[str]], norm: str, text: str,
                   idf: dict[str, float]) -> tuple[float, float]:
    """Alineacion mejor-variante: cada termino original cuenta si ALGUNA variante
    (original, sinonimo, conversion morfologica, fuzzy) aparece en el texto.

    Devuelve (phrase, mass). El peso es el maximo IDF entre variantes conocidas;
    lo no resoluble pesa como max IDF (lo desconocido resta, nunca suma).
    """
    low = text.lower()
    if len(variant_map) >= 2 and norm in low:
        return 1.0, 1.0
    toks = _tokset(text)
    max_idf = max(idf.values()) if idf else 1.0
    hits, num, den = 0, 0.0, 0.0
    n = 0
    for t, vs in variant_map.items():
        if len(t) < 3:
            continue
        n += 1
        qstems: set[str] = set()
        for v in vs:
            qstems |= _stems(v)
        known_w = [idf[v] for v in vs if v in idf]
        w = max(known_w) if known_w else max_idf
        den += w
        if _stem_match(qstems, toks):
            hits += 1
            num += w if known_w else 0.0
    if not n:
        return 0.0, 0.0
    return round(hits / n, 4), round(num / den, 4) if den else 0.0


def evidence_mass(terms: list[str], text: str, idf: dict[str, float]) -> float:
    """Fraccion del peso IDF de la consulta presente en el texto (limite de palabra).
    Terminos ausentes del indice pesan como el maximo IDF: lo desconocido resta."""
    content = [t for t in terms if len(t) >= 3]
    if not content:
        return 0.0
    toks = set(_TOKEN.findall(text.lower()))
    max_idf = max(idf.values()) if idf else 1.0
    num = sum(idf.get(t, max_idf) for t in content if t in toks)
    den = sum(idf.get(t, max_idf) for t in content)
    return round(num / den, 4) if den else 0.0


def topic_component(query_topic: int | None, chunk_topic: int) -> float:
    if query_topic is None:
        return 0.5  # consulta global: neutral, sin penalizar otros temas
    return 1.0 if chunk_topic == query_topic else 0.0


def rank(candidates: dict[str, dict], variant_map: dict[str, list[str]], norm: str,
         idf: dict[str, float], query_topic: int | None,
         section_filter: str | None = None, query_type: str | None = None,
         symbol_signal: bool = False) -> dict[str, dict]:
    """candidates: cid -> {lex, sem, form, source, dup, section_match, chunk_topic,
    text, context}.

    phrase/mass por alineacion mejor-variante SOBRE EL CONTEXTO (h2/h1+cuerpo).
    Routing por tipo (§9): en FORMULA/VARIABLE la evidencia sin formulas se
    degrada (x0.55) SOLO si hay symbol_signal; en DEFINITION/VARIABLE/CONCEPT
    los bloques definitorios reciben prior.
    """
    lex_n = minmax_norm({c: v["lex"] for c, v in candidates.items() if v["lex"] is not None},
                        invert=True)
    sem_n = minmax_norm({c: v["sem"] for c, v in candidates.items() if v["sem"] is not None})
    form_n = minmax_norm({c: v["form"] for c, v in candidates.items() if v["form"] is not None})
    out: dict[str, dict] = {}
    for cid, v in candidates.items():
        lex = lex_n.get(cid, 0.0)
        sem = sem_n.get(cid, 0.0)
        form = form_n.get(cid, 0.0)
        phrase, mass = aligned_scores(variant_map, norm, v.get("context", v.get("text", "")),
                                      idf)
        topic = topic_component(query_topic, v["chunk_topic"])
        section = 1.0 if (section_filter is None or v.get("section_match")) else 0.5
        source = cfg.W_SOURCE_HTML if v["source"] == "html" else cfg.W_SOURCE_PDF
        dup = cfg.DUP_PENALTY if v.get("dup") else 0.0
        final = (cfg.W_LEXICAL * lex + cfg.W_SEMANTIC * sem + cfg.W_FORMULA * form
                 + cfg.W_PHRASE * phrase + cfg.W_TOPIC * topic + cfg.W_SECTION * section
                 + source - dup)
        sec_exp = cfg.W_SEC_EXPANSION if v.get("sec_expansion") else 0.0
        look_cov = cfg.W_LOOKUP_COVER if v.get("lookup_cover", 0.0) >= 0.7 else 0.0
        final += sec_exp + look_cov
        if query_type in ("DEFINITION", "VARIABLE", "CONCEPT") and v.get("content_type") in (
                "definition", "concept"):
            final += cfg.CONTENT_PRIOR
        if query_type == "UNIT" and v.get("content_type") == "table":
            final += cfg.TABLE_UNIT_PRIOR
        if query_topic is not None and v["chunk_topic"] != query_topic:
            final *= 0.6  # §16: tema mencionado -> otros temas penalizados (documentado)
        routed = False
        if (query_type in ("FORMULA", "VARIABLE") and symbol_signal and not v.get("form")
                and not v.get("lookup_cover") and phrase < 0.6):
            final *= 0.55
            routed = True
        out[cid] = {"final": round(final, 4), "mass": mass,
                    "components": {"lexical": round(lex, 4), "semantic": round(sem, 4),
                                   "formula": round(form, 4), "phrase": round(phrase, 4),
                                   "topic": topic, "section": section,
                                   "source": round(source, 4), "dup_penalty": dup,
                                   "sec_expansion": sec_exp, "lookup_cover": look_cov,
                                   "formula_routed": routed}}
    return out
