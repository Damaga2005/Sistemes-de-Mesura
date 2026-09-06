"""Indice lexical FTS5 sobre la KB (base separada, nunca modifica knowledge.sqlite).

Expone busqueda por terminos, frase exacta y BM25 con pesos por columna
(texto=1, h1=3, h2=3): los headings mandan sobre el cuerpo.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .normalize_query import query_terms


@dataclass
class LexicalHit:
    chunk_id: str
    rank: float  # BM25 (más negativo = mejor en FTS5)
    phrase: bool


_MATH_PUNCT = re.compile(r"[{}\(\)\^\*=+,;:.!?/\\|<>~$\[\]]+")


def _fts_query(terms: list[str]) -> str:
    safe = []
    for t in terms:
        # La puntuacion matematica separa, no elimina: "V_{os}" -> "V" "os".
        for piece in _MATH_PUNCT.split(t.replace('"', "")):
            if piece and re.fullmatch(r"[A-Za-zÀ-ÿ0-9_μΩσ%°º+\-·'’]+", piece):
                safe.append('"%s"' % piece)
                # Recall morfologico: prefijo para terminos largos (compensar/
                # compensació). FTS5 lo soporta nativamente; el ranking decide.
                if len(piece) >= 7:
                    safe.append("%s*" % piece[:7])
    return " OR ".join(safe)


def _fts_phrase(terms: list[str]) -> str:
    safe = [t.replace('"', "") for t in terms if t]
    if len(safe) < 2:
        return ""
    return '"%s"' % " ".join(safe)


class LexicalIndex:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._con: sqlite3.Connection | None = None

    def build(self, chunks: list[dict]) -> dict:
        """chunks: [{chunk_id, text, h1, h2}]. Devuelve stats + content_hash."""
        if self.path.exists():
            self.path.unlink()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path)
        con.execute(
            "CREATE VIRTUAL TABLE fts USING fts5(chunk_id UNINDEXED, text, h1, h2, "
            "tokenize = 'unicode61 remove_diacritics 1')"
        )
        h = hashlib.sha256()
        n = 0
        for c in chunks:
            con.execute("INSERT INTO fts(chunk_id, text, h1, h2) VALUES(?,?,?,?)",
                        (c["chunk_id"], c["text"], c.get("h1", ""), c.get("h2", "")))
            h.update(c["chunk_id"].encode())
            h.update(b"\x00")
            n += 1
        con.commit()
        con.execute("INSERT INTO fts(fts) VALUES('optimize')")
        con.commit()
        con.close()
        return {"chunks": n, "content_hash": h.hexdigest()}

    def open(self) -> sqlite3.Connection:
        if self._con is None:
            self._con = sqlite3.connect("file:%s?mode=ro" % self.path, uri=True)
        return self._con

    def search(self, query: str, limit: int = 60) -> list[LexicalHit]:
        terms = query_terms(query)
        if not terms:
            return []
        con = self.open()
        out: dict[str, LexicalHit] = {}
        phrase = _fts_phrase(terms)
        if phrase:
            try:
                for cid, rank in con.execute(
                        "SELECT chunk_id, rank FROM fts WHERE fts MATCH ? "
                        "ORDER BY rank LIMIT ?", (phrase, limit)):
                    out[cid] = LexicalHit(cid, rank, True)
            except sqlite3.OperationalError:
                pass
        q = _fts_query(terms)
        if q:
            try:
                for cid, rank in con.execute(
                        "SELECT chunk_id, bm25(fts, 1.0, 3.0, 3.0) FROM fts "
                        "WHERE fts MATCH ? ORDER BY 2 LIMIT ?", (q, limit)):
                    if cid not in out:
                        out[cid] = LexicalHit(cid, rank, False)
            except sqlite3.OperationalError:
                pass
        return list(out.values())

    def manifest(self) -> dict:
        return {"engine": "sqlite-fts5-unicode61-remove-diacritics",
                "weights": {"text": 1.0, "h1": 3.0, "h2": 3.0}}
