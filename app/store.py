"""Persistencia SQLite: knowledge.sqlite (teoria) y eval.sqlite (evaluacion). Separados.

Sin AUTOINCREMENT ni valores implicitos: todos los IDs son deterministas,
luego re-ejecutar sobre las mismas fuentes produce el mismo contenido.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .build import Chunk, Concept, Formula, Visual
from .config import COURSE, PIPELINE_VERSION
from .questions import EvalQuestion

KNOWLEDGE_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sources(
  id TEXT PRIMARY KEY, path TEXT NOT NULL, topic INTEGER NOT NULL,
  kind TEXT NOT NULL, suffix TEXT NOT NULL, bytes INTEGER NOT NULL,
  sha256 TEXT NOT NULL, title TEXT);
CREATE TABLE IF NOT EXISTS documents(
  id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id),
  topic INTEGER NOT NULL, title TEXT NOT NULL, h1 TEXT NOT NULL,
  doc_order INTEGER NOT NULL, kind TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sections(
  id TEXT PRIMARY KEY, doc_id TEXT NOT NULL REFERENCES documents(id),
  idx INTEGER NOT NULL, h2 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chunks(
  id TEXT PRIMARY KEY, doc_id TEXT NOT NULL REFERENCES documents(id),
  section_id TEXT REFERENCES sections(id), topic INTEGER NOT NULL,
  source_path TEXT NOT NULL, source_type TEXT NOT NULL,
  content_type TEXT NOT NULL, text TEXT NOT NULL,
  formula_ids TEXT NOT NULL, image_refs TEXT NOT NULL,
  parent_context TEXT NOT NULL, language TEXT NOT NULL,
  source_hash TEXT NOT NULL, dup_of TEXT REFERENCES chunks(id));
CREATE TABLE IF NOT EXISTS formulas(
  equation_id TEXT PRIMARY KEY, expression TEXT NOT NULL, encoding TEXT NOT NULL,
  raw TEXT NOT NULL, topic INTEGER NOT NULL, source_path TEXT NOT NULL,
  section_h2 TEXT NOT NULL, variables_json TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tables_t(
  id TEXT PRIMARY KEY, doc_id TEXT NOT NULL REFERENCES documents(id),
  section_id TEXT REFERENCES sections(id), topic INTEGER NOT NULL,
  caption TEXT, markdown TEXT NOT NULL, records_json TEXT NOT NULL,
  source_path TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS visuals(
  asset_id TEXT PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE, bytes_len INTEGER NOT NULL,
  topic INTEGER NOT NULL, source_kind TEXT NOT NULL, caption TEXT,
  occurrences_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS concepts(
  id INTEGER PRIMARY KEY, term_ca TEXT NOT NULL, kind TEXT NOT NULL,
  topic INTEGER NOT NULL, source_path TEXT NOT NULL, section_h2 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reconciliation(
  topic INTEGER PRIMARY KEY, html_words INTEGER NOT NULL, pdf_words INTEGER NOT NULL,
  shared INTEGER NOT NULL, jaccard REAL NOT NULL, coverage REAL NOT NULL, status TEXT NOT NULL);
"""

EVAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS questions(
  qid TEXT PRIMARY KEY, topic INTEGER NOT NULL, question TEXT NOT NULL,
  answer TEXT NOT NULL, justification TEXT NOT NULL,
  expected_source TEXT, origin TEXT NOT NULL);
"""


def write_knowledge(
    path: str | Path,
    manifest_rows: list[dict],
    chunks: list[Chunk],
    formulas: list[Formula],
    tables: list[dict],
    visuals: list[Visual],
    concepts: list[Concept],
    reconciliation: list[dict],
    doc_index: dict[str, dict],
    section_ids: dict[tuple[str, int], str],
) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if Path(path).exists():
        Path(path).unlink()
    con = sqlite3.connect(path)
    try:
        con.executescript(KNOWLEDGE_SCHEMA)
        from app.migrate import migrate as _migrate
        _migrate(con, "knowledge")
        con.execute("INSERT INTO meta(key,value) VALUES('pipeline_version',?)", (PIPELINE_VERSION,))
        con.execute("INSERT INTO meta(key,value) VALUES('course',?)", (COURSE,))
        for r in manifest_rows:
            con.execute(
                "INSERT INTO sources(id,path,topic,kind,suffix,bytes,sha256,title) VALUES(?,?,?,?,?,?,?,?)",
                (r["id"], r["path"], r["topic"], r["kind"], r["suffix"], r["bytes"], r["sha256"], r.get("title")),
            )
        for doc_id, d in doc_index.items():
            con.execute(
                "INSERT INTO documents(id,source_id,topic,title,h1,doc_order,kind) VALUES(?,?,?,?,?,?,?)",
                (doc_id, d["source_id"], d["topic"], d["title"], d["h1"], d["doc_order"], d["kind"]),
            )
        for (doc_id, idx), sid in section_ids.items():
            h2 = doc_index[doc_id]["sections"][idx]
            con.execute("INSERT INTO sections(id,doc_id,idx,h2) VALUES(?,?,?,?)", (sid, doc_id, idx, h2))
        for c in chunks:
            sec_idx = (c.parent_context or {}).get("section_index")
            sec_id = section_ids.get((c.doc, sec_idx)) if sec_idx is not None else None
            con.execute(
                "INSERT INTO chunks(id,doc_id,section_id,topic,source_path,source_type,content_type,"
                "text,formula_ids,image_refs,parent_context,language,source_hash,dup_of)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (c.id, c.doc, sec_id, c.topic, c.source_path, c.source_type, c.content_type, c.text,
                 json.dumps(c.formula_ids, ensure_ascii=False), json.dumps(c.image_refs, ensure_ascii=False),
                 json.dumps(c.parent_context, ensure_ascii=False), c.language, c.source_hash, c.dup_of),
            )
        for f in formulas:
            con.execute(
                "INSERT INTO formulas(equation_id,expression,encoding,raw,topic,source_path,section_h2,"
                "variables_json,status) VALUES(?,?,?,?,?,?,?,?,?)",
                (f.equation_id, f.expression, f.encoding, f.raw, f.topic, f.source_path, f.section_h2,
                 json.dumps(f.variables, ensure_ascii=False), f.status),
            )
        for t in tables:
            con.execute(
                "INSERT INTO tables_t(id,doc_id,section_id,topic,caption,markdown,records_json,source_path)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (t["id"], t["doc_id"], t.get("section_id"), t["topic"], t.get("caption"), t["markdown"],
                 json.dumps(t["records"], ensure_ascii=False), t["source_path"]),
            )
        for v in visuals:
            con.execute(
                "INSERT INTO visuals(asset_id,sha256,bytes_len,topic,source_kind,caption,"
                "occurrences_json) VALUES(?,?,?,?,?,?,?)",
                (v.asset_id, v.sha256, v.bytes_len, v.topic, v.source_kind, v.caption,
                 json.dumps(v.occurrences, ensure_ascii=False)),
            )
        for c in concepts:
            con.execute(
                "INSERT INTO concepts(term_ca,kind,topic,source_path,section_h2) VALUES(?,?,?,?,?)",
                (c.term_ca, c.kind, c.topic, c.source_path, c.section_h2),
            )
        for r in reconciliation:
            con.execute(
                "INSERT INTO reconciliation(topic,html_words,pdf_words,shared,jaccard,coverage,status)"
                " VALUES(?,?,?,?,?,?,?)",
                (r["topic"], r["html_words"], r["pdf_words"], r["shared"], r["jaccard"], r["coverage"], r["status"]),
            )
        con.commit()
    finally:
        con.close()


def write_eval(path: str | Path, questions: list[EvalQuestion]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if Path(path).exists():
        Path(path).unlink()
    con = sqlite3.connect(path)
    try:
        con.executescript(EVAL_SCHEMA)
        con.execute("INSERT INTO meta(key,value) VALUES('pipeline_version',?)", (PIPELINE_VERSION,))
        for q in questions:
            if q.answer not in ("V", "F"):
                raise ValueError("respuesta no V/F en %s" % q.qid)
            con.execute(
                "INSERT INTO questions(qid,topic,question,answer,justification,expected_source,origin)"
                " VALUES(?,?,?,?,?,?,?)",
                (q.qid, q.topic, q.question, q.answer, q.justification, q.expected_source, q.origin),
            )
        con.commit()
    finally:
        con.close()


def validate_knowledge(path: str | Path) -> list[str]:
    """Chequeos de integridad referencial y cobertura. Devuelve lista de errores (vacía = OK)."""
    errors: list[str] = []
    con = sqlite3.connect(path)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        for tbl in ["sources", "documents", "sections", "chunks", "formulas", "tables_t",
                    "visuals", "concepts", "reconciliation"]:
            n = con.execute("SELECT COUNT(*) FROM %s" % tbl).fetchone()[0]
            if n == 0:
                errors.append("tabla vacia: %s" % tbl)
        orphans = con.execute(
            "SELECT COUNT(*) FROM chunks WHERE section_id IS NOT NULL AND section_id NOT IN (SELECT id FROM sections)"
        ).fetchone()[0]
        if orphans:
            errors.append("chunks huerfanos: %d" % orphans)
        orphans_doc = con.execute(
            "SELECT COUNT(*) FROM chunks WHERE doc_id NOT IN (SELECT id FROM documents)"
        ).fetchone()[0]
        if orphans_doc:
            errors.append("chunks con documento inexistente: %d" % orphans_doc)
        nodocs = con.execute(
            "SELECT s.id FROM sources s LEFT JOIN documents d ON d.source_id=s.id "
            "WHERE d.id IS NULL AND s.kind IN ('teoria','pdf-apunts')"
        ).fetchall()
        if nodocs:
            errors.append("fuentes sin documento: %s" % [r[0] for r in nodocs][:5])
        dup_ids = con.execute(
            "SELECT id, COUNT(*) c FROM chunks GROUP BY id HAVING c>1"
        ).fetchall()
        if dup_ids:
            errors.append("chunk ids duplicados: %d" % len(dup_ids))
        banned = con.execute(
            "SELECT COUNT(*) FROM chunks WHERE text LIKE '%var BANC%' OR text LIKE '%COM EDITAR%'"
            " OR text LIKE '%Matplotlib%' OR text LIKE '%image/svg+xml%'"
        ).fetchone()[0]
        if banned:
            errors.append("boilerplate en chunks: %d" % banned)
    finally:
        con.close()
    return errors
