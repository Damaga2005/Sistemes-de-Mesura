"""Spacing conservador (Bloque B): recencia por buckets + debilidad > spacing.

No modifica PriorityCalculator: spacing es una senal separada que el
RecommendationBuilder combina despues (§5). Sin LLM, determinista total.
Toda constante vive en spacing-policy-v1; aqui no hay numeros magicos.

Estado: 100% derivado de mastery (last_attempt, last_correct,
attempt_count, correct/incorrect_count, score, status) + eventos (raices,
ultima senal). No persiste nada nuevo (§3: no duplicar).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from app.student.policy import SPACING_POLICY, Policy

NEVER_SEEN = "NEVER_SEEN"
ALLOW = "ALLOW"
DEFER = "DEFER"


def _parse_ts(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _days_since(raw: str, now_dt: datetime) -> int | None:
    dt = _parse_ts(raw)
    if dt is None:
        return None
    return max(0, (now_dt - dt).days)


@dataclass(frozen=True)
class SpacingState:
    knowledge_unit_id: str
    bucket: str
    last_seen: str = ""
    last_correct: str = ""
    attempt_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    mastery: float = 0.0
    has_roots: bool = False
    critical: bool = False
    verdict: str = ALLOW
    reasons: tuple = field(default_factory=tuple)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(d["reasons"])
        return d


def bucket_for(attempt_count: int, days: int | None, p: dict) -> str:
    if attempt_count <= 0:
        return NEVER_SEEN
    if days is None:
        return "OLD"  # fila sin fecha (solo sintetica): trato conservador
    edges, names = p["buckets_days"], p["bucket_names"]
    for edge, name in zip(edges, names):
        if days <= edge:
            return name
    return names[-1]


def evaluate(unit_history: dict, *, now: str | None = None,
             policy: Policy | None = None) -> SpacingState:
    """unit_history = StudentService.get_unit_history(...). Solo lectura."""
    pol = policy or SPACING_POLICY
    p = pol.parameters
    now_dt = _parse_ts(now) if now else datetime.now(timezone.utc)
    uid = unit_history.get("knowledge_unit_id", "")
    state = unit_history.get("state") or {}
    events = unit_history.get("events", []) or []
    mastery = float(state.get("score", 0.0))
    n = int(state.get("attempt_count", 0))
    ok = int(state.get("correct_count", 0))
    bad = int(state.get("incorrect_count", 0))
    status = state.get("status", "") or ""
    last_seen = state.get("last_attempt", "") or ""
    last_correct = state.get("last_correct", "") or ""
    days = _days_since(last_seen, now_dt)
    days_correct = _days_since(last_correct, now_dt)
    roots = False
    for e in events:
        if (e.get("evidence") or {}).get("root_errors"):
            roots = True
            break
    last_signal = (events[-1].get("evidence") or {}).get("signal") \
        if events else None
    bucket = bucket_for(n, days, p)
    critical = (
        status in p["critical_statuses"]
        or (mastery < p["critical_mastery_below"]
            and n >= p["critical_min_attempts"])
        or (roots and mastery < p["critical_root_mastery_below"]
            and bad >= p["critical_root_min_incorrect"]))
    window = p["defer_correct_within_days"]
    recent_correct = (days_correct is not None and days_correct <= window)
    fresh_failure = (last_signal == 0.0)
    reasons = ["bucket:%s" % bucket]
    if n <= 0:
        verdict, motive = ALLOW, "nunca_visto"
    elif critical:
        verdict = ALLOW
        motive = ("debilidad_critica_sobre_spacing"
                  if (recent_correct and not fresh_failure)
                  else "debilidad_critica")
    elif fresh_failure or not recent_correct:
        verdict, motive = ALLOW, ("fallo_reciente" if fresh_failure
                                  else "disponible")
    else:
        verdict, motive = DEFER, "correcto_reciente_diferido"
    reasons.append("veredicto:%s" % verdict)
    reasons.append("motivo:%s" % motive)
    return SpacingState(
        knowledge_unit_id=uid, bucket=bucket, last_seen=last_seen,
        last_correct=last_correct, attempt_count=n, success_count=ok,
        failure_count=bad, mastery=round(mastery, 4), has_roots=roots,
        critical=critical, verdict=verdict, reasons=tuple(reasons))
