"""ContextExpander (§25-26): minimo necesario + suficiente.

Por resultado: seccion/doc padre, vecinos en la seccion (1+1, truncados),
formulas canonicas, visuales (referencia, no binario) y tabla estructurada.
"""
from __future__ import annotations

import json
import sqlite3

NEIGHBOR_CHARS = 400


class ContextExpander:
    def __init__(self, kb_path: str) -> None:
        self.kb_path = kb_path

    def expand(self, chunk_ids: list[str]) -> dict[str, dict]:
        con = sqlite3.connect("file:%s?mode=ro" % self.kb_path, uri=True)
        try:
            ctx: dict[str, dict] = {}
            for cid in chunk_ids:
                row = con.execute(
                    "SELECT c.id, c.doc_id, c.section_id, c.topic, c.text, c.formula_ids,"
                    " c.image_refs, c.parent_context, d.title, d.h1, s.h2"
                    " FROM chunks c LEFT JOIN documents d ON d.id=c.doc_id"
                    " LEFT JOIN sections s ON s.id=c.section_id WHERE c.id=?", (cid,)).fetchone()
                if not row:
                    continue
                (cid_, doc_id, sec_id, topic, text, fids, irefs, pctx,
                 title, h1, h2) = row
                formulas, visuals, table = [], [], None
                for fid in json.loads(fids or "[]"):
                    f = con.execute(
                        "SELECT equation_id, expression, topic, source_path, section_h2"
                        " FROM formulas WHERE equation_id=?", (fid,)).fetchone()
                    if f:
                        formulas.append({"equation_id": f[0], "expression": f[1],
                                         "topic": f[2], "source_path": f[3], "section_h2": f[4]})
                for ref in json.loads(irefs or "[]"):
                    v = con.execute(
                        "SELECT asset_id, caption, source_kind, occurrences_json FROM visuals"
                        " WHERE asset_id=?", (ref,)).fetchone()
                    if v:
                        occs = json.loads(v[3] or "[]")
                        visuals.append({"asset_id": v[0], "caption": v[1], "source_kind": v[2],
                                        "occurrences": len(occs),
                                        "first": occs[0] if occs else None})
                neighbors = []
                if sec_id:
                    sibs = con.execute(
                        "SELECT id, substr(text,1,?) FROM chunks WHERE section_id=? AND id!=? "
                        "ORDER BY id LIMIT 2", (NEIGHBOR_CHARS, sec_id, cid_)).fetchall()
                    neighbors = [{"chunk_id": s[0], "snippet": s[1]} for s in sibs]
                ctx[cid_] = {"document_title": title, "h1": h1, "section_h2": h2,
                             "parent_context": json.loads(pctx or "{}"),
                             "neighbors": neighbors, "formulas": formulas,
                             "visuals": visuals}
            return ctx
        finally:
            con.close()
