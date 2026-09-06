"""ReasoningEngine (§10, §45): retrieval obligatorio -> pack -> LLM ->
claims -> verificacion -> [second retrieval] -> respuesta verificada o abstencion.

Nunca KB directa desde el razonador: solo EvidencePack (§20). Rondas max 2 (§30-31).
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from app.llm.extractive import ExtractiveProvider
from app.llm.gemini import select_provider
from app.llm.interface import Message
from app.retrieval.models import RetrievalFilters
from app.retrieval.service import RetrievalService

from .claims import ClaimVerifier, extract_claims, verify_calculation
from .formula_check import FormulaValidator
from .models import CalculationCheck, VerifiedAnswer

PROMPTS = Path(__file__).resolve().parent.parent / "llm" / "prompts"
MAX_ROUNDS = 2

# Intentos de override del usuario (§53-54): patrones generales ES/CA de
# autorizacion de fuente externa o de ignorar instrucciones. No son queries
# concretas: es guarda anti-instruccion, siempre abstencion.
OVERRIDE_PATTERNS = [
    r"encara que no (sigui|estigui|hi sigui)",
    r"aunque no (sea|est[eé])",
    r"ignora (les|las|els|los) instruccions?",
    r"ignora (les|las|els|los) instrucciones?",
    r"oblida([ -]t)? (les|las|el|tot|todo)",
    r"olvida (las|los|el|todo)",
    r"usa (aquesta|esta|essa) f[óo]rmula",
    r"usa (esta|esa) f[óo]rmula",
    r"fingeix|finge\b|actua com si|actúa como si",
    r"suposa que|supón que|imagina que",
]


def detect_override(query: str) -> bool:
    import re as _re
    return any(_re.search(p, query, _re.I) for p in OVERRIDE_PATTERNS)


def detect_language(query: str) -> str:
    import re as _re
    if _re.search(r"\b(qué|cómo|cuál|dónde|por qué|una|para|con|las|los)\b", query, _re.I):
        return "es"
    return "ca"


def build_prompt(query: str, pack_dict: dict, language: str, system_prompt: str) -> list[Message]:
    lines = ["PREGUNTA (%s): %s" % (language, query), "", "EVIDÈNCIA (única font):"]
    for r in pack_dict.get("primary_evidence", [])[:5]:
        lines.append("[%s] (%s) %s" % (r["chunk_id"], r.get("section", ""), r["text"][:1500]))
    for r in pack_dict.get("supporting_evidence", [])[:5]:
        lines.append("[%s] (suport) %s" % (r["chunk_id"], r["text"][:800]))
    for f in pack_dict.get("formulas", [])[:12]:
        lines.append("[%s] FÓRMULA %s (%s)" % (
            f["equation_id"], f["expression"], f.get("section_h2", "")))
    for v in pack_dict.get("visuals", [])[:5]:
        lines.append("[%s] FIGURA: %s" % (v["asset_id"], v.get("caption", "")))
    lines.append("Respon en %s." % ("català" if language == "ca" else "español"))
    return [Message("system", system_prompt), Message("user", "\n".join(lines))]


def parse_structured(text: str) -> dict:
    t = text.strip()
    # Cercas markdown habituales, fuera del JSON.
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    start, end = t.find("{"), t.rfind("}")
    if 0 <= start < end:
        try:
            return json.loads(t[start:end + 1])
        except json.JSONDecodeError:
            pass
    raise ValueError("LLM JSON invalido (sin reparacion posible)")


class ReasoningEngine:
    def __init__(self, retriever: RetrievalService, kb_path: str, *,
                 provider=None, prompt_version: str = "reasoning_v2") -> None:
        self.retriever = retriever
        self.validator = FormulaValidator(kb_path)
        self.claim_verifier = ClaimVerifier(self.validator)
        self.provider = provider or select_provider()
        self.prompt_version = prompt_version
        self.system_prompt = (PROMPTS / (prompt_version + ".txt")).read_text(encoding="utf-8")

    def answer(self, query: str, *, filters: RetrievalFilters | None = None,
               top_k: int = 10) -> VerifiedAnswer:
        t0 = time.perf_counter()
        lat: dict = {}
        lang = detect_language(query)
        t = time.perf_counter()
        if detect_override(query):
            pack = self.retriever.retrieve_evidence(query, filters=filters, top_k=top_k)
            lat["retrieval_ms"] = round((time.perf_counter() - t) * 1000, 1)
            ans = self._abstain(query, lang, pack, "CONFLICTING_EVIDENCE", lat, t0)
            ans.warnings = ["adversarial_override: la pregunta autoritza font externa; "
                            "rebutjat per politica KB-only"] + ans.warnings
            return ans
        pack = self.retriever.retrieve_evidence(query, filters=filters, top_k=top_k)
        lat["retrieval_ms"] = round((time.perf_counter() - t) * 1000, 1)
        if pack.abstain:
            return self._abstain(query, lang, pack, "NO_EVIDENCE" if not pack.results
                                 else "INSUFFICIENT_EVIDENCE", lat, t0)
        for _ in range(MAX_ROUNDS):
            structured, provider_info = self._reason(query, lang, pack, lat)
            if structured.get("needs_more_evidence") and structured.get("missing_evidence"):
                pack = self._second_retrieval(query, pack, structured["missing_evidence"],
                                              filters, top_k)
                if pack.abstain:
                    return self._abstain(query, lang, pack, "INSUFFICIENT_EVIDENCE", lat, t0)
                continue
            return self._verify(query, lang, pack, structured, provider_info, lat, t0)
        # Tras 2 rondas insatisfechas: degradacion a extractivo verificado sobre
        # el pack acumulado (nunca vacío aquí), con aviso. Solo si hay evidencia.
        if pack.results or pack.formulas:
            provider_info = {"provider": "extractive-fallback", "model": "extractive-v1",
                             "fallback_reason": "needs-more-evidence-unsatisfied"}
            structured = parse_structured(
                ExtractiveProvider().answer_from_pack(query, pack, self.prompt_version).text)
            structured.setdefault("uncertainties", []).append(
                "needs-more-evidence-unsatisfied")
            return self._verify(query, lang, pack, structured, provider_info, lat, t0)
        return self._abstain(query, lang, pack, "INSUFFICIENT_EVIDENCE", lat, t0)

    def _reason(self, query, lang, pack, lat) -> tuple[dict, dict]:
        from app.retrieval.models import pack_to_dict
        if isinstance(self.provider, ExtractiveProvider):
            t = time.perf_counter()
            resp = self.provider.answer_from_pack(query, pack, self.prompt_version)
            lat["llm_ms"] = round((time.perf_counter() - t) * 1000, 1)
            return parse_structured(resp.text), {"provider": resp.provider,
                                                 "model": resp.model}
        pdict = pack_to_dict(pack)
        messages = build_prompt(query, pdict, lang, self.system_prompt)
        last_error, resp, info = None, None, {}
        for _ in range(2):
            t = time.perf_counter()
            try:
                resp = self.provider.generate(messages, temperature=0.0)
            except RuntimeError as e:
                raise RuntimeError(str(e))
            lat["llm_ms"] = round((time.perf_counter() - t) * 1000, 1)
            info = {"provider": resp.provider, "model": resp.model, "usage": resp.usage}
            try:
                return parse_structured(resp.text), info
            except ValueError as e:
                last_error = str(e)
                messages = messages + [Message(
                    "user", "Tu salida no era JSON válido. Repite EXACTAMENTE el mismo "
                            "contenido en JSON estricto, sin texto fuera.")]
        # Degradacion controlada (§37): antes de fallar, respuesta extractiva
        # verificada con aviso explicito de proveedor (no se finge el LLM).
        fallback = ExtractiveProvider().answer_from_pack(query, pack, self.prompt_version)
        try:
            parsed = parse_structured(fallback.text)
        except ValueError:
            raise RuntimeError("reasoning_unavailable: salida no estructurada (%s)" % last_error)
        parsed.setdefault("uncertainties", []).append("llm_malformed_fallback")
        lat["llm_fallback"] = True
        return parsed, {"provider": "extractive-fallback", "model": "extractive-v1",
                        "fallback_reason": last_error}

    def _second_retrieval(self, query, pack, missing, filters, top_k):
        extra_queries = []
        for m in missing[:3]:
            extra_queries.append("%s %s" % (query, m) if isinstance(m, str)
                                 else query + " " + json.dumps(m, ensure_ascii=False))
        seen = {r["chunk_id"] for r in pack.results}
        for q in extra_queries:
            more = self.retriever.retrieve_evidence(q, filters=filters, top_k=top_k)
            for r in more.results:
                if r["chunk_id"] not in seen:
                    seen.add(r["chunk_id"])
                    pack.results.append(r)
            for f in more.formulas:
                if f["equation_id"] not in {x["equation_id"] for x in pack.formulas}:
                    pack.formulas.append(f)
        return pack

    def _verify(self, query, lang, pack, structured, provider_info, lat, t0) -> VerifiedAnswer:
        t = time.perf_counter()
        ev_texts = {r["chunk_id"]: r["text"] for r in pack.results}
        ev_forms = {f["equation_id"]: f for f in pack.formulas}
        claims = extract_claims(structured)
        for c in claims:
            self.claim_verifier.verify(c, ev_texts, ev_forms)
        calc_checks = []
        for calc in structured.get("calculations", [])[:10]:
            if not isinstance(calc, dict) or "expression" not in calc:
                continue
            res = verify_calculation(str(calc["expression"]), calc.get("result"),
                                     str(calc.get("unit", "")))
            calc_checks.append(CalculationCheck(
                expression=str(calc["expression"]), claimed=calc.get("result"),
                computed=res.get("computed"), unit=str(calc.get("unit", "")),
                match=bool(res.get("match")), detail=res.get("detail", "")))
        form_status = self._formula_status(structured, pack)
        status, abst_type = self._aggregate(claims, calc_checks, form_status, pack)
        lat["verification_ms"] = round((time.perf_counter() - t) * 1000, 1)
        lat["total_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        if status == "ABSTAIN":
            return self._abstain(query, lang, pack, abst_type or "INSUFFICIENT_EVIDENCE",
                                 lat, t0)
        provenance = [{"source_path": s["source_path"], "source_hash": s["source_hash"],
                       "topic": s["topic"]} for s in pack.sources]
        return VerifiedAnswer(
            query=query, language=lang, answer=str(structured.get("answer", "")),
            claims=claims, formulas=[dict(f) for f in pack.formulas[:12]],
            calculations=calc_checks, verification_status=status,
            formula_verification=form_status, confidence=status, abstain=False,
            abstention_type=None, provenance=provenance,
            warnings=[w.get("warning", str(w)) for w in pack.warnings],
            versions={"reasoning": "reasoning-3.0", "prompt": self.prompt_version,
                      "retrieval": "retrieval-2.0", "provider": provider_info},
            latency_ms=lat)

    def _formula_status(self, structured, pack) -> str:
        pack_ids = {f["equation_id"] for f in pack.formulas}
        used = [f for f in structured.get("formulas_used", []) if isinstance(f, str)]
        inline = 0
        for c in structured.get("claims", []):
            if isinstance(c, dict) and c.get("type") == "FORMULA" and not c.get("evidence_ids"):
                inline += 1
                m = re.search(r"\$.+?\$", str(c.get("text", "")))
                if m:
                    status, _ = self.validator.check_latex(m.group(0))
                    if status == "MISSING":
                        return "MISMATCH"
                    used.append("__equiv__" if status == "EQUIVALENT_MATCH" else "__exact__")
        if not used and not inline:
            return "MISSING"
        for fid in used:
            if fid in ("__equiv__", "__exact__"):
                continue
            if fid not in pack_ids and self.validator.check_id(fid)[0] == "MISSING":
                return "MISMATCH"
        if "__equiv__" in used:
            return "EQUIVALENT_MATCH"
        return "EXACT_MATCH"

    def _aggregate(self, claims, calc_checks, form_status, pack):
        if not claims:
            return "ABSTAIN", "NO_EVIDENCE"
        statuses = [c.status for c in claims]
        if any(s == "CONTRADICTED" for s in statuses):
            return "ABSTAIN", "CONFLICTING_EVIDENCE"
        if any(not c.match for c in calc_checks):
            return "ABSTAIN", "CALCULATION_UNCERTAIN"
        if form_status == "MISMATCH":
            return "ABSTAIN", "UNSUPPORTED_FORMULA"
        if all(s == "SUPPORTED" for s in statuses):
            return ("VERIFIED" if form_status in ("EXACT_MATCH", "MISSING") else "SUPPORTED"), None
        if all(s in ("SUPPORTED", "PARTIALLY_SUPPORTED") for s in statuses):
            return "PARTIAL", None
        if any(s == "SUPPORTED" for s in statuses):
            return "PARTIAL", None
        return "ABSTAIN", "INSUFFICIENT_EVIDENCE"

    def _abstain(self, query, lang, pack, abst_type, lat, t0) -> VerifiedAnswer:
        lat["total_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        msg = ("No he trobat evidència suficient en el material de Sistemes de Mesura "
               "per respondre amb fiabilitat." if lang == "ca" else
               "No he encontrado evidencia suficiente en el material de Sistemes de Mesura "
               "para responder con fiabilidad.")
        return VerifiedAnswer(
            query=query, language=lang, answer=msg, claims=[], formulas=[],
            calculations=[], verification_status="ABSTAIN", formula_verification="MISSING",
            confidence="ABSTAIN", abstain=True, abstention_type=abst_type,
            provenance=[{"source_path": s["source_path"], "source_hash": s["source_hash"],
                         "topic": s["topic"]} for s in pack.sources],
            warnings=[w.get("warning", str(w)) for w in pack.warnings],
            versions={"reasoning": "reasoning-3.0", "prompt": self.prompt_version,
                      "retrieval": "retrieval-2.0", "provider": {"provider": "none"}},
            latency_ms=lat)
