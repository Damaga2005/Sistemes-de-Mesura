"""Modelos tipados del Retrieval Engine. Sin dependencias de LLM (Fase 3+)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Protocol


@dataclass
class RetrievalFilters:
    topic: int | None = None
    section: str | None = None
    source_type: str | None = None  # html | pdf
    content_type: str | None = None
    formula_only: bool = False


@dataclass
class RetrievalQuery:
    text: str
    topic: int | None = None
    section: str | None = None
    query_type: str | None = None  # GENERAL si no hay evidencia para clasificar


@dataclass
class RetrievalResult:
    chunk_id: str
    score: float
    final_score: float
    source_id: str
    source_path: str
    source_hash: str
    topic: int
    section: str | None
    text: str
    evidence_type: str  # lexical | semantic | formula | metadata
    formula_ids: list[str] = field(default_factory=list)
    image_refs: list[str] = field(default_factory=list)
    parent_context: dict | None = None
    components: dict = field(default_factory=dict)  # scores explicados (--debug)
    warnings: list[str] = field(default_factory=list)


@dataclass
class RetrievalResponse:
    query: RetrievalQuery
    normalized_query: str
    results: list[RetrievalResult]
    abstain: bool
    abstention_reason: str | None
    confidence: float
    warnings: list[str]
    retrieval_version: str
    index_version: str
    knowledge_base_version: str
    latency_ms: float
    debug: dict = field(default_factory=dict)


@dataclass
class EvidencePack:
    query: str
    results: list[dict]
    primary_evidence: list[dict]
    supporting_evidence: list[dict]
    formulas: list[dict]
    concepts: list[dict]
    units: list[dict]
    visuals: list[dict]
    sources: list[dict]
    confidence: float
    abstain: bool
    warnings: list[dict]


class Retriever(Protocol):
    def retrieve(self, query: str, *, filters: RetrievalFilters | None = None,
                 top_k: int = 10) -> RetrievalResponse:
        ...


def pack_to_dict(pack: EvidencePack) -> dict:
    return asdict(pack)


def response_to_dict(resp: RetrievalResponse) -> dict:
    return asdict(resp)
