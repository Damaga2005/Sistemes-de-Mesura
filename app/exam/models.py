"""Modelos Exam Session Core (Fase 7 Bloque 2): especificacion, no ejecucion.

ExamBlueprint = spec reproducible (no preguntas). ExamSession = ejecucion
concreta con maquina de estados cerrada. ExamQuestionInstance = pregunta
congelada por referencia (id+fingerprint, D78). ExamAnswer = respuesta
guardada (vacío "" = NO_ANSWER futuro, nunca LLM).

Sin LLM, determinista total. Vocabularios del Examiner reutilizados.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

from app.examiner.models import DIFFICULTIES, QUESTION_TYPES

EXAM_SPEC_VERSION = "exam-spec-v1"
EXAM_POLICY_ID = "exam-spec"

EXAM_KINDS = ("PRACTICE_EXAM", "MOCK_EXAM", "REAL_EXAM", "IMPORTED_EXAM")
EXAM_STATES = ("CREATED", "READY", "IN_PROGRESS", "EXPIRED", "CANCELLED",
               "SUBMITTED", "GRADED")
ORDERINGS = ("seeded_shuffle", "blueprint_order")

# Unica autoridad de transiciones (§10). GRADED solo vía grading service
# (artefactos completos); PAUSED no existe en v1 (fuera del mapa = error).
TRANSITIONS: dict[str, tuple[str, ...]] = {
    "CREATED": ("READY", "CANCELLED"),
    "READY": ("IN_PROGRESS", "CANCELLED"),
    "IN_PROGRESS": ("SUBMITTED", "EXPIRED", "CANCELLED"),
    "EXPIRED": ("GRADED",),
    "CANCELLED": (),
    "SUBMITTED": ("GRADED",),
    "GRADED": (),
}


class ExamError(Exception):
    """Error explicito de Exam Mode (transicion, snapshot, validacion...)."""


class SnapshotInvalid(ExamError):
    """Fingerprint o cuerpo no coinciden: la sesion NO puede comenzar (§7)."""


def exam_attempt_id(session_id: str, position: int, question_id: str,
                    answer: str) -> str:
    """Attempt determinista por sesion (B3): re-grade rejuega, otra sesion
    no colisiona. Misma forma que F5 para compatibilidad de stores."""
    return "attex-" + hashlib.sha256(
        ("%s|%d|%s|%s" % (session_id, position, question_id,
                           answer)).encode()).hexdigest()[:12]


def transition(current: str, target: str) -> str:
    """Unica autoridad: devuelve target o lanza ExamError explicito.

    GRADED solo lo invoca el grading service tras verificar artefactos;
    el mapa lo permite desde SUBMITTED/EXPIRED y nada mas.
    """
    if current not in TRANSITIONS:
        raise ExamError("estado desconocido: %r" % current)
    if target not in TRANSITIONS[current]:
        raise ExamError("transicion invalida: %s -> %s" % (current, target))
    return target


def _canon(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


@dataclass(frozen=True)
class ExamBlueprint:
    title: str = ""
    version: str = "1"
    seed: int = 0
    duration_seconds: int | None = None
    question_count: int = 0
    topics: tuple = ()
    sections: dict = field(default_factory=dict)
    types: dict = field(default_factory=dict)
    difficulty: dict = field(default_factory=dict)
    required_formula_ids: tuple = ()
    concept_requirements: tuple = ()
    scoring: dict = field(default_factory=dict)
    ordering_policy: str = "seeded_shuffle"
    exam_kind: str = "MOCK_EXAM"
    policy_id: str = EXAM_POLICY_ID
    policy_version: str = EXAM_SPEC_VERSION

    @staticmethod
    def from_dict(d: dict) -> "ExamBlueprint":
        return ExamBlueprint(
            title=d.get("title", ""), version=str(d.get("version", "1")),
            seed=int(d.get("seed", 0)),
            duration_seconds=d.get("duration_seconds"),
            question_count=int(d.get("question_count", 0)),
            topics=tuple(d.get("topics", [])),
            sections={int(k): list(v)
                      for k, v in dict(d.get("sections", {})).items()},
            types=dict(d.get("types", {})),
            difficulty=dict(d.get("difficulty", {})),
            required_formula_ids=tuple(d.get("required_formula_ids", [])),
            concept_requirements=tuple(d.get("concept_requirements", [])),
            scoring=dict(d.get("scoring", {})),
            ordering_policy=d.get("ordering_policy", "seeded_shuffle"),
            exam_kind=d.get("exam_kind", "MOCK_EXAM"),
            policy_id=d.get("policy_id", EXAM_POLICY_ID),
            policy_version=d.get("policy_version", EXAM_SPEC_VERSION))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["topics"] = list(d["topics"])
        d["required_formula_ids"] = list(d["required_formula_ids"])
        d["concept_requirements"] = list(d["concept_requirements"])
        return d

    def canonical(self) -> str:
        return _canon(self.to_dict())

    def exam_id(self) -> str:
        return "exm-" + hashlib.sha256(
            self.canonical().encode()).hexdigest()[:12]

    def validate(self) -> list[str]:
        """Validacion pura de spec (sin pool). [] = valido."""
        errs = []
        if not self.title:
            errs.append("title vacio")
        if not self.version:
            errs.append("version vacia")
        if self.question_count < 1:
            errs.append("question_count debe ser >= 1")
        if not self.topics or any(not isinstance(t, int) for t in self.topics):
            errs.append("topics debe ser lista no vacia de enteros")
        for t in self.types:
            if t not in QUESTION_TYPES:
                errs.append("tipo desconocido: %r" % t)
        if self.types and sum(self.types.values()) != self.question_count:
            errs.append("suma de tipos %d != question_count %d"
                        % (sum(self.types.values()), self.question_count))
        for lv in self.difficulty:
            if lv not in DIFFICULTIES:
                errs.append("dificultad desconocida: %r" % lv)
        if self.difficulty and abs(sum(self.difficulty.values()) - 1.0) > 0.02:
            errs.append("difficulty debe sumar 1.0 (±0.02)")
        if self.duration_seconds is not None and (
                not isinstance(self.duration_seconds, int)
                or self.duration_seconds < 1):
            errs.append("duration_seconds debe ser null o entero >= 1")
        if self.ordering_policy not in ORDERINGS:
            errs.append("ordering desconocido: %r" % self.ordering_policy)
        if self.exam_kind not in EXAM_KINDS:
            errs.append("exam_kind desconocido: %r" % self.exam_kind)
        if self.policy_id != EXAM_POLICY_ID \
                or self.policy_version != EXAM_SPEC_VERSION:
            errs.append("policy debe ser %s@%s"
                        % (EXAM_POLICY_ID, EXAM_SPEC_VERSION))
        sc = self.scoring
        if sc:
            dp = sc.get("default_points", 1.0)
            if isinstance(dp, bool) or not isinstance(dp, (int, float)) \
                    or dp <= 0:
                errs.append("scoring.default_points debe ser > 0")
            if "required_default" in sc and not isinstance(
                    sc["required_default"], bool):
                errs.append("scoring.required_default debe ser bool")
            if sc.get("required_default", True) is False:
                errs.append("optional sin regla implementada: ABSTAIN "
                            "(este bloque no inventa penalizaciones)")
        for c in self.concept_requirements:
            if not isinstance(c, dict) or not c.get("term"):
                errs.append("concept_requirements: {term, ...} con term")
        return errs


@dataclass(frozen=True)
class ExamSession:
    session_id: str
    exam_id: str
    student_id: str
    exam_kind: str
    status: str
    seed: int
    exam_version: str
    policy_versions: dict = field(default_factory=dict)
    duration_seconds: int | None = None
    started_at: str = ""
    submitted_at: str = ""
    cancelled_at: str = ""
    expires_at: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ExamQuestionInstance:
    session_id: str
    position: int
    question_id: str
    question_version: str
    fingerprint: str
    body_sha: str = ""
    points: float = 1.0
    required: bool = True
    blueprint_slot: str = ""
    seed: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ExamAnswer:
    session_id: str
    position: int
    question_id: str
    answer: str = ""
    saved_at: str = ""
    version: int = 1

    def to_dict(self) -> dict:
        return asdict(self)


# Vista STEM (§18): whitelist estricta. Todo lo demas (solution,
# correct_answer, expected_answer, claims, evidence, validation,
# concept_terms, formula_ids en opciones) jamas sale en examen activo.
STEM_FIELDS = ("position", "question_id", "question_version", "prompt",
               "options", "variables", "conditions", "type", "difficulty",
               "points", "required", "session_id")
OPTION_VIEW_FIELDS = ("text",)


def stem_view(question_body: dict, *, position: int, question_version: str,
              points: float, required: bool, session_id: str) -> dict:
    """Cuerpo canonico -> vista segura. Falla cerrado ante tipo raro."""
    opts = []
    for o in question_body.get("options", []) or []:
        if isinstance(o, dict) and "text" in o:
            opts.append({"text": o["text"]})
    return {"position": position,
            "question_id": question_body.get("question_id", ""),
            "question_version": question_version,
            "prompt": question_body.get("prompt", ""),
            "options": opts,
            "variables": question_body.get("variables", {}),
            "conditions": question_body.get("conditions", []),
            "type": question_body.get("type", ""),
            "difficulty": question_body.get("difficulty", ""),
            "points": points, "required": required, "session_id": session_id}
