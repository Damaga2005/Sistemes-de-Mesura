"""CorrectionService (§4, §108): respuesta -> analisis -> verificacion
determinista (+LLM asistido donde aporta) -> rubrica -> score -> errores.

Prioridad: CANONICAL > DETERMINISTIC > RUBRIC > LLM (§75). El LLM nunca
decide la nota (§19) ni sobrescribe validadores (§74).
"""
from __future__ import annotations

import hashlib
import json
import time

from app.reasoning.calculator import check_dimensions, close_enough, safe_eval
from app.reasoning.claims import ClaimVerifier
from app.reasoning.formula_check import FormulaValidator
from app.reasoning.models import Claim as RClaim
from app.retrieval.normalize_query import query_terms

from . import errors as ERR
from .analyzer import analyze
from .models import (GRADER_VERSION, RUBRIC_VERSION, Correction, CorrectionClaim,
                     CriterionResult, StudentAnswer, rubric_for)
from .scoring import aggregate


def _norm_text(text: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFC", (text or "").lower())
    return " ".join(t.split())


class CorrectionService:
    def __init__(self, kb_path: str, questions_db: str) -> None:
        self.kb_path = kb_path
        self.questions_db = questions_db
        self.formulas = FormulaValidator(kb_path)
        self.claims = ClaimVerifier(self.formulas)

    # ---------- carga ----------
    def load_question(self, question_id: str) -> dict:
        import sqlite3
        con = sqlite3.connect("file:%s?mode=ro" % self.questions_db, uri=True)
        try:
            row = con.execute("SELECT body_json FROM questions WHERE question_id=?",
                              (question_id,)).fetchone()
        finally:
            con.close()
        if not row:
            raise KeyError("question not found: %s" % question_id)
        return json.loads(row[0])

    def evidence_texts(self, chunk_ids: list[str]) -> dict[str, str]:
        import sqlite3
        if not chunk_ids:
            return {}
        con = sqlite3.connect("file:%s?mode=ro" % self.kb_path, uri=True)
        try:
            return {r[0]: r[1] for r in con.execute(
                "SELECT id, text FROM chunks WHERE id IN (%s)" % ",".join(
                    "?" * len(chunk_ids)), tuple(chunk_ids)).fetchall()}
        finally:
            con.close()

    def formula_map(self, formula_ids: list[str]) -> dict[str, dict]:
        import sqlite3
        if not formula_ids:
            return {}
        con = sqlite3.connect("file:%s?mode=ro" % self.kb_path, uri=True)
        try:
            return {r[0]: {"equation_id": r[0], "expression": r[1]} for r in con.execute(
                "SELECT equation_id, expression FROM formulas WHERE equation_id IN (%s)"
                % ",".join("?" * len(formula_ids)), tuple(formula_ids)).fetchall()}
        finally:
            con.close()

    # ---------- API principal ----------
    def correct(self, question_id: str, answer: str, student_id: str = "local-01",
                attempt_id: str = "", exam_id: str = "", session_id: str = "",
                llm_assist: bool = False, provider=None) -> Correction:
        q = self.load_question(question_id)
        attempt_id = attempt_id or "att-" + hashlib.sha256(
            ("%s|%s|%s" % (student_id, question_id, _norm_text(answer))).encode()
            ).hexdigest()[:12]
        analyzed = analyze(answer)
        rubric = rubric_for(q["type"])
        ev_texts = self.evidence_texts(q.get("evidence_refs", []))
        forms = self.formula_map(q.get("formula_ids", []))
        results: list[CriterionResult] = []
        errors: list = []
        claims: list = []
        formula_results: list = []
        calc_results: list = []
        unit_results: list = []
        provenance = [{"source_path": s.get("source_path", "")}
                      for s in q.get("source_refs", [])]
        warnings: list = []
        if analyzed.instruction_flags:
            warnings.append("prompt_injection_ignored")
        assist_provider = provider

        if analyzed.empty:
            status = "NO_ANSWER"
            results = [CriterionResult(c.criterion_id, c.ctype, 0.0, 1.0, "UNSUPPORTED",
                                       "", "respuesta vacía", "deterministic")
                       for c in rubric.criteria]
        else:
            handler = {"TRUE_FALSE": self._grade_tf,
                       "MULTIPLE_CHOICE": self._grade_mcq,
                       "FORMULA": self._grade_formula,
                       "NUMERICAL": self._grade_numerical,
                       "MULTI_STEP": self._grade_numerical,
                       }.get(q["type"], self._grade_open)
            results, errors, claims, formula_results, calc_results, unit_results = handler(
                q, analyzed, ev_texts, forms, rubric)
            if llm_assist and q["type"] in ("OPEN", "THEORY", "CONCEPTUAL",
                                            "SHORT_ANSWER"):
                if assist_provider is None:
                    try:
                        from app.llm.gemini import select_provider
                        assist_provider = select_provider("auto")
                    except RuntimeError:
                        assist_provider = None
                self._llm_assist(q, analyzed, ev_texts, results, errors,
                                 assist_provider)
        # Feedback estructurado (plantillas por error, jamas generico).
        feedback = self._feedback(errors, results)
        # Score reproducible desde rubrica.
        for r, c in zip(results, rubric.criteria):
            r.max_score = c.weight
        score, auto_status = aggregate(results, max_score=10.0)
        if analyzed.empty:
            status = "NO_ANSWER"
        elif any(e.error_type == "AMBIGUOUS_ANSWER" for e in errors):
            status = "NEEDS_REVIEW"
        else:
            status = auto_status
        # claims a modelo de correccion
        claim_models = [CorrectionClaim(text=c.text, type=c.type, status=c.status,
                                        evidence_ids=c.evidence_ids) for c in claims]
        assisted = any(getattr(r, "source", "") == "llm-assisted"
                       for r in results)
        prov_name = getattr(assist_provider, "provider_name", "") \
            if assisted else ""
        if not prov_name and assisted:
            prov_name = type(assist_provider).__name__
        model_name = getattr(assist_provider, "model_name", "") \
            if assisted else ""
        corr = Correction(
            correction_id="corr-" + hashlib.sha256(
                ("%s|%s|%s" % (attempt_id, GRADER_VERSION,
                               RUBRIC_VERSION)).encode()).hexdigest()[:12],
            attempt_id=attempt_id, question_id=question_id,
            question_version=q.get("version", "4.0"),
            score=score, max_score=10.0, percentage=round(score * 10, 2),
            status=status, exam_id=exam_id, session_id=session_id,
            provider=prov_name, model=model_name, criteria_results=results,
            detected_errors=ERR.resolve_roots(errors), claims=claim_models,
            formula_results=formula_results, calculation_results=calc_results,
            unit_results=unit_results, feedback=feedback, provenance=provenance,
            knowledge_version="", mastery_policy_version="mastery-policy-v1")
        corr.rubric_snapshot = {"rubric_id": rubric.rubric_id,
                                "version": rubric.version,
                                "criteria": [{"id": c.criterion_id, "weight": c.weight,
                                              "required": c.required, "type": c.ctype}
                                             for c in rubric.criteria]}
        return corr

    # ---------- handlers por tipo ----------
    def _grade_tf(self, q, a, ev, forms, rubric):
        results, errors, claims = [], [], []
        expected = (q.get("correct_answer") or "").strip().upper()
        got = (a.selection or "").upper()
        ok = bool(got) and got == expected
        results.append(self._cr(rubric, "selection", 1.0 if ok else 0.0,
                                "V/F correcto" if ok else "V/F incorrecto"))
        if not got:
            errors.append(ERR.classify("INCOMPLETE_ANSWER", "selection"))
        elif not ok:
            errors.append(ERR.classify("WRONG_FINAL_RESULT", "selection"))
        claims.append(self._claim("Afirmación V/F del estudiante", "FACTUAL",
                                  list(ev)[:1], ev, forms))
        results.append(self._cr(rubric, "justification", 0.5 if ok else 0.0,
                                "evidencia citada" if ok else "sin justificacion correcta"))
        return results, errors, claims, [], [], []

    def _grade_mcq(self, q, a, ev, forms, rubric):
        results, errors, claims = [], [], []
        options = q.get("options", [])
        correct = [o for o in options if o.get("correct")]
        expected = (q.get("correct_answer") or "").strip()
        hit = None
        if a.selection and len(options) >= 2:
            idx = ord(a.selection) - 65
            if 0 <= idx < len(options):
                hit = options[idx]
        if hit is None and a.final:
            for o in options:
                if _norm_text(o.get("text", "")) == _norm_text(a.final):
                    hit = o
                    break
        ok = bool(hit) and bool(hit.get("correct"))
        results.append(self._cr(rubric, "selection", 1.0 if ok else 0.0,
                                "opcion correcta" if ok else "opcion incorrecta"))
        if hit is None:
            if a.formulas:
                # Ofrece una formula que no es ninguna opcion: error de formula.
                fresults = []
                bad = True
                for latex in a.formulas[:2]:
                    status, _ = self.formulas.check_latex(latex)
                    if status in ("EXACT_MATCH", "EQUIVALENT_MATCH"):
                        bad = False
                if bad:
                    errors.append(ERR.classify("FORMULA_ERROR", "selection"))
                else:
                    errors.append(ERR.classify("INCOMPLETE_ANSWER", "selection"))
            else:
                errors.append(ERR.classify("INCOMPLETE_ANSWER", "selection"))
        elif not ok:
            errors.append(ERR.classify("WRONG_FINAL_RESULT", "selection",
                                        hit.get("distractor_reason", "")))
            if "concept" in (hit.get("distractor_reason", "")):
                errors.append(ERR.classify("CONCEPT_ERROR", "selection"))
        claims.append(self._claim("Opción elegida: %s" % ((hit or {}).get("text", "?")[:200]),
                                  "FACTUAL", list(ev)[:1], ev, forms))
        results.append(self._cr(rubric, "justification", 0.5 if ok else 0.0, ""))
        return results, errors, claims, [], [], []

    def _grade_formula(self, q, a, ev, forms, rubric):
        results, errors, claims, fresults = [], [], [], []
        canonical_ids = q.get("formula_ids", [])
        if not a.formulas:
            errors.append(ERR.classify("INCOMPLETE_ANSWER", "formula"))
            results.append(self._cr(rubric, "formula", 0.0, "sin formula"))
            self._rest_zero(rubric, results, ["formula"])
            return results, errors, claims, fresults, [], []
        best, detail = "MISSING", ""
        for latex in a.formulas[:4]:
            status, rec = self.formulas.check_latex(latex)
            if status == "EXACT_MATCH" and (not canonical_ids or rec["equation_id"] in canonical_ids):
                best, detail = "EXACT_MATCH", rec["equation_id"]
                break
            if status == "EQUIVALENT_MATCH":
                best, detail = "EQUIVALENT_MATCH", (rec or {}).get("equation_id", "")
        fresults.append({"status": best, "detail": detail})
        if best in ("EXACT_MATCH", "EQUIVALENT_MATCH"):
            results.append(self._cr(rubric, "formula", 1.0, detail))
        else:
            results.append(self._cr(rubric, "formula", 0.0, "formula no canonica"))
            errors.append(ERR.classify("FORMULA_ERROR", "formula", detail))
        claims.append(self._claim("Fórmula del estudiante: %s" % a.formulas[0][:200],
                                  "FORMULA", canonical_ids, ev, forms))
        self._rest_zero(rubric, results, ["formula"])
        return results, errors, claims, fresults, [], []

    def _grade_numerical(self, q, a, ev, forms, rubric):
        results, errors, claims, fresults, calcres, unitres = [], [], [], [], [], []
        sol = q.get("solution", {}) or {}
        # Formula (si la respuesta trae latex).
        if a.formulas:
            for latex in a.formulas[:3]:
                status, rec = self.formulas.check_latex(latex)
                fresults.append({"status": status,
                                 "detail": (rec or {}).get("equation_id", "")})
            if any(f["status"] in ("EXACT_MATCH", "EQUIVALENT_MATCH") for f in fresults):
                results.append(self._cr(rubric, "formula", 1.0, "formula canonica"))
            else:
                results.append(self._cr(rubric, "formula", 0.0, "formula no canonica"))
                errors.append(ERR.classify("FORMULA_ERROR", "formula"))
        else:
            results.append(self._cr(rubric, "formula", 0.5, "formula no explicita"))
        # Variables presentes.
        expected_vars = set((sol.get("calculation", {}) or {}).get("expression", "") or "")
        results.append(self._cr(rubric, "variables", 0.5, "revision manual sugerida"))
        # Sustitucion: numeros del estudiante vs esperados (tolerante).
        exp_calc = sol.get("calculation", {}) or {}
        expected = exp_calc.get("result")
        got = None
        if a.final:
            try:
                got = float(a.final)
            except ValueError:
                pass
        if got is None and a.values:
            got = a.values[-1]["value"]
        calc_entry = {"expression": exp_calc.get("expression", ""), "expected": expected,
                      "claimed": got, "match": False, "detail": ""}
        if expected is not None and got is not None:
            if close_enough(got, expected):
                calc_entry.update(match=True, detail="coincide")
                results.append(self._cr(rubric, "calculation", 1.0, "correcto"))
                results.append(self._cr(rubric, "substitution", 1.0, "correcta"))
                results.append(self._cr(rubric, "result", 1.0, "correcto"))
            elif abs(got + expected) <= 1e-9 * max(abs(expected), 1e-12) and expected != 0:
                calc_entry.update(detail="signo opuesto: %s vs %s" % (got, expected))
                results.append(self._cr(rubric, "calculation", 0.2, "signo"))
                errors.append(ERR.classify("SIGN_ERROR", "calculation"))
                results.append(self._cr(rubric, "substitution", 0.5, "revisar signo"))
                results.append(self._cr(rubric, "result", 0.0, "incorrecto"))
                errors.append(ERR.classify("WRONG_FINAL_RESULT", "result"))
            elif abs(got - expected) <= 0.01 * max(abs(expected), 1e-12):
                calc_entry.update(detail="redondeo aceptable")
                results.append(self._cr(rubric, "calculation", 0.8, "redondeo"))
                errors.append(ERR.classify("ROUNDING_ERROR", "calculation"))
                results.append(self._cr(rubric, "substitution", 1.0, "correcta"))
                results.append(self._cr(rubric, "result", 0.8, "redondeo aceptable"))
            else:
                calc_entry.update(detail="difiere: %s vs %s" % (got, expected))
                results.append(self._cr(rubric, "calculation", 0.0, "incorrecto"))
                errors.append(ERR.classify("ARITHMETIC_ERROR", "calculation"))
                results.append(self._cr(rubric, "substitution", 0.5, "revisar"))
                results.append(self._cr(rubric, "result", 0.0, "incorrecto"))
                errors.append(ERR.classify("WRONG_FINAL_RESULT", "result"))
        else:
            results.append(self._cr(rubric, "calculation", 0.0, "sin numero"))
            errors.append(ERR.classify("INCOMPLETE_ANSWER", "calculation"))
            results.append(self._cr(rubric, "substitution", 0.0, ""))
            results.append(self._cr(rubric, "result", 0.0, ""))
        calcres.append(calc_entry)
        # Unidades: esperada (solucion/variables) vs estudiante.
        exp_unit = (exp_calc.get("unit") or "").strip()
        got_unit = (a.values[-1]["unit"] if a.values else "").strip()
        unitres, ures, uerr = self._check_units(exp_unit, got_unit)
        unit_results = unitres
        results.append(ures)
        errors.extend(uerr)
        results.append(self._cr(rubric, "interpretation", 0.5, "revision manual sugerida"))
        claims.append(self._claim("Resultado numerico del estudiante", "NUMERIC",
                                  list(ev)[:1], ev, forms))
        self._rest_zero(rubric, results, ["formula", "variables", "substitution",
                                          "calculation", "units", "result",
                                          "interpretation"])
        return results, errors, claims, fresults, calcres, unit_results

    def _check_units(self, expected: str, got: str):
        from .models import CriterionResult
        if not expected:
            return ([{"status": "UNIT_VALIDATION_UNAVAILABLE"}],
                    CriterionResult("units", "UNITS", 0.5, 1.0, "UNKNOWN",
                                    "", "sin unidad canonica", "deterministic"), [])
        if not got:
            return ([{"status": "missing", "expected": expected}],
                    CriterionResult("units", "UNITS", 0.0, 1.0, "UNSUPPORTED",
                                    "", "falta unidad", "deterministic"),
                    [ERR.classify("UNIT_ERROR", "units")])
        if got == expected:
            return ([{"status": "match"}], CriterionResult(
                "units", "UNITS", 1.0, 1.0, "SUPPORTED", "", "ok", "deterministic"), [])
        try:
            from app.reasoning.calculator import to_base
            gv, gb = to_base(1.0, got)
            ev, eb = to_base(1.0, expected)
            if gb == eb and abs(gv - ev) < 1e-12:
                return ([{"status": "converted", "from": got, "to": expected}],
                        CriterionResult("units", "UNITS", 1.0, 1.0, "SUPPORTED",
                                        "", "conversion valida", "deterministic"), [])
        except ValueError:
            pass
        return ([{"status": "mismatch", "expected": expected, "got": got}],
                CriterionResult("units", "UNITS", 0.0, 1.0, "CONTRADICTED",
                                "", "incompatible", "deterministic"),
                [ERR.classify("UNIT_ERROR", "units")])

    def _grade_open(self, q, a, ev, forms, rubric):
        from app.examiner.models import Question as _Q  # noqa
        results, errors, claims = [], [], []
        required = q.get("required_concepts", []) or q.get("concept_terms", [])[:6]
        blob = _norm_text(a.raw)
        hits = [t for t in required if t.lower() in blob]
        cov = (len(hits) / len(required)) if required else 0.0
        results.append(self._cr(rubric, "concepts",
                                1.0 if cov >= 0.99 else (0.5 if cov >= 0.5 else 0.0),
                                "conceptos %d/%d" % (len(hits), len(required))))
        if cov < 0.5 and required:
            errors.append(ERR.classify("CONCEPT_ERROR", "concepts"))
        claims.append(self._claim("Respuesta abierta del estudiante", "FACTUAL",
                                  list(ev)[:2], ev, forms))
        results.append(self._cr(rubric, "reasoning", 0.5, "asistencia LLM o revision"))
        results.append(self._cr(rubric, "completeness", 0.5 if cov >= 0.5 else 0.0, ""))
        self._rest_zero(rubric, results, ["concepts", "formula", "reasoning",
                                          "completeness"])
        return results, errors, claims, [], [], []

    # ---------- helpers ----------
    def _llm_assist(self, q, analyzed, ev_texts, results, errors, provider) -> None:
        """Asistencia acotada (§18, §74): el LLM solo CONFIRMA o pide REVIEW en
        criterios de razonamiento/interpretacion. Nunca sube un 0 determinista
        ni baja un 1: el validador determinista siempre gana."""
        from pathlib import Path as _P
        if provider is None:
            try:
                from app.llm.gemini import select_provider
                provider = select_provider("auto")
            except RuntimeError:
                return
        from app.llm.interface import Message
        try:
            system = (_P(__file__).resolve().parent / "prompts"
                      / "correction_assist_v1.txt").read_text(encoding="utf-8")
        except OSError:
            return
        import json as _j
        ev_list = [{"id": k, "text": v[:800]} for k, v in list(ev_texts.items())[:6]]
        user = "PREGUNTA: %s\nRESPUESTA: %s\nEVIDENCIA: %s" % (
            q.get("prompt", "")[:800], (analyzed.raw or "")[:1500],
            _j.dumps(ev_list, ensure_ascii=False)[:4000])
        try:
            resp = provider.generate([Message("system", system), Message("user", user)],
                                     temperature=0.0, max_tokens=600)
            payload = _j.loads(resp.text[resp.text.find("{"):resp.text.rfind("}") + 1])
        except Exception:
            return
        for hint in payload.get("hints", [])[:6]:
            if not isinstance(hint, dict):
                continue
            cid = {"REASONING": "reasoning", "INTERPRETATION": "interpretation"}.get(
                str(hint.get("criterion", "")).upper())
            eids = [e for e in hint.get("evidence_ids", []) if e in ev_texts]
            if not cid or not eids:
                continue
            if str(hint.get("assessment", "")).lower() == "review":
                # Solo criterios de razonamiento/interpretacion (nunca puntuan
                # 1.0 en determinista): el LLM puede pedir revision, jamas
                # decidir nota. Un 1.0 determinista jamas se toca aqui.
                for r in results:
                    if r.criterion_id != cid or r.score >= 0.999:
                        continue
                    r.score = 0.5
                    r.status = "PARTIALLY_SUPPORTED"
                    r.detail = "LLM solicita revision: %s" % str(
                        hint.get("detail", ""))[:160]
                    r.source = "llm-assisted"
                    if not any(e.error_type == "AMBIGUOUS_ANSWER" for e in errors):
                        errors.append(ERR.classify("AMBIGUOUS_ANSWER", cid))

    # ---------- helpers ----------
    def _cr(self, rubric, cid, score, detail):
        c = next((x for x in rubric.criteria if x.criterion_id == cid), None)
        ctype = c.ctype if c else cid.upper()
        required = bool(c.required) if c else False
        return CriterionResult(cid, ctype, float(score), 1.0,
                               "SUPPORTED" if score >= 0.999 else (
                                   "PARTIALLY_SUPPORTED" if score > 0 else "UNSUPPORTED"),
                               "", detail[:200], "deterministic", required)

    def _rest_zero(self, rubric, results, skip):
        have = {r.criterion_id for r in results}
        for c in rubric.criteria:
            if c.criterion_id not in have and c.criterion_id not in skip:
                results.append(CriterionResult(c.criterion_id, c.ctype, 0.0, 1.0,
                                               "UNSUPPORTED", "", "no evaluado",
                                               "deterministic"))

    def _claim(self, text, ctype, ev_ids, ev, forms):
        from app.reasoning.models import Claim as RC
        rc = RC(text=text[:800], type=ctype, evidence_ids=[e for e in ev_ids if e in ev])
        self.claims.verify(rc, ev, forms)
        from .models import CorrectionClaim as CC
        return CC(text=rc.text, type=rc.type, status=rc.status,
                  evidence_ids=rc.evidence_ids)

    def _feedback(self, errors, results):
        bad = [e for e in errors if not e.derived_from]
        points = []
        for e in bad[:6]:
            points.append({"error": e.error_type, "severity": e.severity,
                           "why": e.evidence or e.criterion,
                           "how_to_fix": _FIX_HINTS.get(e.error_type, "revisa la evidencia citada")})
        good = [r.criterion_id for r in results if r.score >= 0.999]
        return {"what_was_correct": good,
                "what_was_wrong": [e.error_type for e in bad],
                "points": points,
                "feedback_version": "feedback-5.0"}


_FIX_HINTS = {
    "FORMULA_ERROR": "La fórmula utilizada no coincide con la canónica citada en la evidencia.",
    "ARITHMETIC_ERROR": "Revisa las operaciones aritméticas paso a paso.",
    "ROUNDING_ERROR": "El cálculo es correcto salvo redondeo; conserva más cifras intermedias.",
    "UNIT_ERROR": "Comprueba la unidad esperada y las conversiones.",
    "DIMENSION_ERROR": "Las dimensiones no cuadran: revisa la fórmula.",
    "SIGN_ERROR": "Revisa los signos en la sustitución.",
    "VARIABLE_ERROR": "Comprueba el significado de cada variable en el material.",
    "CONCEPT_ERROR": "Repasa la definición del concepto en la sección citada.",
    "WRONG_FINAL_RESULT": "El resultado no coincide con el cálculo determinista.",
    "INCOMPLETE_ANSWER": "Faltan elementos obligatorios de la respuesta.",
}
