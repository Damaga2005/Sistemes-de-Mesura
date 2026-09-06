"""Modelos del Adaptive Learning Core (Bloque A). Sin LLM, sin UI."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

ADAPTIVE_VERSION = "adaptive-6a.1"

ACTIONS = ("REVIEW", "PRACTICE", "REINFORCE", "CHALLENGE", "MAINTAIN")
EVIDENCE_LEVELS = ("UNSEEN", "LOW", "MODERATE", "HIGH")


@dataclass(frozen=True)
class LearningPriority:
    knowledge_unit_id: str
    unit_kind: str
    priority_score: float
    mastery: float
    confidence: float
    evidence_level: str
    reasons: tuple = ()
    error_signals: tuple = ()
    recency_signal: float = 0.0
    recommended_action: str = "PRACTICE"
    policy_id: str = "priority-policy"
    policy_version: str = "v1"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(d["reasons"])
        d["error_signals"] = list(d["error_signals"])
        return d


@dataclass(frozen=True)
class LearningPathItem:
    knowledge_unit_id: str
    unit_kind: str
    priority: float
    action: str
    difficulty: str
    target_topic: int | None = None
    target_section: str | None = None
    target_concepts: tuple = ()
    target_formulas: tuple = ()
    reasons: tuple = ()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["target_concepts"] = list(d["target_concepts"])
        d["target_formulas"] = list(d["target_formulas"])
        d["reasons"] = list(d["reasons"])
        return d


@dataclass(frozen=True)
class QuestionSpec:
    topic: int | None = None
    section: str | None = None
    type: str = "CONCEPTUAL"
    difficulty: str = "EASY"
    formula_ids: tuple = ()
    concept_terms: tuple = ()
    seed: int = 0
    origin: str = "GENERATED"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["formula_ids"] = list(d["formula_ids"])
        d["concept_terms"] = list(d["concept_terms"])
        return d


@dataclass(frozen=True)
class Recommendation:
    """Recomendacion final del Builder (Bloque B, §6).

    policy_id/version = spacing-policy (politica propia del Builder);
    source_policies cita las politicas de prioridad y dificultad que
    produjeron priority_score/action/difficulty (trazabilidad completa).
    spacing_state = SpacingState.to_dict(). Sin texto libre de LLM.
    """

    student_id: str
    knowledge_unit_id: str
    unit_kind: str
    priority_score: float
    action: str
    difficulty: str
    reason_codes: tuple = ()
    target_topic: int | None = None
    target_section: str | None = None
    target_concepts: tuple = ()
    target_formulas: tuple = ()
    spacing_state: dict = field(default_factory=dict)
    policy_id: str = "spacing-policy"
    policy_version: str = "v1"
    source_policies: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["reason_codes"] = list(d["reason_codes"])
        d["target_concepts"] = list(d["target_concepts"])
        d["target_formulas"] = list(d["target_formulas"])
        return d
