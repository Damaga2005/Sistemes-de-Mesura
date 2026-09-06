"""Evidencia para blueprints: siempre KB -> retrieval -> pack. Nunca al reves.

Sin acceso a la evaluation DB de V/F (aislamiento §42-43): este modulo solo
conoce knowledge.sqlite + indice. Un test dedicado lo demuestra.
"""
from __future__ import annotations

import sqlite3

from app.retrieval.models import RetrievalFilters


class EvidenceError(Exception):
    pass


def formula_record(kb_path: str, formula_id: str) -> dict:
    con = sqlite3.connect("file:%s?mode=ro" % kb_path, uri=True)
    try:
        row = con.execute(
            "SELECT f.equation_id, f.expression, f.topic, f.source_path, f.section_h2,"
            " f.variables_json, d.h1, d.title FROM formulas f "
            "LEFT JOIN documents d ON d.source_id = "
            "(SELECT id FROM sources WHERE path = f.source_path) "
            "WHERE f.equation_id=?", (formula_id,)).fetchone()
    finally:
        con.close()
    if not row:
        raise EvidenceError("FORMULA_NOT_FOUND: %s" % formula_id)
    import json as _j
    return {"equation_id": row[0], "expression": row[1], "topic": row[2],
            "source_path": row[3], "section_h2": row[4],
            "variables": _j.loads(row[5] or "[]"),
            "h1": row[6] or "", "doc_title": row[7] or ""}


def evidence_for_blueprint(retriever, kb_path: str, query: str, topic: int,
                           top_k: int = 10):
    """Pack de evidencia con filtro de topic: el examiner genera por tema."""
    from app.retrieval.models import RetrievalFilters
    pack = retriever.retrieve_evidence(
        query, filters=RetrievalFilters(topic=topic), top_k=top_k)
    if pack.abstain or not pack.results:
        raise EvidenceError("NO_EVIDENCE: %s" % query)
    return pack


def chunks_mentioning(kb_path: str, topic: int, terms: list[str], limit: int = 5) -> list[dict]:
    """Chunks de teoria del topic que mencionan todos los terminos (para V/F)."""
    con = sqlite3.connect("file:%s?mode=ro" % kb_path, uri=True)
    try:
        clauses = " AND ".join(["c.text LIKE ?"] * len(terms))
        rows = con.execute(
            "SELECT c.id, c.text, c.source_path, s.h2 FROM chunks c "
            "LEFT JOIN sections s ON s.id=c.section_id "
            "WHERE c.topic=? AND c.source_type='html' AND " + clauses + " LIMIT ?",
            (topic, *["%" + t + "%" for t in terms], limit)).fetchall()
        return [{"chunk_id": r[0], "text": r[1], "source_path": r[2], "section": r[3] or ""}
                for r in rows]
    finally:
        con.close()
