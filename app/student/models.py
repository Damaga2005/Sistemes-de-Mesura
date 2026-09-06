"""Modelos de Student Mastery/Memory (§7-8, §44-65). Rendimiento observado,
jamas conocimiento canonico ni diagnostico psicologico (§60, §128).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

MASTERY_POLICY_VERSION = "mastery-policy-v1"

STATUSES = ("UNKNOWN", "EMERGING", "DEVELOPING", "PROFICIENT", "MASTERED", "AT_RISK")


@dataclass
class Attempt:
    attempt_id: str
    student_id: str
    question_id: str
    question_version: str
    exam_id: str = ""
    answer: str = ""
    seed: str = ""


@dataclass
class MasteryState:
    mastery_id: str
    student_id: str
    knowledge_unit_id: str
    # Contrato efectivo Fase 6 (GAP 4, opcion B): topic | section | concept |
    # formula. "skill" se acepta pasivamente por compatibilidad pero ningun
    # productor lo emite: Skill graph -> FUTURO (ver PHASE_6_PREAUDIT).
    unit_kind: str
    score: float = 0.0
    confidence: float = 0.0
    attempt_count: int = 0
    correct_count: int = 0
    incorrect_count: int = 0
    last_attempt: str = ""
    last_correct: str = ""
    error_counts: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MasteryEvent:
    event_id: str
    student_id: str
    question_id: str
    attempt_id: str
    correction_id: str
    knowledge_unit_id: str
    unit_kind: str
    old_score: float
    new_score: float
    old_confidence: float
    new_confidence: float
    reason: str
    evidence: dict = field(default_factory=dict)
    policy_version: str = MASTERY_POLICY_VERSION
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Memory:
    memory_id: str
    student_id: str
    kind: str  # PERFORMANCE (jamas FACTUAL academica)
    text: str
    confidence: float
    evidence_count: int
    last_evidence: str
    attempt_ids: list[str] = field(default_factory=list)
    correction_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
