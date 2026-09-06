"""Modelos del Corrector (§7-23). Corrección ≠ mastery (separados por diseño)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

GRADER_VERSION = "grader-5.0"
RUBRIC_VERSION = "rubric-5.0"

CORRECTNESS = ("CORRECT", "PARTIALLY_CORRECT", "INCORRECT", "NEEDS_REVIEW",
               "UNGRADABLE", "NO_ANSWER")
ERROR_TYPES = ("CONCEPT_ERROR", "FORMULA_ERROR", "VARIABLE_ERROR", "UNIT_ERROR",
               "DIMENSION_ERROR", "SIGN_ERROR", "ARITHMETIC_ERROR", "ALGEBRA_ERROR",
               "ROUNDING_ERROR", "REASONING_ERROR", "INTERPRETATION_ERROR",
               "INCOMPLETE_ANSWER", "AMBIGUOUS_ANSWER", "NO_JUSTIFICATION",
               "WRONG_METHOD", "WRONG_FINAL_RESULT")
SEVERITY = ("MINOR", "MODERATE", "MAJOR", "CRITICAL")
CRITERION_TYPES = ("CONCEPT", "FORMULA", "VARIABLES", "UNITS", "CALCULATION",
                   "REASONING", "INTERPRETATION", "FINAL_RESULT", "COMPLETENESS",
                   "PRECISION")


@dataclass
class RubricCriterion:
    criterion_id: str
    name: str
    description: str
    weight: float
    required: bool = False
    ctype: str = "CONCEPT"


@dataclass
class Rubric:
    rubric_id: str
    version: str
    question_type: str
    criteria: list[RubricCriterion]
    passing_score: float = 0.5


@dataclass
class CriterionResult:
    criterion_id: str
    ctype: str
    score: float  # 0..1
    max_score: float = 1.0
    status: str = "UNSUPPORTED"
    evidence_ref: str = ""
    detail: str = ""
    source: str = "deterministic"  # deterministic | llm-assisted
    required: bool = False


@dataclass
class DetectedError:
    error_type: str
    severity: str
    criterion: str = ""
    evidence: str = ""
    root_cause: bool = False
    derived_from: str = ""


@dataclass
class CorrectionClaim:
    text: str
    type: str
    status: str = "UNKNOWN"
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class Correction:
    correction_id: str
    attempt_id: str
    question_id: str
    question_version: str
    score: float
    max_score: float
    percentage: float
    status: str
    exam_id: str = ""
    session_id: str = ""
    provider: str = ""
    model: str = ""
    criteria_results: list[CriterionResult] = field(default_factory=list)
    detected_errors: list[DetectedError] = field(default_factory=list)
    claims: list[CorrectionClaim] = field(default_factory=list)
    formula_results: list[dict] = field(default_factory=list)
    calculation_results: list[dict] = field(default_factory=list)
    unit_results: list[dict] = field(default_factory=list)
    feedback: dict = field(default_factory=dict)
    provenance: list[dict] = field(default_factory=list)
    grader_version: str = GRADER_VERSION
    rubric_version: str = RUBRIC_VERSION
    rubric_snapshot: dict = field(default_factory=dict)
    reasoning_version: str = "reasoning-3.0"
    knowledge_version: str = ""
    prompt_version: str = ""
    mastery_policy_version: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StudentAnswer:
    attempt_id: str
    student_id: str
    question_id: str
    exam_id: str = ""
    answer: str = ""
    seed: str = ""


# Rúbricas canónicas por tipo (pesos explícitos, §16; versionadas por contenido).
def rubric_for(question_type: str) -> Rubric:
    if question_type == "NUMERICAL":
        criteria = [
            ("formula", "Fórmula canónica", 0.20, True, "FORMULA"),
            ("variables", "Uso de variables", 0.15, False, "VARIABLES"),
            ("substitution", "Sustitución", 0.15, False, "CALCULATION"),
            ("calculation", "Cálculo", 0.25, True, "CALCULATION"),
            ("units", "Unidades", 0.10, False, "UNITS"),
            ("result", "Resultado final", 0.10, True, "FINAL_RESULT"),
            ("interpretation", "Interpretación", 0.05, False, "INTERPRETATION"),
        ]
    elif question_type in ("MULTIPLE_CHOICE", "TRUE_FALSE"):
        criteria = [
            ("selection", "Selección correcta", 0.70, True, "FINAL_RESULT"),
            ("justification", "Justificación/evidencia", 0.30, False, "REASONING"),
        ]
    elif question_type == "FORMULA":
        criteria = [
            ("formula", "Fórmula exacta o equivalente", 0.60, True, "FORMULA"),
            ("variables", "Variables", 0.20, False, "VARIABLES"),
            ("conditions", "Condiciones", 0.20, False, "CONCEPT"),
        ]
    else:  # THEORY/CONCEPTUAL/SHORT_ANSWER/OPEN/MULTI_STEP
        criteria = [
            ("concepts", "Conceptos requeridos", 0.35, True, "CONCEPT"),
            ("formula", "Fórmulas", 0.20, False, "FORMULA"),
            ("reasoning", "Razonamiento", 0.25, False, "REASONING"),
            ("completeness", "Completitud", 0.20, False, "COMPLETENESS"),
        ]
    return Rubric(rubric_id="rubric-%s-v1" % question_type.lower(),
                  version=RUBRIC_VERSION, question_type=question_type,
                  criteria=[RubricCriterion(criterion_id=c, name=n, description=n,
                                            weight=w, required=r, ctype=t)
                            for c, n, w, r, t in criteria])
