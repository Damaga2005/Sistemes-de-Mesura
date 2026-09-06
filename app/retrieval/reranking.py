"""Reranking determinista (§24): la corroboracion PDF no infla confianza.

Si un chunk PDF es casi-duplicado (Jaccard>=0.8) de un HTML mejor rankeado,
se degrada x0.5 con warning `pdf-corroboration` en lugar de sumar 2X.
"""
from __future__ import annotations

import re

from . import config as cfg

_TOKEN = re.compile(r"[a-zà-ÿ0-9_μΩσ]+", re.I)


def _toks(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


class Reranker:
    def rerank(self, ranked: list[dict]) -> list[dict]:
        """ranked: [{chunk_id, final, source_type, text, ...}] ordenados. Devuelve reordenados."""
        seen_html: list[set[str]] = []
        out = []
        for r in ranked[: cfg.RERANK_DEPTH]:
            if r.get("source_type") == "pdf":
                toks = _toks(r.get("text", ""))
                if toks and any(len(toks & h) / len(toks | h) >= 0.8 for h in seen_html):
                    r = dict(r)
                    r["final"] = round(r["final"] * 0.5, 4)
                    r.setdefault("warnings", []).append("pdf-corroboration")
                    r.setdefault("components", {})["pdf_demotion"] = 0.5
            else:
                seen_html.append(_toks(r.get("text", "")))
            out.append(r)
        out.extend(ranked[cfg.RERANK_DEPTH :])
        out.sort(key=lambda r: -r["final"])
        return out
