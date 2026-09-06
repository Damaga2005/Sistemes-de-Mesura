"""Memoria de rendimiento (§61-65): solo inferencias con evidencia.

FACTUAL academica: PROHIBIDA (la memoria nunca aprende materia).
Cada memoria: confidence + evidence_count + last_evidence + attempt_ids.
Sin evidencia suficiente -> INSUFFICIENT_EVIDENCE (no se almacena, §64).
Rechazo de inyeccion manual (§142): sin eventos no hay memoria.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from .models import Memory

MIN_EVIDENCE = 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def summarize_performance(student_id: str, error_totals: dict[str, int],
                          attempts: list[dict], mastery_top: list[dict]) -> list[Memory]:
    """Deriva memorias desde agregados con provenance. Determinista."""
    out: list[Memory] = []
    total = sum(error_totals.values())
    if total >= MIN_EVIDENCE:
        top = sorted(error_totals.items(), key=lambda x: (-x[1], x[0]))[0]
        out.append(_make(student_id, "PERFORMANCE",
                         "El error más frecuente es %s (%d/%d intentos con error)." % (
                             top[0], top[1], total),
                         attempts, "error-profile"))
    weak = [m for m in mastery_top if m.get("status") == "AT_RISK"]
    if weak:
        first = sorted(weak, key=lambda x: x["knowledge_unit_id"])[0]
        out.append(_make(student_id, "PERFORMANCE",
                         "Riesgo en %s: últimos intentos incorrectos." % first[
                             "knowledge_unit_id"],
                         attempts, "at-risk"))
    strong = [m for m in mastery_top if m.get("status") == "MASTERED"]
    if strong:
        first = sorted(strong, key=lambda x: x["knowledge_unit_id"])[0]
        out.append(_make(student_id, "PERFORMANCE",
                         "Dominio en %s." % first["knowledge_unit_id"],
                         attempts, "mastered"))
    return out


def _make(student_id: str, kind: str, text: str, attempts: list[dict],
          reason: str) -> Memory:
    aids = sorted({a["attempt_id"] for a in attempts})[:50]
    cids = sorted({a.get("correction_id", "") for a in attempts if a.get("correction_id")})[:50]
    stamp = _now()
    mid = "mem-" + hashlib.sha256(("%s|%s|%s" % (student_id, text, reason)).encode(),
                                  ).hexdigest()[:12]
    return Memory(memory_id=mid, student_id=student_id, kind=kind, text=text,
                  confidence=round(min(1.0, len(aids) / 8.0), 3),
                  evidence_count=len(aids), last_evidence=stamp,
                  attempt_ids=aids, correction_ids=cids)


def reject_manual_memory() -> tuple[bool, str]:
    """§142: memoria manual sin eventos -> rechazado siempre."""
    return False, "memory requires mastery events as evidence"
