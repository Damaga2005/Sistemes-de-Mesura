"""Proveedor extractivo determinista (fallback controlado §76).

NO genera conocimiento: compone la respuesta copiando evidencia (chunks,
formulas canonicas) con plantillas fijas por tipo de consulta. Toda claim
cita su evidencia y la verificacion la aprueba por construccion. No finge
ser un LLM generativo: provider_name lo declara.
"""
from __future__ import annotations

import json
import time

from app.retrieval.models import EvidencePack

from .interface import LLMResponse, Message


def _best_formula(pack: EvidencePack) -> dict | None:
    for f in pack.formulas:
        return f
    return None


class ExtractiveProvider:
    provider_name = "extractive-fallback"
    model_name = "extractive-v1"

    def generate(self, messages: list[Message], *, temperature: float = 0.0,
                 max_tokens: int = 1500) -> LLMResponse:
        raise RuntimeError("extractive-fallback: usar answer_extractivo(), no generate()")

    def answer_from_pack(self, query: str, pack: EvidencePack,
                         prompt_version: str = "reasoning_v1",
                         max_tokens: int = 1500) -> LLMResponse:
        t0 = time.perf_counter()
        prim = pack.primary_evidence[:3]
        claims, formulas_used = [], []
        parts = []
        for r in prim:
            claims.append({"text": r["text"][:500], "type": "FACTUAL",
                           "evidence_ids": [r["chunk_id"]]})
        for f in pack.formulas[:5]:
            formulas_used.append(f["equation_id"])
            claims.append({"text": f["expression"], "type": "FORMULA",
                           "evidence_ids": [f["equation_id"]]})
        if prim:
            first = prim[0]
            parts.append(first["text"][:1200])
        else:
            parts.append("No hi ha evidència.")
        for f in pack.formulas[:3]:
            parts.append("Fórmula %s: %s (%s)." % (
                f["equation_id"], f["expression"], f.get("section_h2", "")))
        srcs = sorted({s["source_path"] for s in pack.sources})
        parts.append("Fonts: " + "; ".join(srcs[:5]))
        out = {"answer": "\n\n".join(parts)[:max_tokens * 4],
               "claims": claims, "formulas_used": formulas_used,
               "calculations": [], "uncertainties": [],
               "needs_more_evidence": False, "missing_evidence": []}
        ms = round((time.perf_counter() - t0) * 1000, 1)
        return LLMResponse(text=json.dumps(out, ensure_ascii=False),
                           provider=self.provider_name, model=self.model_name,
                           prompt_version=prompt_version, latency_ms=ms)
