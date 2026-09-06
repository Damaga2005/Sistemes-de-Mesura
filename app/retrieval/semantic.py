"""Indice semantico TF-IDF local (stdlib + numpy). Reproducible e idempotente.

Limitacion documentada (§19/D21): sin stack neural offline en este entorno
(no hay torch/sklearn ni modelo descargable verificado); TF-IDF con coseno
es la estrategia local razonable. La interfaz EmbeddingProvider permite
sustituirlo por un modelo neuronal sin cambiar el consumidor.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

TOKEN_RE = re.compile(r"[a-zà-ÿ][a-zà-ÿ0-9_·'’μΩσ-]{2,}", re.I)


def tokenize(text: str, stopwords: frozenset = frozenset()) -> list[str]:
    return [w.lower() for w in TOKEN_RE.findall(text) if w.lower() not in stopwords]


@dataclass
class SemanticHit:
    chunk_id: str
    score: float  # coseno [0,1]


class TfidfIndex:
    def __init__(self, stopwords: frozenset = frozenset()) -> None:
        self.stopwords = stopwords
        self.vocab: dict[str, int] = {}
        self.idf: dict[str, float] = {}
        self.doc_ids: list[str] = []
        self.postings: dict[str, list[list]] = {}  # term -> [[doc_idx, w], ...]
        self.norms: list[float] = []

    def build(self, docs: list[tuple[str, str]]) -> dict:
        """docs: [(chunk_id, text)] en orden determinista. Devuelve stats + hash."""
        self.doc_ids = [d for d, _ in docs]
        tf: list[dict[str, float]] = []
        df: dict[str, int] = {}
        for _, text in docs:
            counts: dict[str, int] = {}
            for tok in tokenize(text, self.stopwords):
                counts[tok] = counts.get(tok, 0) + 1
            row = {t: 1.0 + math.log(c) for t, c in counts.items()}
            tf.append(row)
            for t in counts:
                df[t] = df.get(t, 0) + 1
        n = len(docs)
        terms = sorted(df)
        self.vocab = {t: i for i, t in enumerate(terms)}
        self.idf = {t: math.log((n + 1.0) / (df[t] + 1.0)) + 1.0 for t in terms}
        self.postings = {t: [] for t in terms}
        self.norms = []
        h = hashlib.sha256()
        for i, row in enumerate(tf):
            norm = 0.0
            for t, w in row.items():
                weight = round(w * self.idf[t], 6)
                self.postings[t].append([i, weight])
                norm += weight * weight
            self.norms.append(round(math.sqrt(norm), 6))
            h.update(self.doc_ids[i].encode())
            h.update(b"\x00")
        return {"docs": n, "terms": len(terms), "content_hash": h.hexdigest()}

    def vectorize(self, text: str) -> dict[str, float]:
        counts: dict[str, int] = {}
        for tok in tokenize(text, self.stopwords):
            if tok in self.idf:
                counts[tok] = counts.get(tok, 0) + 1
        return {t: round((1.0 + math.log(c)) * self.idf[t], 6) for t, c in counts.items()}

    def search(self, query: str, limit: int = 60) -> list[SemanticHit]:
        qvec = self.vectorize(query)
        if not qvec:
            return []
        qnorm = math.sqrt(sum(w * w for w in qvec.values()))
        acc: dict[int, float] = {}
        for t, qw in qvec.items():
            for idx, dw in self.postings.get(t, []):
                acc[idx] = acc.get(idx, 0.0) + qw * dw
        out = []
        for idx, dot in acc.items():
            denom = self.norms[idx] * qnorm
            if denom > 0:
                out.append(SemanticHit(self.doc_ids[idx], round(dot / denom, 6)))
        out.sort(key=lambda x: -x.score)
        return out[:limit]

    def save(self, directory: str | Path) -> None:
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        (d / "vocab.json").write_text(json.dumps(
            {"vocab": self.vocab, "idf": self.idf, "doc_ids": self.doc_ids,
             "norms": self.norms}, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        (d / "postings.json").write_text(json.dumps(self.postings, ensure_ascii=False, sort_keys=True),
                                         encoding="utf-8")

    @classmethod
    def load(cls, directory: str | Path, stopwords: frozenset = frozenset()) -> "TfidfIndex":
        d = Path(directory)
        idx = cls(stopwords)
        meta = json.loads((d / "vocab.json").read_text(encoding="utf-8"))
        idx.vocab, idx.idf = meta["vocab"], meta["idf"]
        idx.doc_ids, idx.norms = meta["doc_ids"], meta["norms"]
        idx.postings = json.loads((d / "postings.json").read_text(encoding="utf-8"))
        return idx
