"""Modelos del Examiner Engine (§6-8). Todo trazable, nada inventado."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

EXAMINER_VERSION = "examiner-4.0"

QUESTION_TYPES = ("THEORY", "CONCEPTUAL", "FORMULA", "NUMERICAL",
                  "MULTIPLE_CHOICE", "TRUE_FALSE", "SHORT_ANSWER", "OPEN",
                  "MULTI_STEP")
DIFFICULTIES = ("EASY", "MEDIUM", "HARD", "EXPERT")
QUESTION_ORIGINS = ("GENERATED", "REAL_EXAM", "IMPORTED", "MANUAL")
EXAM_KINDS = ("GENERATED", "REAL_EXAM")
VALIDATION_STATUS = ("VALID", "INVALID", "NEEDS_REVIEW")
VALUE_KINDS = ("SOURCE_VALUE", "DERIVED_VALUE", "GENERATED_TEST_VALUE")
FAILURE_REASONS = ("NO_EVIDENCE", "INSUFFICIENT_EVIDENCE", "FORMULA_NOT_FOUND",
                   "FORMULA_MISMATCH", "VARIABLE_UNSUPPORTED", "UNIT_UNSUPPORTED",
                   "CALCULATION_ERROR", "DIMENSION_ERROR", "INVALID_DOMAIN",
                   "AMBIGUOUS", "UNSUPPORTED_CLAIM", "CONTRADICTED_CLAIM",
                   "DUPLICATE", "INVALID_LLM_OUTPUT", "PROVENANCE_INCOMPLETE",
                   "EVIDENCE_TOPIC_MISMATCH")


@dataclass
class QuestionBlueprint:
    topic: int
    section: str
    question_type: str
    difficulty: str
    learning_objective: str
    formula_ids: list[str] = field(default_factory=list)
    concept_terms: list[str] = field(default_factory=list)
    variables: list[str] = field(default_factory=list)
    units: dict = field(default_factory=dict)
    conditions: list[str] = field(default_factory=list)
    expected_reasoning_steps: list[str] = field(default_factory=list)
    answer_constraints: list[str] = field(default_factory=list)
    seed: int = 0


@dataclass
class QuestionOption:
    text: str
    correct: bool
    distractor_reason: str = ""
    formula_id: str | None = None


@dataclass
class QuestionSolution:
    final_answer: str = ""
    reasoning_steps: list[str] = field(default_factory=list)
    formula_application: list[dict] = field(default_factory=list)
    calculation: dict = field(default_factory=dict)
    interpretation: str = ""


@dataclass
class QuestionClaim:
    text: str
    type: str
    status: str = "UNSUPPORTED"
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class QuestionValidation:
    status: str = "INVALID"
    reasons: list[str] = field(default_factory=list)
    evidence_score: str = "unsupported"
    checks: dict = field(default_factory=dict)


@dataclass
class Question:
    question_id: str
    version: str
    topic: int
    section: str
    type: str
    difficulty: str
    prompt: str
    options: list[QuestionOption] = field(default_factory=list)
    correct_answer: str = ""
    expected_answer: str = ""
    solution: QuestionSolution = field(default_factory=QuestionSolution)
    hints: list[str] = field(default_factory=list)
    formula_ids: list[str] = field(default_factory=list)
    concept_terms: list[str] = field(default_factory=list)
    source_refs: list[dict] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    variables: dict = field(default_factory=dict)
    units: dict = field(default_factory=dict)
    conditions: list[str] = field(default_factory=list)
    claims: list[QuestionClaim] = field(default_factory=list)
    validation: QuestionValidation = field(default_factory=QuestionValidation)
    generator_version: str = EXAMINER_VERSION
    prompt_version: str = ""
    seed: int = 0
    fingerprint: str = ""
    origin: str = "GENERATED"

    def to_dict(self) -> dict:
        return asdict(self)


def fingerprint(topic: int, section: str, qtype: str, objective: str,
                formula_ids: list[str], concepts: list[str], prompt: str) -> str:
    """Fingerprint estable §35: topic|section|type|objective|formulas|concepts|prompt."""
    import unicodedata
    norm = " ".join(prompt.lower().split())
    norm = unicodedata.normalize("NFC", norm)
    payload = "|".join([str(topic), section.strip(), qtype, objective.strip(),
                        ",".join(sorted(formula_ids)), ",".join(sorted(concepts)), norm])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def difficulty_for(n_formulas: int, n_vars: int, steps: int, choices: bool) -> str:
    """Dificultad desde rasgos observables (§8), nunca desde el prompt."""
    score = (2 if n_formulas > 1 else 0) + (1 if n_vars >= 3 else 0) \
        + (2 if steps >= 3 else (1 if steps == 2 else 0)) + (1 if choices else 0)
    if score >= 4:
        return "HARD"
    if score >= 2:
        return "MEDIUM"
    return "EASY"
