"""Review seguro (Fase 7 Bloque 5): RESULT/REVIEW/MASTERY sobre datos existentes.

Autoridad unica de acceso (matriz B4 §8) + proyeccion por whitelist
(INTERNAL -> vistas, jamas Correction.__dict__). Determinista total,
sin LLM (explainer OFF), sin writes, sin cache, sin store propio.
"""
from __future__ import annotations

import json
import sqlite3

from app.correction.errors import PROPAGATION

from .models import ExamError, exam_attempt_id
from .review_policy import effective_policy

# ---------------------------------------------------------------- autoridad
# B4 §8 + D103. STEM pre-IN_PROGRESS DENY (incluye prompt); RESULT solo con
# fila; REVIEW solo GRADED+COMPLETE; MASTERY resumen propio solo GRADED.
_RULES: dict[tuple[str, str], str] = {}
for _s in ("CREATED", "READY", "SUBMITTED", "EXPIRED", "GRADED",
           "CANCELLED"):
    _RULES[("STEM", _s)] = "DENY"
    _RULES[("RESULT", _s)] = "DENY"
    _RULES[("REVIEW", _s)] = "DENY"
    _RULES[("MASTERY", _s)] = "DENY"
_RULES[("STEM", "IN_PROGRESS")] = "ALLOW"
_RULES[("RESULT", "GRADED")] = "ALLOW"
_RULES[("RESULT", "SUBMITTED")] = "CONDITIONAL"
_RULES[("REVIEW", "GRADED")] = "CONDITIONAL"
_RULES[("MASTERY", "GRADED")] = "ALLOW"

_MARKERS = {"STEM": "STEM_NOT_AVAILABLE", "RESULT": "RESULT_NOT_AVAILABLE",
            "REVIEW": "REVIEW_NOT_AVAILABLE", "MASTERY": "MASTERY_NOT_AVAILABLE"}


class ReviewNotAvailable(ExamError):
    pass


class MasteryNotAvailable(ExamError):
    pass


def check_view(view: str, status: str, *, has_result: bool = False,
               complete: bool = False) -> bool:
    """True o ExamError con marcador. RESULT: SUBMITTED exige fila.
    REVIEW: GRADED exige COMPLETE (D104). Sin condiciones dispersas."""
    if view not in _MARKERS:
        raise ExamError("vista desconocida: %r" % view)
    rule = _RULES.get((view, status), "DENY")
    if rule == "ALLOW":
        if view == "REVIEW" and not complete:
            raise ReviewNotAvailable(
                "REVIEW_NOT_AVAILABLE: resultado INCOMPLETE")
        return True
    if rule == "CONDITIONAL":
        if view == "RESULT" and has_result:
            return True
        if view == "REVIEW" and complete:
            return True
    raise ExamError("%s (estado %s)" % (_MARKERS[view], status))


# ---------------------------------------------------------------- i18n fija
# Diccionarios versionados con la policy (D110). Solo literales humanos
# cambian de idioma; formulas/unidades/numeros/refs son byte-identicos.
ERROR_HUMAN = {
    "CONCEPT_ERROR": ("error de concepte", "error de concepto"),
    "FORMULA_ERROR": ("error de fórmula", "error de fórmula"),
    "VARIABLE_ERROR": ("error de variable", "error de variable"),
    "UNIT_ERROR": ("error d'unitats", "error de unidades"),
    "DIMENSION_ERROR": ("error de dimensions", "error de dimensiones"),
    "SIGN_ERROR": ("error de signe", "error de signo"),
    "ARITHMETIC_ERROR": ("error aritmètic", "error aritmético"),
    "ALGEBRA_ERROR": ("error algebraic", "error algebraico"),
    "ROUNDING_ERROR": ("error d'arrodoniment", "error de redondeo"),
    "REASONING_ERROR": ("error de raonament", "error de razonamiento"),
    "INTERPRETATION_ERROR": ("error d'interpretació", "error de interpretación"),
    "INCOMPLETE_ANSWER": ("resposta incompleta", "respuesta incompleta"),
    "AMBIGUOUS_ANSWER": ("resposta ambigua", "respuesta ambigua"),
    "NO_JUSTIFICATION": ("manca de justificació", "falta de justificación"),
    "WRONG_METHOD": ("mètode inadequat", "método inadecuado"),
    "WRONG_FINAL_RESULT": ("resultat final incorrecte",
                           "resultado final incorrecto"),
}
BAND_HUMAN = {"MINOR": ("lleu", "leve"), "MODERATE": ("mitjana", "media"),
              "MAJOR": ("alta", "alta"), "CRITICAL": ("crítica", "crítica")}
FIX_HINT = {
    "FORMULA_ERROR": ("La fórmula utilitzada no coincideix amb la canònica "
                      "citada en l'evidència.",
                      "La fórmula utilizada no coincide con la canónica "
                      "citada en la evidencia."),
    "ARITHMETIC_ERROR": ("Repasa les operacions aritmètiques pas a pas.",
                         "Revisa las operaciones aritméticas paso a paso."),
    "ROUNDING_ERROR": ("El càlcul és correcte excepte l'arrodoniment; "
                       "conserva més xifres intermèdies.",
                       "El cálculo es correcto salvo redondeo; conserva más "
                       "cifras intermedias."),
    "UNIT_ERROR": ("Comprova la unitat esperada i les conversions.",
                   "Comprueba la unidad esperada y las conversiones."),
    "DIMENSION_ERROR": ("Les dimensions no quadren: repasa la fórmula.",
                        "Las dimensiones no cuadran: revisa la fórmula."),
    "SIGN_ERROR": ("Repasa els signes en la substitució.",
                   "Revisa los signos en la sustitución."),
    "VARIABLE_ERROR": ("Comprova el significat de cada variable en "
                       "el material.",
                       "Comprueba el significado de cada variable en "
                       "el material."),
    "CONCEPT_ERROR": ("Repasa la definició del concepte en la secció citada.",
                      "Repasa la definición del concepto en la sección citada."),
    "WRONG_FINAL_RESULT": ("El resultat no coincideix amb el càlcul "
                           "determinista.",
                           "El resultado no coincide con el cálculo "
                           "determinista."),
    "INCOMPLETE_ANSWER": ("Falten elements obligatoris de la resposta.",
                          "Faltan elementos obligatorios de la respuesta."),
    "ALGEBRA_ERROR": ("Repasa les manipulacions algebraiques pas a pas.",
                      "Revisa las manipulaciones algebraicas paso a paso."),
    "REASONING_ERROR": ("Repasa el raonament: cada pas ha de basar-se en "
                        "l'evidència.",
                        "Repasa el razonamiento: cada paso debe apoyarse en "
                        "la evidencia."),
    "INTERPRETATION_ERROR": ("Rellegeix l'enunciat: interpreta què es demana "
                             "exactament.",
                             "Relee el enunciado: interpreta qué se pide "
                             "exactamente."),
    "AMBIGUOUS_ANSWER": ("Concreta la resposta: era ambigua o il·legible.",
                         "Concreta la respuesta: era ambigua o ilegible."),
    "NO_JUSTIFICATION": ("Afegeix justificació: el resultat sol no basta.",
                         "Añade justificación: el resultado solo no basta."),
    "WRONG_METHOD": ("El mètode no és l'adequat per a aquest problema.",
                     "El método no es el adecuado para este problema."),
}
_FALLBACK_HINT = ("repasa l'evidència citada", "revisa la evidencia citada")
_STATUS_LINE = {
    "CORRECT": ("Resposta correcta.", "Respuesta correcta."),
    "PARTIALLY_CORRECT": ("Parcialment correcta: revisa els punts indicats.",
                          "Parcialmente correcta: revisa los puntos indicados."),
    "INCORRECT": ("Incorrecta: revisa l'error principal.",
                  "Incorrecta: revisa el error principal."),
    "NO_ANSWER": ("Sense resposta: compta 0 punts.",
                  "Sin respuesta: cuenta 0 puntos."),
    "INSUFFICIENT_EVIDENCE": ("Evidència insuficient: requereix revisió manual.",
                              "Evidencia insuficiente: requiere revisión manual."),
}
_ABSTAIN = ("NEEDS_REVIEW", "UNGRADABLE")


def _lang_index(lang: str) -> int:
    return 0 if lang == "ca" else 1


# ---------------------------------------------------------------- feedback
def build_feedback(correction: dict, question: dict, *,
                   params: dict, answer: str = "",
                   formula_lookup=None) -> dict:
    """Correction+pregunta+respuesta -> StudentFeedback (whitelist)."""
    lang = params.get("feedback_lang", "ca")
    li = _lang_index(lang)
    prov = {"correction_id": correction.get("correction_id", ""),
            "attempt_id": correction.get("attempt_id", ""),
            "question_id": correction.get("question_id", ""),
            "provider": correction.get("provider", ""),
            "model": correction.get("model", ""),
            "grader_version": correction.get("grader_version", ""),
            "rubric_version": correction.get("rubric_version", "")}
    base = {"status": correction.get("status", ""), "score": None,
            "student_answer": None, "correct_answer": None, "solution": None,
            "formula": None, "source": None, "errors": [], "guidance": [],
            "explanation": None, "feedback_version": "feedback-5.0",
            "lang": lang, "provenance": prov}
    if correction.get("status") in _ABSTAIN:
        base["status"] = "INSUFFICIENT_EVIDENCE"
        base["explanation"] = _STATUS_LINE["INSUFFICIENT_EVIDENCE"][li]
        return base
    if params.get("reveal_score"):
        base["score"] = correction.get("score", 0.0)
    if params.get("reveal_student_answer"):
        base["student_answer"] = answer
    if params.get("reveal_correct_answer"):
        base["correct_answer"] = _correct_presentation(question)
    if params.get("reveal_solution"):
        base["solution"] = _solution_presentation(question)
    fids = question.get("formula_ids", []) or []
    if fids:
        base["formula"] = {"formula_id": fids[0]}
        if params.get("reveal_formula") and formula_lookup is not None:
            rec = formula_lookup(fids[0])
            if rec is not None:
                base["formula"] = {
                    "formula_id": fids[0], "latex": rec.get("expression", ""),
                    "topic": rec.get("topic"), "section": rec.get("section",
                                                                  ""),
                    "variables": rec.get("variables", []),
                    "document": rec.get("document", "")}
    if params.get("reveal_source"):
        base["source"] = {"topic": question.get("topic"),
                          "section": question.get("section", "")}
    if params.get("reveal_errors"):
        base["errors"], base["guidance"] = _present_errors(
            correction.get("detected_errors", []) or [], lang)
    base["explanation"] = _STATUS_LINE.get(
        correction.get("status"), _STATUS_LINE["INSUFFICIENT_EVIDENCE"])[li]
    return base


def _correct_presentation(question: dict):
    t = question.get("type", "")
    if t == "MULTIPLE_CHOICE":
        for i, o in enumerate(question.get("options", []) or []):
            if isinstance(o, dict) and o.get("correct"):
                return {"letter": chr(65 + i), "text": o.get("text", "")}
        return None
    if t in ("TRUE_FALSE",):
        return question.get("correct_answer", "")
    return question.get("correct_answer", "") or \
        question.get("expected_answer", "")


def _solution_presentation(question: dict):
    t = question.get("type", "")
    sol = question.get("solution", {}) or {}
    if t in ("FORMULA", "NUMERICAL", "MULTI_STEP"):
        calc = sol.get("calculation", {}) or {}
        return {"final_answer": sol.get("final_answer", ""),
                "reasoning_steps": sol.get("reasoning_steps", []),
                "formula_application": sol.get("formula_application", []),
                "calculation": {"result": calc.get("result"),
                                "verified": calc.get("verified"),
                                "unit": calc.get("unit", "")},
                "interpretation": sol.get("interpretation", "")}
    if t in ("MULTIPLE_CHOICE", "TRUE_FALSE"):
        return {"correct_selection": _correct_presentation(question)}
    return {"expected_answer": sol.get("final_answer", "") or
            question.get("expected_answer", ""),
            "reasoning_steps": sol.get("reasoning_steps", [])}


def _present_errors(errors: list, lang: str) -> tuple:
    li = _lang_index(lang)
    present = [e for e in errors if isinstance(e, dict)]
    present.sort(key=lambda e: (not e.get("root_cause", False),
                                e.get("error_type", "")))
    attached: set[int] = set()
    out, guidance = [], []
    for i, e in enumerate(present):
        if i in attached:
            continue
        et = e.get("error_type", "")
        if not e.get("root_cause", False) and not _is_orphan(e, present):
            continue  # se muestra bajo su raiz
        cons = []
        for j, d in enumerate(present):
            if j in attached or j == i:
                continue
            if d.get("derived_from", "") == et or (
                    not d.get("derived_from", "") and d.get("error_type", "")
                    in PROPAGATION.get(et, set())):
                cons.append(d.get("error_type", ""))
                attached.add(j)
        sev = e.get("severity", "MODERATE")
        out.append({"type": et, "human": ERROR_HUMAN.get(et, (et, et))[li],
                    "severity_band": BAND_HUMAN.get(sev, ("mitjana",
                                                          "media"))[li],
                    "root": bool(e.get("root_cause", False)),
                    "consequences": sorted(cons)})
        guidance.append({"for_error": et,
                         "hint": FIX_HINT.get(et, _FALLBACK_HINT)[li]})
    return out, guidance


def _is_orphan(e: dict, present: list) -> bool:
    if e.get("root_cause", False):
        return False
    if e.get("derived_from", ""):
        return not any(p.get("error_type", "") == e["derived_from"]
                       for p in present)
    for p in present:
        if p.get("root_cause", False) and e.get("error_type", "") in \
                PROPAGATION.get(p.get("error_type", ""), set()):
            return False
    return True


def _is_orphan(e: dict, present: list) -> bool:
    if e.get("root_cause", False):
        return False
    if e.get("derived_from", ""):
        return not any(p.get("error_type", "") == e["derived_from"]
                       for p in present)
    for p in present:
        if p.get("root_cause", False) and e.get("error_type", "") in \
                PROPAGATION.get(p.get("error_type", ""), set()):
            return False
    return True


# ---------------------------------------------------------------- servicio
BAND_STATUS = {"MASTERED": 0, "PROFICIENT": 0, "DEVELOPING": 1,
               "EMERGING": 2, "AT_RISK": 2, "UNKNOWN": 2}
_BAND_HUMAN = {0: ("sòlid", "sólido"), 1: ("practicar", "practicar"),
               2: ("revisar", "revisar")}


class ExamReviewService:
    """Vistas REVIEW/MASTERY (derivadas, sin store, sin writes, sin LLM).

    Cableado: exam_service (sesiones), grading_service (resultados),
    student_service (corrections/questions/mastery, solo lectura),
    kb_path (formulas/canónicas, solo lectura).
    """

    def __init__(self, exam_service, grading_service, student_service,
                 kb_path: str) -> None:
        self.exam = exam_service
        self.grading = grading_service
        self.stu = student_service
        self.kb_path = kb_path

    # ---------- primitivas de lectura (SELECT puros) ----------
    def _correction_body(self, correction_id: str) -> dict:
        con = sqlite3.connect("file:%s?mode=ro" % self.stu.store.path,
                              uri=True)
        try:
            row = con.execute("SELECT body_json FROM corrections WHERE "
                              "correction_id=?", (correction_id,)).fetchone()
        finally:
            con.close()
        if not row:
            raise ExamError("correction inexistente: %r" % correction_id)
        return json.loads(row[0])

    def _formula_record(self, fid: str) -> dict | None:
        from app.examiner.evidence import EvidenceError, formula_record
        try:
            rec = formula_record(self.kb_path, fid)
        except EvidenceError:
            return None
        return {"expression": rec.get("expression", ""),
                "topic": rec.get("topic"),
                "section": rec.get("section_h2", ""),
                "variables": [v for v in (rec.get("variables", []) or [])
                              if isinstance(v, str)][:12],
                "document": rec.get("doc_title", "") or
                rec.get("h1", "")}

    def _doc_title(self, source_path: str) -> str:
        if not source_path:
            return ""
        con = sqlite3.connect("file:%s?mode=ro" % self.kb_path, uri=True)
        try:
            row = con.execute(
                "SELECT d.title FROM documents d JOIN sources s ON"
                " s.id=d.source_id WHERE s.path=?", (source_path,)).fetchone()
        finally:
            con.close()
        return row[0] if row else ""

    def _question_topic(self, student_id: str, unit_id: str) -> int | None:
        kind, _, ref = unit_id.partition(":")
        if kind in ("topic", "section"):
            try:
                return int(ref[1:3])
            except (ValueError, IndexError):
                return None
        if kind == "formula":
            rec = self._formula_record(ref)
            return rec.get("topic") if rec else None
        if kind == "concept":
            hist = self.stu.get_unit_history(student_id, unit_id)
            for e in reversed(hist.get("events", []) or []):
                try:
                    q = self.stu.correction.load_question(
                        e.get("question_id") or "")
                except (KeyError, ValueError):
                    continue
                if isinstance(q.get("topic"), int):
                    return q["topic"]
            return None
        return None

    # ---------- review ----------
    def _review_context(self, session_id: str, student_id: str,
                        policy_version: str = "") -> tuple:
        data = self.exam.read_session(session_id, student_id)
        sess = data["session"]
        try:
            result = self.grading.get_result(session_id, student_id)
        except ExamError:
            raise ExamError("REVIEW_NOT_AVAILABLE: sin resultado "
                            "(GRADING_INCOMPLETE?)")
        check_view("REVIEW", sess["status"],
                   complete=(result.get("status") == "COMPLETE"))
        if result.get("status") != "COMPLETE":
            raise ExamError("REVIEW_NOT_AVAILABLE: resultado INCOMPLETE")
        policy = effective_policy(sess["exam_kind"], policy_version)
        return data, result, policy

    def get_review(self, session_id: str, student_id: str,
                   policy_version: str = "") -> dict:
        data, result, policy = self._review_context(
            session_id, student_id, policy_version)
        params = policy["parameters"]
        out = []
        for q in result["questions"]:
            out.append(self._review_one(data, q, params))
        return {"session_id": session_id, "exam_id": result["exam_id"],
                "title": result.get("title", ""),
                "exam_kind": result["exam_kind"],
                "origin_status": result["origin_status"],
                "percentage": result["percentage"],
                "graded_at": result["graded_at"], "policy": policy,
                "result": {k: result[k] for k in
                           ("status", "total_points", "earned_points",
                            "percentage", "question_count", "answered_count",
                            "blank_count", "correct_count", "partial_count",
                            "incorrect_count")},
                "questions": out}

    def get_review_question(self, session_id: str, position: int,
                            student_id: str,
                            policy_version: str = "") -> dict:
        data, result, policy = self._review_context(
            session_id, student_id, policy_version)
        hits = [q for q in result["questions"]
                if q["position"] == position]
        if not hits:
            raise ExamError("position inexistente o ajena: %r" % position)
        return self._review_one(data, hits[0], policy["parameters"])

    def _review_one(self, data: dict, q: dict, params: dict) -> dict:
        corr = self._correction_body(q["correction_id"])
        try:
            body = self.stu.correction.load_question(q["question_id"])
        except KeyError:
            raise ExamError("pregunta inexistente: %r" % q["question_id"])
        ans = data["answers"].get(q["position"], {}).get("answer", "")
        fb = build_feedback(corr, body, params=params, answer=ans,
                            formula_lookup=self._formula_record)
        if params.get("reveal_source") and fb.get("source") is not None:
            refs = body.get("source_refs", []) or []
            if refs and isinstance(refs[0], dict):
                fb["source"]["document"] = self._doc_title(
                    refs[0].get("source_path", ""))
        return {"position": q["position"], "question_id": q["question_id"],
                "question_version": q.get("question_version", ""),
                "type": body.get("type", ""),
                "difficulty": body.get("difficulty", ""),
                "prompt": body.get("prompt", ""),
                "options": [{"text": o.get("text", "")} for o in
                            body.get("options", []) or []
                            if isinstance(o, dict) and "text" in o],
                "points_available": q.get("points_available", "0.000"),
                "points_earned": q.get("points_earned", "0.000"),
                "feedback": fb}

    # ---------- mastery (solo lectura) ----------
    def get_mastery_view(self, student_id: str, session_id: str,
                         policy_version: str = "") -> dict:
        data = self.exam.read_session(session_id, student_id)
        sess = data["session"]
        check_view("MASTERY", sess["status"])
        policy = effective_policy(sess["exam_kind"], policy_version)
        li = 0 if policy["parameters"].get("feedback_lang",
                                            "ca") == "ca" else 1
        units: dict[str, dict] = {}
        for pos, a in sorted(data["answers"].items()):
            aid = exam_attempt_id(session_id, pos, a["question_id"],
                                  a.get("answer", ""))
            for e in self._events_of(aid):
                u = e["unit"]
                slot = units.setdefault(u, {"roots": {}, "n": 0})
                slot["n"] += 1
                for r in e["roots"]:
                    slot["roots"][r] = slot["roots"].get(r, 0) + 1
        items = []
        for uid in sorted(units):
            st = self.stu.get_mastery(student_id, uid) or {}
            status = st.get("status", "UNKNOWN")
            roots = units[uid]["roots"]
            main = sorted(roots.items(), key=lambda kv: (-kv[1], kv[0]))
            items.append({
                "knowledge_unit_id": uid,
                "unit_kind": uid.split(":")[0],
                "topic": self._question_topic(student_id, uid),
                "mastery_status": status,
                "band": _BAND_HUMAN[BAND_STATUS.get(status, 2)][li],
                "evidence": {"attempts": st.get("attempt_count", 0),
                             "correct": st.get("correct_count", 0)},
                "confidence": round(float(st.get("confidence", 0.0)), 4),
                "main_error": main[0][0] if main else "",
                "main_error_human": ERROR_HUMAN.get(
                    main[0][0], (main[0][0], main[0][0]))[li] if main else ""})
        return {"student_id": student_id, "session_id": session_id,
                "policy": {"policy_id": policy["policy_id"],
                           "policy_version": policy["policy_version"]},
                "units": items}

    def _events_of(self, attempt_id: str) -> list[dict]:
        con = sqlite3.connect("file:%s?mode=ro" % self.stu.store.path,
                              uri=True)
        try:
            rows = con.execute("SELECT knowledge_unit_id, evidence_json FROM"
                               " mastery_events WHERE attempt_id=?",
                               (attempt_id,)).fetchall()
        finally:
            con.close()
        out = []
        for uid, blob in rows:
            try:
                ev = json.loads(blob or "{}")
            except ValueError:
                ev = {}
            out.append({"unit": uid,
                        "roots": ev.get("root_errors", []) or []})
        return out
