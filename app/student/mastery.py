"""Mastery engine determinista (§44-59, §103-106): eventos inmutables +
estado derivado de la lista completa de senales (event sourcing ligero §105).

Sin randomness (§49). Replay(events) == estado (test §116). El historial
nunca se borra (§54); la recencia pondera sin eliminar (§54 documentado).
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from . import policy
from .models import MasteryEvent, MasteryState


def _now() -> str:
    # Microsegundos, no segundos: el score es recency-weighted (policy.update_score
    # pondera w_i = 1 + 0.1*i) y las senales se releen ORDER BY created_at,event_id.
    # Con resolucion de segundo, varios submit dentro del mismo segundo colisionan
    # y el desempate por event_id (hash) baraja el orden -> score no determinista
    # (rompe "Determinismo total" y test_21_mastery_deterministic). Microsegundos
    # preservan el orden de insercion para llamadas secuenciales.
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def unit_id(kind: str, ref: str) -> str:
    return "%s:%s" % (kind, ref)


def apply_event(*, student_id: str, kind: str, ref: str, question_id: str,
                attempt_id: str, correction_id: str, signal: float | None,
                counted: str | None, root_errors: list[str],
                all_errors: list[str] | None = None,
                prior_signals: list[float], prior_state: MasteryState | None,
                created_at: str = "") -> tuple[MasteryState, MasteryEvent]:
    """Determinista: mismos eventos -> mismo estado. `prior_signals` viene de
    los eventos previos (no se inventa). signal None = no-graduado (§122)."""
    uid = unit_id(kind, ref)
    created = created_at or _now()
    prev = prior_state
    prev_errors = dict(prev.error_counts) if prev else {}
    if signal is None:
        signals = list(prior_signals)
        new_score = policy.update_score(signals)
        new_conf = policy.update_confidence(len(signals), signals[-7:])
        new_correct = prev.correct_count if prev else 0
        new_incorrect = prev.incorrect_count if prev else 0
        reason = "ungraded-status"
    else:
        signals = list(prior_signals) + [signal]
        new_score = policy.update_score(signals)
        new_correct = (prev.correct_count if prev else 0) + (1 if counted == "correct" else 0)
        new_incorrect = (prev.incorrect_count if prev else 0) + (1 if counted == "incorrect" else 0)
        # Perfil: TODOS los errores observados; raices solo para analisis causal.
        for e in (all_errors if all_errors is not None else root_errors):
            prev_errors[e] = prev_errors.get(e, 0) + 1
        new_conf = policy.update_confidence(len(signals), signals[-7:])
        reason = "signal=%.2f" % signal
    new_state = MasteryState(
        mastery_id="ms-%s" % hashlib.sha256(
            ("%s|%s" % (student_id, uid)).encode()).hexdigest()[:12],
        student_id=student_id, knowledge_unit_id=uid, unit_kind=kind,
        score=new_score, confidence=new_conf,
        attempt_count=(prev.attempt_count if prev else 0) + 1,
        correct_count=new_correct, incorrect_count=new_incorrect,
        last_attempt=created,
        last_correct=created if (signal or 0) >= 0.99 else (prev.last_correct if prev else ""),
        error_counts=prev_errors)
    event = MasteryEvent(
        event_id="mev-" + hashlib.sha256(
            ("%s|%s|%s" % (attempt_id, uid, correction_id)).encode()).hexdigest()[:12],
        student_id=student_id, question_id=question_id, attempt_id=attempt_id,
        correction_id=correction_id, knowledge_unit_id=uid, unit_kind=kind,
        old_score=prev.score if prev else 0.0, new_score=new_score,
        old_confidence=prev.confidence if prev else 0.0, new_confidence=new_conf,
        reason=reason,
        evidence={"root_errors": root_errors,
                  "all_errors": all_errors if all_errors is not None else root_errors,
                  "signal": signal},
        policy_version=policy.POLICY_VERSION, created_at=created)
    return new_state, event


def replay(events: list[MasteryEvent]) -> MasteryState | None:
    """Reconstruye estado desde eventos ordenados (test §116)."""
    by_unit: dict[str, list[float]] = {}
    meta: dict[str, MasteryEvent] = {}
    for e in sorted(events, key=lambda x: (x.created_at, x.event_id)):
        sig = e.evidence.get("signal")
        if sig is not None:
            by_unit.setdefault(e.knowledge_unit_id, []).append(float(sig))
        meta[e.knowledge_unit_id] = e
    if not meta:
        return None
    uid = sorted(set(by_unit) | set(meta))[0]
    signals = by_unit.get(uid, [])
    n_graded = len(signals)
    score = policy.update_score(signals)
    conf = policy.update_confidence(n_graded, signals[-7:])
    last = meta[uid]
    total_attempts = sum(1 for e in events if e.knowledge_unit_id == uid)
    return MasteryState(mastery_id="ms-replay", student_id=last.student_id,
                        knowledge_unit_id=uid, unit_kind=last.unit_kind,
                        score=score, confidence=conf,
                        attempt_count=total_attempts,
                        correct_count=sum(1 for s in signals if s >= 0.5),
                        incorrect_count=sum(1 for s in signals if s < 0.5),
                        last_attempt=last.created_at, last_correct="",
                        error_counts={})


def status_of(state: MasteryState, recent: list[float]) -> str:
    return policy.status_for(state.score, state.attempt_count,
                             state.correct_count, recent)
