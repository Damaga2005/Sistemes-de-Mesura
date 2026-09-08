"""ExaminerEngine: blueprint con evidencia -> generacion -> validacion -> store.

Ruta determinista por defecto (reproducible, sin coste); LLM solo para tipos
abiertos con --llm (mismo pipeline de verificacion). Rechazar es correcto.
"""
from __future__ import annotations

from app.llm.extractive import ExtractiveProvider
from app.llm.gemini import select_provider
from app.retrieval.models import RetrievalFilters

from . import blueprints as BP
from . import evidence as EV
from . import staticgen as SG
from .llmgenerator import build_generation_messages, parse_candidate
from .models import (EXAMINER_VERSION, Question, QuestionClaim, QuestionOption,
                     QuestionSolution, fingerprint)
from .store import QuestionStore
from .verify import QuestionValidator

PROMPT_VERSION = "question_generation_v1"


class ExaminerEngine:
    def __init__(self, retriever, kb_path: str, store_path: str, *,
                 provider=None, use_llm: bool = False) -> None:
        self.retriever = retriever
        self.kb_path = kb_path
        self.store = QuestionStore(store_path)
        self.validator = QuestionValidator(kb_path)
        self.provider = provider
        self.use_llm = use_llm

    def _provider(self):
        if self.provider is not None:
            return self.provider
        try:
            return select_provider("gemini")
        except RuntimeError:
            return ExtractiveProvider()

    def generate(self, *, topic: int, section: str = "", question_type: str,
                 difficulty: str = "", formula_id: str = "", seed: int = 0,
                 debug: bool = False, origin: str = "GENERATED") -> tuple[Question | None, dict]:
        from .models import QUESTION_ORIGINS
        if origin not in QUESTION_ORIGINS:
            raise ValueError("origin no válido: %r" % origin)
        log: dict = {"seed": seed, "topic": topic, "type": question_type,
                     "origin": origin}
        bp, reason, evsum = BP.build_blueprint(
            self.retriever, self.kb_path, topic=topic, section=section,
            question_type=question_type, difficulty=difficulty,
            formula_id=formula_id, seed=seed)
        log["blueprint"] = reason
        if bp is None:
            return None, {**log, "rejected": reason}
        pack = self.retriever.retrieve_evidence(
            bp.section.strip() or ("Tema %d" % topic),
            filters=RetrievalFilters(topic=topic), top_k=10)
        ev_texts = {r["chunk_id"]: r["text"] for r in pack.results}
        forms = {f["equation_id"]: f for f in pack.formulas}
        q: Question | None = None
        extra_texts: dict = {}
        if question_type == "TRUE_FALSE":
            built = self._gen_tf(bp, seed)
        elif question_type in ("FORMULA", "MULTIPLE_CHOICE") and bp.formula_ids:
            built = self._gen_formula_mcq(bp, seed)
        elif question_type == "NUMERICAL":
            built = self._gen_numerical(bp, seed)
        elif question_type == "MULTI_STEP":
            built = self._gen_multistep(bp, seed)
        elif question_type == "SHORT_ANSWER":
            built = self._gen_short(bp, pack, seed)
        elif self.use_llm and question_type in ("THEORY", "CONCEPTUAL", "OPEN",
                                                "MULTIPLE_CHOICE"):
            built = self._gen_llm(bp, pack, seed)
        else:
            built = self._gen_theory_template(bp, pack, seed)
        if built is None or built[0] is None:
            return None, {**log, "rejected": "NO_EVIDENCE_OR_GENERATION_FAILED"}
        q, extra_texts = built
        q.origin = origin
        ev_texts.update(extra_texts)
        self.validator.validate(q, ev_texts, forms)
        # Enlazar formulas validadas (claims FORMULA SUPPORTED con id canonico):
        # la matriz formula->preguntas (§37) queda completa tambien via LLM.
        for c in q.claims:
            if c.type == "FORMULA" and c.status == "SUPPORTED":
                for eid in c.evidence_ids:
                    if eid.startswith("eq-") and eid not in q.formula_ids:
                        q.formula_ids.append(eid)
        log["validation"] = q.validation.status
        if q.validation.status == "INVALID":
            return None, {**log, "rejected": ";".join(q.validation.reasons)}
        self.store.put(q)
        out = {**log, "question_id": q.question_id, "status": q.validation.status,
               "fingerprint": q.fingerprint}
        if debug:
            out["blueprint_obj"] = bp.__dict__
            out["evidence"] = evsum
        return q, out

    # ---------- deterministic builders ----------
    def _base(self, bp, seed, prompt) -> Question:
        fp = fingerprint(bp.topic, bp.section, bp.question_type,
                         bp.learning_objective, bp.formula_ids, bp.concept_terms, prompt)
        return Question(question_id="q-" + fp[:12], version="4.0", topic=bp.topic,
                        section=bp.section, type=bp.question_type,
                        difficulty=bp.difficulty, prompt=prompt,
                        formula_ids=list(bp.formula_ids), seed=seed,
                        evidence_refs=[], fingerprint=fp,
                        prompt_version="", generator_version=EXAMINER_VERSION)

    def _gen_tf(self, bp, seed):
        # Seccion del blueprint o la del pack: usar la seccion efectiva.
        rec = SG.gen_true_false(self.kb_path, bp.topic, bp.section, seed)
        if not rec:
            return None, {}
        q = self._base(bp, seed, "Vertader o fals: %s" % rec["statement"].lstrip("| ").strip())
        q.section = rec["section"] or bp.section
        q.correct_answer = "V" if rec["truth"] else "F"
        q.expected_answer = q.correct_answer
        q.solution = QuestionSolution(
            final_answer=q.correct_answer,
            reasoning_steps=[rec["explanation"]], interpretation=rec["explanation"])
        q.source_refs = [{"source_path": rec["source_path"]}]
        q.evidence_refs = [rec["evidence"]]
        q.claims = [QuestionClaim(text=rec["statement"],
                                  type="FACTUAL", evidence_ids=[rec["evidence"]])]
        return q, {rec["evidence"]: rec["text"]}

    def _gen_formula_mcq(self, bp, seed):
        rec = EV.formula_record(self.kb_path, bp.formula_ids[0])
        gen = SG.gen_formula_mcq(rec, seed)
        if len(gen["options"]) < 2:
            return None, {}
        q = self._base(bp, seed, gen["stem"])
        q.options = [QuestionOption(**o) for o in gen["options"]]
        q.correct_answer = gen["correct_answer"]
        q.expected_answer = gen["correct_answer"]
        q.solution = QuestionSolution(
            final_answer=gen["correct_answer"], reasoning_steps=gen["solution_steps"],
            formula_application=[{"formula_id": rec["equation_id"],
                                   "substitution": rec["expression"]}])
        q.source_refs = [{"source_path": rec["source_path"]}]
        q.evidence_refs = []
        # Evidencia: chunks de la seccion de la formula (nunca el equation_id
        # como texto: 'eq-02-0201' contamina con tokens eq/0201).
        pack = self.retriever.retrieve_evidence(
            rec["section_h2"] or rec.get("h1", "") or rec["expression"][:60],
            filters=RetrievalFilters(topic=bp.topic), top_k=5)
        q.evidence_refs = [r["chunk_id"] for r in pack.results[:3]]
        if not q.evidence_refs:
            return None, {}
        q.claims = [QuestionClaim(text=gen["correct_answer"], type="FORMULA",
                                  evidence_ids=[rec["equation_id"]])]
        # Verificar unicidad real: ningun distractor equivalente.
        from .distractors import validate_distractors
        ok, _ = validate_distractors(rec["expression"],
                                     [o for o in gen["options"] if not o["correct"]])
        if not ok:
            return None, {}
        return q, {r["chunk_id"]: r["text"] for r in pack.results}

    def _gen_numerical(self, bp, seed):
        if not bp.formula_ids:
            return None, {}
        rec = EV.formula_record(self.kb_path, bp.formula_ids[0])
        gen = SG.gen_numerical(rec, seed)
        if not gen:
            return None, {}
        from app.reasoning.calculator import check_dimensions
        units = {s: "" for s in gen["values"]}
        dim_ok = None
        if all(units.values()):
            dim_ok = check_dimensions("", [], "")
        prompt = ("Donades %s, calcula %s amb %s." % (
            gen["given"], gen["target"], rec["equation_id"]))
        q = self._base(bp, seed, prompt)
        q.variables = {s: {"value": v["value"], "unit": v["unit"], "kind": v["kind"]}
                       for s, v in gen["values"].items()}
        q.units = {"__status__": "UNIT_VALIDATION_UNAVAILABLE",
                   "__dimension_ok__": dim_ok}
        q.solution = QuestionSolution(
            final_answer=str(gen["result"]), reasoning_steps=gen["steps"],
            formula_application=[{"formula_id": rec["equation_id"],
                                   "substitution": gen["py_expr"]}],
            calculation={"expression": gen["py_expr"], "result": gen["result"],
                         "verified": True, "unit": ""},
            interpretation="Resultat determinista verificat.")
        q.correct_answer = str(gen["result"])
        q.expected_answer = str(gen["result"])
        q.source_refs = [{"source_path": rec["source_path"]}]
        pack = self.retriever.retrieve_evidence(
            rec["section_h2"] or rec.get("h1", "") or rec["expression"][:60],
            filters=RetrievalFilters(topic=bp.topic), top_k=5)
        q.evidence_refs = [r["chunk_id"] for r in pack.results[:3]]
        if not q.evidence_refs:
            return None, {}
        q.claims = [QuestionClaim(text=rec["expression"], type="FORMULA",
                                  evidence_ids=[rec["equation_id"]])]
        return q, {r["chunk_id"]: r["text"] for r in pack.results}

    def _gen_multistep(self, bp, seed):
        for chain in SG.find_chains(self.kb_path, bp.topic, seed):
            built = self._try_chain(bp, chain, seed)
            if built is not None:
                return built
        return None, {}

    def _try_chain(self, bp, chain, seed):
        rec1 = EV.formula_record(self.kb_path, chain["first"])
        rec2 = EV.formula_record(self.kb_path, chain["second"])
        g1 = SG.gen_numerical(rec1, seed)
        if not g1:
            return None, {}
        # El intermedio alimenta F2: resolver F1 y sustituir el simbolo comun.
        from . import numerical as NUM
        try:
            py2, map2 = NUM.to_python(rec2["expression"])
        except ValueError:
            return None, {}
        core1 = rec1["expression"].strip()
        if core1.startswith("$") and core1.endswith("$"):
            core1 = core1[1:-1]
        out_sym = core1.split("=", 1)[0].strip() if "=" in core1 else ""
        # Simplificacion honesta: el paso 2 usa el resultado como dato derivado.
        vals2 = dict(g1["values"])
        # Buscar que simbolo de F2 corresponde a la salida de F1.
        linked = [s for s in map2 if s == out_sym]
        if not linked:
            # Coincidencia por base plegada (u_c vs uc).
            from app.retrieval.formula import base_key
            linked = [s for s in map2 if base_key(s) == base_key(out_sym)]
        if not linked:
            return None, {}
        vals2[linked[0]] = {"value": g1["result"], "unit": "", "kind": "DERIVED_VALUE"}
        # Completar resto de simbolos de F2 con valores seed (determinista).
        for s in map2:
            if s not in vals2:
                extra = NUM.generate_values([s], seed + 331, {})
                vals2[s] = extra[s]
        py_vals2 = {map2[s]: vals2[s]["value"] for s in map2}
        ok, _ = NUM.check_denominators(py2, py_vals2)
        if not ok:
            return None, {}
        try:
            res2 = NUM.solve(py2, py_vals2)
        except ValueError:
            return None, {}
        q = self._base(bp, seed + 1, "Encadenat: calcula %s amb %s i usa el resultat en %s." % (
            out_sym, chain["first"], chain["second"]))
        q.formula_ids = [chain["first"], chain["second"]]
        q.fingerprint = fingerprint(bp.topic, bp.section, bp.question_type,
                                    bp.learning_objective, q.formula_ids, [],
                                    q.prompt)
        q.question_id = "q-" + q.fingerprint[:12]
        q.variables = {s: {"value": v["value"], "unit": v["unit"], "kind": v["kind"]}
                       for s, v in vals2.items()}
        q.units = {"__status__": "UNIT_VALIDATION_UNAVAILABLE", "__dimension_ok__": None}
        q.solution = QuestionSolution(
            final_answer=str(res2),
            reasoning_steps=["Pas 1: %s = %s." % (out_sym, g1["result"]),
                             "Pas 2: substituir en %s." % chain["second"],
                             "Càlcul determinista = %s." % res2],
            formula_application=[{"formula_id": chain["first"], "substitution": g1["py_expr"]},
                                 {"formula_id": chain["second"], "substitution": py2}],
            calculation={"expression": py2, "result": res2, "verified": True, "unit": ""})
        q.correct_answer, q.expected_answer = str(res2), str(res2)
        q.source_refs = [{"source_path": rec1["source_path"]},
                         {"source_path": rec2["source_path"]}]
        q.evidence_refs, q.claims = [], []
        pack = self.retriever.retrieve_evidence(
            rec2["section_h2"], filters=RetrievalFilters(topic=bp.topic), top_k=5)
        q.evidence_refs = [r["chunk_id"] for r in pack.results[:3]]
        if not q.evidence_refs:
            return None, {}
        q.claims = [QuestionClaim(text=rec1["expression"], type="FORMULA",
                                  evidence_ids=[chain["first"]]),
                    QuestionClaim(text=rec2["expression"], type="FORMULA",
                                  evidence_ids=[chain["second"]])]
        return q, {r["chunk_id"]: r["text"] for r in pack.results}

    def _gen_short(self, bp, pack, seed):
        prim = pack.primary_evidence[:3] if pack.primary_evidence else pack.results[:3]
        if not prim:
            return None, {}
        chunk = {"chunk_id": prim[0]["chunk_id"], "text": prim[0]["text"]}
        gen = SG.gen_short_answer(chunk, seed)
        if not gen:
            return None, {}
        q = self._base(bp, seed, gen["prompt"])
        q.expected_answer, q.correct_answer = gen["expected_answer"], gen["expected_answer"]
        q.solution = QuestionSolution(final_answer=gen["expected_answer"],
                                      reasoning_steps=["Definició literal del material."])
        q.source_refs = [{"source_path": prim[0]["source_path"]}]
        q.evidence_refs = [gen["evidence"]]
        q.claims = [QuestionClaim(text=gen["expected_answer"][:500], type="DEFINITION",
                                  evidence_ids=[gen["evidence"]])]
        q.concept_terms = gen["required_concepts"]
        return q, {}

    def _gen_theory_template(self, bp, pack, seed):
        prim = pack.primary_evidence[:2] if pack.primary_evidence else pack.results[:2]
        if not prim:
            return None, {}
        first = prim[0]
        where = first.get("section") or bp.section or "el material"
        prompt = "Explica, segons «%s»: %s" % (
            where, (first["text"][:160].rsplit(" ", 1)[0] + "…"))
        q = self._base(bp, seed, prompt)
        q.expected_answer = first["text"][:800]
        q.correct_answer = q.expected_answer
        from app.retrieval.normalize_query import query_terms
        q.concept_terms = [t for t in query_terms(first["text"]) if len(t) >= 5][:6]
        q.solution = QuestionSolution(final_answer=q.expected_answer,
                                      reasoning_steps=["Resposta basada en evidència citada."])
        q.source_refs = [{"source_path": first["source_path"]}]
        q.evidence_refs = [first["chunk_id"]]
        q.claims = [QuestionClaim(text=q.expected_answer[:500], type="EXPLANATION",
                                  evidence_ids=[first["chunk_id"]])]
        return q, {}

    def _gen_llm(self, bp, pack, seed):
        from app.retrieval.models import pack_to_dict
        provider = self._provider()
        if isinstance(provider, ExtractiveProvider):
            return None, {}
        messages = build_generation_messages(bp, {"formulas": pack.formulas,
                                                  "chunks": pack.results}, "ca")
        try:
            resp = provider.generate(messages, temperature=0.0)
        except RuntimeError:
            return None, {}
        from .llmgenerator import parse_candidate
        try:
            cand = parse_candidate(resp.text)
        except ValueError:
            return None, {}
        if cand.get("status") == "INSUFFICIENT_EVIDENCE":
            return None, {}
        q = self._base(bp, seed, str(cand.get("prompt", ""))[:2000])
        q.prompt_version = "question_generation_v1"
        for o in cand.get("options", [])[:6]:
            q.options.append(QuestionOption(text=str(o.get("text", ""))[:500],
                                            correct=bool(o.get("correct", False)),
                                            distractor_reason=str(o.get("distractor_reason", ""))))
        q.correct_answer = str(cand.get("correct_answer", ""))[:1000]
        q.expected_answer = str(cand.get("expected_answer", q.correct_answer))[:2000]
        q.solution = QuestionSolution(
            final_answer=q.expected_answer,
            reasoning_steps=[str(s)[:500] for s in cand.get("solution_steps", [])[:8]])
        q.hints = []
        q.source_refs = [{"source_path": s["source_path"]} for s in pack.sources[:4]]
        q.evidence_refs = [r["chunk_id"] for r in pack.results[:4]]
        q.concept_terms = [str(c)[:80] for c in cand.get("required_concepts", [])[:8]]
        for c in cand.get("claims", [])[:12]:
            if isinstance(c, dict) and c.get("text"):
                q.claims.append(QuestionClaim(
                    text=str(c["text"])[:800], type=str(c.get("type", "FACTUAL")),
                    evidence_ids=[e for e in c.get("evidence_ids", [])[:4]]))
        return q, {}
