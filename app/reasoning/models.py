"""Modelos del Reasoning Engine (§45-48). Sin dependencias de proveedor."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

CONFIDENCE_LEVELS = ("VERIFIED", "SUPPORTED", "PARTIAL", "UNCERTAIN", "ABSTAIN")
FORMULA_STATUS = ("EXACT_MATCH", "EQUIVALENT_MATCH", "MISSING", "MISMATCH")
CLAIM_STATUS = ("SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "CONTRADICTED")
ABSTAIN_TYPES = ("NO_EVIDENCE", "INSUFFICIENT_EVIDENCE", "AMBIGUOUS",
                 "CONFLICTING_EVIDENCE", "UNSUPPORTED_FORMULA", "UNSUPPORTED_VARIABLE",
                 "UNSUPPORTED_UNIT", "CALCULATION_UNCERTAIN")


@dataclass
class Claim:
    text: str
    type: str
    evidence_ids: list[str] = field(default_factory=list)
    status: str = "UNSUPPORTED"
    detail: str = ""


@dataclass
class CalculationCheck:
    expression: str
    claimed: float | None
    computed: float | None
    unit: str = ""
    match: bool = False
    detail: str = ""


@dataclass
class VerifiedAnswer:
    query: str
    language: str
    answer: str
    claims: list[Claim]
    formulas: list[dict]
    calculations: list[CalculationCheck]
    verification_status: str  # CONFIDENCE_LEVELS
    formula_verification: str  # EXACT_MATCH | EQUIVALENT_MATCH | MISSING | MISMATCH
    confidence: str
    abstain: bool
    abstention_type: str | None
    provenance: list[dict]
    warnings: list[str]
    versions: dict
    latency_ms: dict

    def to_dict(self) -> dict:
        d = asdict(self)
        return d
