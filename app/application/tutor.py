"""TutorWorkflow: USER QUERY → F3 → ANSWER/ABSTAIN (B4.1).

Delega íntegramente en ReasoningEngine. Proyecta la respuesta a campos
seguros (sin prompts internos, sin scores de retrieval, sin CoT).
"""
from __future__ import annotations

from .context import ApplicationContext
from .errors import AppError


class TutorWorkflow:
    def __init__(self, app) -> None:
        self.app = app

    def ask(self, ctx: ApplicationContext, query: str,
            top_k: int = 10) -> dict:
        if not isinstance(query, str) or not query.strip():
            raise AppError("USER_ERROR", "pregunta vacía")
        if not isinstance(top_k, int) or top_k < 1:
            raise AppError("VALIDATION_ERROR", "top_k inválido")
        self.app.require(self.app.__dict__, "reasoning")
        try:
            ans = self.app.reasoning.answer(query, top_k=top_k)
        except AppError:
            raise
        except RuntimeError as e:
            raise AppError("GENERATION_ERROR", str(e)[:300],
                           cause=type(e).__name__)
        except (KeyError, ValueError) as e:
            raise AppError("RETRIEVAL_ERROR", str(e)[:300],
                           cause=type(e).__name__)
        d = ans.to_dict() if hasattr(ans, "to_dict") else dict(ans)
        return {"ok": True, "data": _project(d, ctx)}


def _project(d: dict, ctx: ApplicationContext) -> dict:
    claims = []
    for c in d.get("claims", []) or []:
        claims.append({"text": c.get("text", ""),
                       "type": c.get("type", ""),
                       "status": c.get("status", ""),
                       "evidence_ids": list(c.get("evidence_ids", []) or [])})
    prov = d.get("versions", {}) or {}
    provider = prov.get("provider", "")
    if isinstance(provider, dict):
        provider = {"provider": provider.get("provider", ""),
                    "model": provider.get("model", "")}
    return {"answer": d.get("answer", ""),
            "status": d.get("verification_status", ""),
            "abstain": bool(d.get("abstain", False)),
            "abstention_type": d.get("abstention_type"),
            "language": d.get("language", ctx.language),
            "claims": claims,
            "formulas": [{"equation_id": f.get("equation_id", "")}
                         for f in d.get("formulas", []) or []],
            "provenance": [{"source_path": p.get("source_path", ""),
                            "source_hash": p.get("source_hash", ""),
                            "topic": p.get("topic")}
                           for p in d.get("provenance", []) or []],
            "versions": {"reasoning": prov.get("reasoning", ""),
                         "prompt": prov.get("prompt", ""),
                         "retrieval": prov.get("retrieval", ""),
                         "provider": provider}}
