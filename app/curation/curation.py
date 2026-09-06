"""Curacion de metadata (§129-138): propuestas con evidencia, jamas invencion.

Fuentes (todas de la KB, ninguna del LLM):
- variables: patron definitorio 'on X és/denota' (-> CONFIRMED) mas patrones
  de precision media (-> PROPOSED) sobre el texto de la seccion; el simbolo
  debe aparecer en la formula. Sin evidencia -> UNKNOWN.
- units: glosario SI extraido de tables_t (Magnitud|Unitat|Simbol) -> CONFIRMED
  con evidencia de tabla; linkage formula<->unidad solo por mencion explicita.
- conditions: frases 'si/quan/sempre que/cal que...' vecinas -> NEEDS_REVIEW.
Overrides: capa derivada versionada con provenance completa (nunca tocan la
fuente ni sus hashes). Sin evidencia suficiente -> UNKNOWN/NEEDS_REVIEW.
"""
from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from pathlib import Path

VAR_PATTERNS = [
    # Alta precision -> CONFIRMED si el simbolo esta en la formula.
    # 'on X és/denota...' es definitorio en prosa academica catalana.
    # (El antiguo patron 'amb X ...' se elimino: 'amb i/a' son conjuncion/
    # preposicion en el 99% de casos, no variables. Ver FAILURE_ANALYSIS.)
    (re.compile(r"\bon\s+\$?([A-Za-z][\w]*)\$?\s+(?:és|es|denota|representa|indica)\s+([^.;]{3,160})"), "CONFIRMED"),
    (re.compile(r"\$?([A-Za-z][\w]*)\$?\s*:\s*([^.;]{3,160})"), "PROPOSED"),
    (re.compile(r"\$?([A-Za-z][\w]*)\$?\s+(?:és|es)\s+(?:la|el)\s+([^.;]{3,160})"), "PROPOSED"),
    (re.compile(r"(?:denota|representa|indica|designa)\s+(?:amb\s+)?\$?([A-Za-z][\w]*)\$?\s+([^.;]{3,160})"), "PROPOSED"),
]

COND_PATTERNS = [
    re.compile(r"\b(si|quan|quando|sempre que|cal que|només si|nomes si)\b[^.;]{10,200}", re.I),
]


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", text)).strip()


def propose_variables(kb_path: str) -> list[dict]:
    """{formula_id, field, current, proposed, evidence, status}."""
    con = sqlite3.connect("file:%s?mode=ro" % kb_path, uri=True)
    try:
        forms = con.execute("SELECT equation_id, expression, topic, source_path,"
                            " section_h2, variables_json FROM formulas").fetchall()
        chunks = con.execute("SELECT topic, text, s.h2 FROM chunks c LEFT JOIN sections s "
                             "ON s.id=c.section_id WHERE c.source_type='html'").fetchall()
    finally:
        con.close()
    by_topic: dict[int, str] = {}
    by_section: dict[tuple[int, str], str] = {}
    for topic, text, h2 in chunks:
        by_topic[topic] = by_topic.get(topic, "") + " " + text
        if h2:
            key = (topic, h2)
            by_section[key] = by_section.get(key, "") + " " + text
    import json as _j
    out = []
    for eid, expr, topic, spath, h2, vjson in forms:
        have = {v.get("sym") for v in _j.loads(vjson or "[]")}
        # Ventana: misma seccion primero (precision), resto del topic despues.
        context = (by_section.get((topic, h2 or ""), "") + " " + by_topic.get(topic, ""))[:60000]
        # Ventana: frases que mencionan la seccion o estan cerca de simbolos.
        for pat, tier in VAR_PATTERNS:
            for m in pat.finditer(context):
                sym, meaning = m.group(1), m.group(2).strip()
                if sym in have or len(sym) > 24:
                    continue
                # El simbolo debe aparecer en la formula (evidencia de rol).
                if sym not in expr and sym.lower() not in expr.lower():
                    continue
                out.append({"formula_id": eid, "field": "variables",
                            "current_value": sorted(have), "proposed_value": sym,
                            "meaning": meaning[:200], "evidence": m.group(0)[:300],
                            "status": tier, "review_reason": "pattern:" + pat.pattern[:40]})
                have.add(sym)
                if len([o for o in out if o["formula_id"] == eid]) >= 6:
                    break
    return out


def si_glossary(kb_path: str) -> list[dict]:
    """Glosario Magnitud->Unidad desde tables_t (CONFIRMED, evidencia tabla)."""
    con = sqlite3.connect("file:%s?mode=ro" % kb_path, uri=True)
    con = sqlite3.connect("file:%s?mode=ro" % kb_path, uri=True)
    try:
        rows = con.execute("SELECT id, markdown, source_path FROM tables_t").fetchall()
    finally:
        con.close()
    out = []
    for tid, md, spath in rows:
        for line in (md or "").splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 3 and cells[0] and cells[1] and "---" not in line \
                    and "Magnitud" not in cells[0]:
                out.append({"quantity": cells[0][:80], "unit": cells[1][:40],
                            "symbol": cells[2][:20], "evidence": tid,
                            "source_path": spath, "status": "CONFIRMED"})
    # Deduplicar por (quantity, unit).
    seen, dedup = set(), []
    for e in out:
        key = (e["quantity"].lower(), e["unit"].lower())
        if key not in seen:
            seen.add(key)
            dedup.append(e)
    return dedup


def propose_conditions(kb_path: str, limit_per_formula: int = 2) -> list[dict]:
    con = sqlite3.connect("file:%s?mode=ro" % kb_path, uri=True)
    try:
        forms = con.execute("SELECT equation_id, section_h2, topic FROM formulas").fetchall()
        secs = con.execute("SELECT s.h2, s.doc_id, c.text FROM sections s JOIN chunks c "
                           "ON c.section_id=s.id").fetchall()
    finally:
        con.close()
    by_h2: dict[str, str] = {}
    for h2, doc, text in secs:
        by_h2[h2 or ""] = by_h2.get(h2 or "", "") + " " + (text or "")
    out = []
    for eid, h2, topic in forms:
        context = by_h2.get(h2 or "", "")[:20000]
        n = 0
        for pat in COND_PATTERNS:
            for m in pat.finditer(context):
                out.append({"formula_id": eid, "field": "conditions",
                            "current_value": [], "proposed_value": _norm(m.group(0))[:220],
                            "evidence": (h2 or "")[:120], "status": "NEEDS_REVIEW",
                            "review_reason": "conditional-candidate"})
                n += 1
                if n >= limit_per_formula:
                    break
            if n >= limit_per_formula:
                break
    return out


OVERRIDE_SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata_overrides(
  override_id TEXT PRIMARY KEY, formula_id TEXT NOT NULL, field TEXT NOT NULL,
  old_value TEXT NOT NULL, new_value TEXT NOT NULL, evidence TEXT NOT NULL,
  reviewer TEXT NOT NULL, version INTEGER NOT NULL, created_at TEXT NOT NULL);
"""


def apply_override(db_path: str | Path, *, formula_id: str, field: str, old_value: str,
                   new_value: str, evidence: str, reviewer: str) -> dict:
    """Override con provenance; version incremental por (formula, field)."""
    import hashlib
    from datetime import datetime, timezone
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    try:
        con.executescript(OVERRIDE_SCHEMA)
        n = con.execute("SELECT COUNT(*) FROM metadata_overrides WHERE formula_id=? AND field=?",
                        (formula_id, field)).fetchone()[0]
        if not evidence or not reviewer:
            raise ValueError("override exige evidence y reviewer (source priority §132)")
        oid = "ovr-" + hashlib.sha256(
            ("%s|%s|%s|%d" % (formula_id, field, new_value, n + 1)).encode()).hexdigest()[:12]
        con.execute("INSERT INTO metadata_overrides(override_id,formula_id,field,old_value,"
                    "new_value,evidence,reviewer,version,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (oid, formula_id, field, old_value, new_value, evidence, reviewer, n + 1,
                     datetime.now(timezone.utc).isoformat(timespec="seconds")))
        con.commit()
        return {"override_id": oid, "version": n + 1}
    finally:
        con.close()


def _norm_q(text: str) -> str:
    t = unicodedata.normalize("NFC", (text or "").lower())
    return " ".join(t.split())


def unit_for(kb_path: str, quantity: str) -> dict | None:
    """Unidad canonica para una magnitud (glosario SI). None si no consta."""
    want = _norm_q(quantity)
    for e in si_glossary(kb_path):
        if _norm_q(e["quantity"]) == want or want in _norm_q(e["quantity"]):
            return {"unit": e["unit"], "symbol": e["symbol"],
                    "evidence": e["evidence"], "status": "CONFIRMED"}
    return None


def variable_status(kb_path: str, formula_id: str, symbol: str,
                    metadata_dir: str | Path | None = None) -> dict:
    """Estado de una variable: CONFIRMED (KB o curacion confirmada) /
    PROPOSED (curacion) / UNKNOWN. Jamas inventa (§33, §129)."""
    con = sqlite3.connect("file:%s?mode=ro" % kb_path, uri=True)
    try:
        row = con.execute("SELECT variables_json, expression FROM formulas "
                          "WHERE equation_id=?", (formula_id,)).fetchone()
    finally:
        con.close()
    if not row:
        return {"status": "UNKNOWN", "reason": "formula inexistente"}
    import json as _j
    for v in _j.loads(row[0] or "[]"):
        if v.get("sym") == symbol:
            return {"status": "CONFIRMED", "meaning": v.get("meaning", ""),
                    "origin": "knowledge-base"}
    if metadata_dir:
        prop = Path(metadata_dir) / "variable_proposals.jsonl"
        if prop.is_file():
            for line in prop.read_text(encoding="utf-8").splitlines():
                try:
                    r = _j.loads(line)
                except ValueError:
                    continue
                if r.get("formula_id") == formula_id and r.get("proposed_value") == symbol:
                    return {"status": r.get("status", "PROPOSED"),
                            "meaning": r.get("meaning", ""),
                            "origin": "curation", "evidence": r.get("evidence", "")}
    if symbol in (row[1] or ""):
        return {"status": "UNKNOWN", "reason": "mencionada sin definicion localizada"}
    return {"status": "UNKNOWN", "reason": "no aparece en la formula"}
