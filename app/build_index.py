"""Construccion del indice (lexical FTS5 + semantico TF-IDF). Idempotente:
mismas entradas -> mismos hashes de contenido (el timestamp no forma parte).
Uso: python3 -m app.build_index
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config as fase1_config  # noqa: E402
from app.retrieval import config as cfg  # noqa: E402
from app.retrieval.lexical import LexicalIndex  # noqa: E402
from app.retrieval.normalize_query import STOPWORDS  # noqa: E402
from app.retrieval.semantic import TfidfIndex  # noqa: E402

from app import paths as sm_paths  # noqa: E402

WORKSPACE = sm_paths.package_dir()
KB = WORKSPACE / "data" / "processed" / "knowledge.sqlite"
INDEX_DIR = WORKSPACE / "data" / "index"


def main() -> None:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect("file:%s?mode=ro" % KB, uri=True)
    try:
        rows = con.execute(
            "SELECT c.id, c.text, d.h1, s.h2 FROM chunks c "
            "LEFT JOIN documents d ON d.id=c.doc_id LEFT JOIN sections s ON s.id=c.section_id"
            " ORDER BY c.id").fetchall()
    finally:
        con.close()
    lex = LexicalIndex(INDEX_DIR / "lexical" / "fts.sqlite")
    lex_stats = lex.build([{"chunk_id": r[0], "text": r[1], "h1": r[2] or "", "h2": r[3] or ""}
                           for r in rows])
    sem = TfidfIndex(stopwords=STOPWORDS)
    sem_stats = sem.build([(r[0], "%s %s %s" % (r[2] or "", r[3] or "", r[1])) for r in rows])
    sem.save(INDEX_DIR / "semantic")
    content = hashlib.sha256(
        (lex_stats["content_hash"] + sem_stats["content_hash"]).encode()).hexdigest()
    manifest = {
        "index_version": cfg.INDEX_VERSION,
        "retrieval_version": cfg.RETRIEVAL_VERSION,
        "kb_chunks": lex_stats["chunks"],
        "lexical": {"engine": "sqlite-fts5-unicode61", "content_hash": lex_stats["content_hash"]},
        "semantic": {"model": "tfidf-local-1.0", "dimension": len(sem.vocab),
                     "terms": sem_stats["terms"], "content_hash": sem_stats["content_hash"]},
        "content_hash": content,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kb_pipeline": fase1_config.PIPELINE_VERSION,
    }
    (INDEX_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                                             encoding="utf-8")
    print("chunks=%d terms=%d content=%s" % (lex_stats["chunks"], sem_stats["terms"], content[:12]))


if __name__ == "__main__":
    main()
