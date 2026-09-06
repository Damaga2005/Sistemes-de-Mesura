"""Filtros academicos (§15): topic/section/source_type/content_type/formula_only.

Opcionales y transparentes: devuelven el conjunto de chunk_ids permitidos
o None si no hay ningun filtro activo.
"""
from __future__ import annotations

import sqlite3

from .models import RetrievalFilters


def apply_filters(kb_path: str, filters: RetrievalFilters | None) -> set[str] | None:
    if filters is None:
        return None
    clauses: list[str] = []
    params: list = []
    join_section = filters.section is not None
    if filters.topic is not None:
        clauses.append("c.topic = ?")
        params.append(filters.topic)
    if filters.source_type == "pdf":
        clauses.append("c.source_path LIKE '%Apunts%'")
    elif filters.source_type == "html":
        clauses.append("c.source_path NOT LIKE '%Apunts%'")
    if filters.content_type is not None:
        clauses.append("c.content_type = ?")
        params.append(filters.content_type)
    if filters.formula_only:
        clauses.append("c.formula_ids != '[]'")
    if join_section:
        clauses.append("s.h2 LIKE ?")
        params.append("%" + filters.section + "%")
    if not clauses:
        return None
    sql = "SELECT c.id FROM chunks c"
    if join_section:
        sql += " JOIN sections s ON s.id = c.section_id"
    sql += " WHERE " + " AND ".join(clauses)
    con = sqlite3.connect("file:%s?mode=ro" % kb_path, uri=True)
    try:
        return {r[0] for r in con.execute(sql, tuple(params)).fetchall()}
    finally:
        con.close()
