"""Ensamblado del EvidencePack (§29-30): todo lo que Fase 3 necesita, nada mas.

primary = top-3 no abstenido; supporting = resto del top-k. Trazabilidad total:
chunk -> section -> document -> source file -> source hash (+formula/image).
Las formulas se ordenan por relevancia a la query (cobertura exacta primero,
luego solape de seccion): el pack sirve a Fase 3 en orden util.
"""
from __future__ import annotations

import sqlite3

from app.retrieval.formula import FormulaIndex as _FormulaIndex
from app.retrieval.formula import symbols_of as _symbols_of
from app.retrieval.normalize_query import query_terms as _query_terms

_covers = _FormulaIndex.covers

from .models import EvidencePack

UNIT_TOKENS = ["V", "A", "Ω", "Hz", "kHz", "MHz", "mV", "mA", "dB", "dBm", "W", "J", "C", "F",
               "H", "T", "Pa", "N", "m", "s", "g", "kg", "mm", "%", "°", "º", "rad", "Ω·m"]


def _units_in(text: str) -> list[str]:
    found = []
    for u in UNIT_TOKENS:
        if u in ("m", "s", "g", "C", "F", "T", "A", "V", "H", "N"):
            import re as _re
            if _re.search(r"(?<![A-Za-zμ])" + _re.escape(u) + r"(?![A-Za-z])", text):
                found.append(u)
        elif u in text:
            found.append(u)
    return sorted(set(found))


def assemble(query: str, results: list[dict], expanded: dict[str, dict],
             kb_path: str, *, abstain: bool, abstention_reason: str | None,
             confidence: float, warnings: list[str]) -> EvidencePack:
    primary, supporting = [], []
    formulas: dict[str, dict] = {}
    visuals: dict[str, dict] = {}
    concepts: dict[str, dict] = {}
    sources: dict[str, dict] = {}
    for i, r in enumerate(results):
        entry = {"chunk_id": r["chunk_id"], "score": r["final_score"],
                 "source_path": r["source_path"], "source_hash": r["source_hash"],
                 "topic": r["topic"], "section": r["section"], "text": r["text"],
                 "formula_ids": r["formula_ids"], "image_refs": r["image_refs"],
                 "components": r.get("components", {})}
        (primary if i < 3 else supporting).append(entry)
        ctx = expanded.get(r["chunk_id"], {})
        for f in ctx.get("formulas", []):
            formulas[f["equation_id"]] = f
        for v in ctx.get("visuals", []):
            visuals[v["asset_id"]] = v
        sources[r["source_path"]] = {"source_path": r["source_path"],
                                     "source_hash": r["source_hash"], "topic": r["topic"]}
    con = sqlite3.connect("file:%s?mode=ro" % kb_path, uri=True)
    try:
        for term, kind, topic, spath, h2 in con.execute(
                "SELECT term_ca, kind, topic, source_path, section_h2 FROM concepts"):
            if term.lower() in query.lower() and len(term) > 6:
                concepts[term] = {"term_ca": term, "kind": kind, "topic": topic,
                                  "source_path": spath, "section_h2": h2}
                if len(concepts) >= 10:
                    break
    finally:
        con.close()
    # Orden de formulas por relevancia a la query (cobertura, solape, id).
    try:
        qsyms = _symbols_of(query)
        qw = {w for w in _query_terms(query) if len(w) >= 4}

        def _fkey(f: dict):
            cov = 1 if qsyms and _covers(qsyms, f.get("expression", "")) else 0
            sec = set(_query_terms(f.get("section_h2", "") or ""))
            shared = qw & sec
            ov = (len(shared) / len(qw)) if qw else 0.0
            return (-cov, -round(ov, 4), f.get("equation_id", ""))

        formulas_list = sorted(formulas.values(), key=_fkey)
    except Exception:
        formulas_list = list(formulas.values())
    units = [{"symbol": u} for u in _units_in(query)]
    w = [{"warning": x} for x in warnings]
    if abstention_reason:
        w.append({"abstention_reason": abstention_reason})
    return EvidencePack(query=query, results=[dict(r) for r in results],
                        primary_evidence=primary, supporting_evidence=supporting,
                        formulas=formulas_list, concepts=list(concepts.values()),
                        units=units, visuals=list(visuals.values()),
                        sources=list(sources.values()), confidence=confidence,
                        abstain=abstain, warnings=w)
