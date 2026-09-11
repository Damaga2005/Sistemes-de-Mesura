"""Retention / Forgetting (Fase 12): una sola funcion canonica determinista.

Deriva el estado de retencion desde las estructuras existentes, sin
tablas nuevas, sin aprendizaje automatico, sin modelo de lenguaje
externo, sin segundo Adaptive Engine:

    MasteryState (score, status, attempt/correct/incorrect, last_attempt,
                  last_correct, error_counts)
  + student_spacing (last_review, next_review, interval_days,
                     review_count, last_status, last_score)
  + mastery_events (signals, root_errors, orden cronologico)
  + error_memory (solo via filtro de Recovery en modes.py)

Estados canonicos:

    UNSEEN    sin evidencia de practica suficiente (n == 0 o sin fila).
    LEARNING  practicada pero no consolidada, o debil sin senal de olvido.
    MASTERED  consolidada segun MasteryState y sin vencimiento ni riesgo.
    DUE       next_review <= now segun F10 (sin evidencia de olvido).
    AT_RISK   consolidada y acercandose a next_review (fraccion del
              intervalo vigente). Sin evidencia negativa fresca.
    FORGOTTEN historial fuerte + vencimiento + evidencia negativa fresca.

Principio anti-falso-olvido: ausencia de evidencia != evidencia de
olvido. Sin evidencia negativa fresca nunca se declara FORGOTTEN;
como maximo AT_RISK / DUE.

`retention_score` (0..1) es una heuristica operativa documentada, no
un modelo cientifico de memoria humana (no se afirma ninguna curva).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from app.student.policy import RETENTION_POLICY, Policy

RETENTION_STATES = ("UNSEEN", "LEARNING", "MASTERED", "DUE", "AT_RISK", "FORGOTTEN")

_STRONG_STATUSES = ("MASTERED", "PROFICIENT")


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


def _now_dt(now: str | None) -> datetime:
    dt = _parse_ts(now) if now else None
    return dt or datetime.now(timezone.utc)


def _days_between(a: datetime | None, b: datetime | None) -> int | None:
    if a is None or b is None:
        return None
    return max(0, (b - a).days)


@dataclass(frozen=True)
class RetentionState:
    knowledge_unit_id: str
    state: str
    retention_score: float = 0.0
    reasons: tuple = field(default_factory=tuple)
    mastery_status: str = ""
    mastery_score: float = 0.0
    attempt_count: int = 0
    due: bool = False
    overdue_days: int = 0
    policy_id: str = "retention-policy"
    policy_version: str = "v1"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(d["reasons"])
        return d


def retention_code(state: str) -> str:
    """Reason code de observabilidad. Solo AT_RISK / DUE / FORGOTTEN
    emiten codigo (los demas no aportan senal de recuperacion)."""
    mapping = {
        "AT_RISK": "retention_at_risk",
        "DUE": "retention_due",
        "FORGOTTEN": "retention_forgotten",
    }
    return mapping.get(state, "")


def calculate_retention(svc, student_id: str, knowledge_unit_id: str, *,
                        now: str | None = None,
                        policy: Policy | None = None) -> RetentionState:
    """Unico calculo canonico de retention. Solo lectura, determinista."""
    pol = policy or RETENTION_POLICY
    p = pol.parameters
    moment = _now_dt(now)
    hist = svc.get_unit_history(student_id, knowledge_unit_id)
    state = hist.get("state") or {}
    events = hist.get("events", []) or []
    n = int(state.get("attempt_count", 0) or 0)
    mastery = float(state.get("score", 0.0) or 0.0)
    mstatus = str(state.get("status", "") or "")
    correct = int(state.get("correct_count", 0) or 0)
    last_attempt = _parse_ts(str(state.get("last_attempt", "") or ""))
    last_signal = None
    if events:
        last_signal = (events[-1].get("evidence") or {}).get("signal")
    fresh_negative = last_signal == 0.0

    kind, _, ref = knowledge_unit_id.partition(":")
    sp = None
    if kind and ref:
        try:
            sp = svc.get_spacing(student_id, kind, ref)
        except Exception:
            sp = None
    due = False
    overdue = 0
    interval = None
    review_count = 0
    if sp is not None:
        nxt = _parse_ts(str(sp.get("next_review", "") or ""))
        interval = sp.get("interval_days")
        try:
            interval = int(interval) if interval is not None else None
        except (TypeError, ValueError):
            interval = None
        review_count = int(sp.get("review_count", 0) or 0)
        if nxt is not None:
            due = nxt <= moment
            overdue = max(0, (moment - nxt).days) if due else 0
    last_review = _parse_ts(str((sp or {}).get("last_review", "") or ""))
    anchor = last_review or last_attempt
    elapsed = _days_between(anchor, moment)

    if n <= 0:
        return RetentionState(
            knowledge_unit_id=knowledge_unit_id, state="UNSEEN",
            retention_score=0.0,
            reasons=("sin_evidencia", "retention:UNSEEN"),
            mastery_status=mstatus, mastery_score=round(mastery, 4),
            attempt_count=n, due=False, overdue_days=0,
            policy_id=pol.policy_id, policy_version=pol.version)

    strong = (
        mstatus in _STRONG_STATUSES
        or correct >= int(p.get("forgotten_min_correct", 3))
        or mastery >= 0.9
    )
    # El submit actualiza student_spacing en la misma transaccion
    # (last_review/next_review pasan a "ahora" y un fallo reinicia el
    # intervalo a 1). Por eso FORGOTTEN acepta dos evidencias
    # equivalentes de "hubo ausencia + fallo":
    #   a) fila todavia vencida + evidencia negativa fresca, o
    #   b) intervalo recien reiniciado a 1 con historial de revisiones
    #      (el fallo llego tras practica consolidada).
    reset_proxy = (
        sp is not None
        and int(sp.get("review_count", 0) or 0) >= 2
        and (interval or 0) <= 1
        and str(sp.get("last_status", "") or "") == "INCORRECT"
    )
    forgotten = (
        n >= int(p.get("forgotten_min_attempts", 3))
        and strong
        and fresh_negative
        and (due or reset_proxy)
    )
    reasons: list[str] = []
    if mstatus:
        reasons.append("mastery:%s:%.2f" % (mstatus, mastery))
    reasons.append("intentos:n=%d(correct=%d)" % (n, correct))
    if sp is None:
        reasons.append("spacing:sin_fila")
    elif due:
        reasons.append("spacing:vencida:overdue=%dd" % overdue)
    else:
        reasons.append("spacing:al_dia")
    if fresh_negative:
        reasons.append("evidencia:negativa_reciente")
    if strong:
        reasons.append("historial:fuerte")

    if forgotten:
        score = _heuristic(mastery, due, overdue, interval, fresh_negative)
        return RetentionState(
            knowledge_unit_id=knowledge_unit_id, state="FORGOTTEN",
            retention_score=score,
            reasons=tuple(reasons + ["retention:FORGOTTEN"]),
            mastery_status=mstatus, mastery_score=round(mastery, 4),
            attempt_count=n, due=True, overdue_days=overdue,
            policy_id=pol.policy_id, policy_version=pol.version)
    if due:
        score = _heuristic(mastery, True, overdue, interval, fresh_negative)
        return RetentionState(
            knowledge_unit_id=knowledge_unit_id, state="DUE",
            retention_score=score,
            reasons=tuple(reasons + ["retention:DUE"]),
            mastery_status=mstatus, mastery_score=round(mastery, 4),
            attempt_count=n, due=True, overdue_days=overdue,
            policy_id=pol.policy_id, policy_version=pol.version)

    at_risk = False
    if strong and not fresh_negative:
        if sp is not None and interval:
            lead = float(p.get("at_risk_lead_ratio", 0.5))
            if elapsed is not None and elapsed >= interval * lead:
                at_risk = True
        elif elapsed is not None and elapsed >= int(
                p.get("no_spacing_at_risk_days", 14)):
            at_risk = True
    if at_risk:
        score = _heuristic(mastery, False, 0, interval, False)
        return RetentionState(
            knowledge_unit_id=knowledge_unit_id, state="AT_RISK",
            retention_score=score,
            reasons=tuple(reasons + ["retention:AT_RISK"]),
            mastery_status=mstatus, mastery_score=round(mastery, 4),
            attempt_count=n, due=False, overdue_days=0,
            policy_id=pol.policy_id, policy_version=pol.version)
    if mstatus == "MASTERED":
        score = _heuristic(mastery, False, 0, interval, fresh_negative)
        return RetentionState(
            knowledge_unit_id=knowledge_unit_id, state="MASTERED",
            retention_score=score,
            reasons=tuple(reasons + ["retention:MASTERED"]),
            mastery_status=mstatus, mastery_score=round(mastery, 4),
            attempt_count=n, due=False, overdue_days=0,
            policy_id=pol.policy_id, policy_version=pol.version)
    score = _heuristic(mastery, False, 0, interval, fresh_negative)
    return RetentionState(
        knowledge_unit_id=knowledge_unit_id, state="LEARNING",
        retention_score=score,
        reasons=tuple(reasons + ["retention:LEARNING"]),
        mastery_status=mstatus, mastery_score=round(mastery, 4),
        attempt_count=n, due=False, overdue_days=0,
        policy_id=pol.policy_id, policy_version=pol.version)


def _heuristic(mastery: float, due: bool, overdue: int,
               interval: int | None, fresh_negative: bool) -> float:
    """Heuristica operativa 0..1 (NO modelo cientifico): parte del
    mastery vigente, penaliza vencimiento y evidencia negativa fresca."""
    score = max(0.0, min(1.0, float(mastery or 0.0)))
    if due:
        span = float((interval or 7) + 7)
        score *= max(0.0, 1.0 - float(max(0, overdue)) / span)
    if fresh_negative:
        score *= 0.5
    return round(max(0.0, min(1.0, score)), 4)


def recovery_rank(state: str, has_recurrent_error: bool) -> int:
    """Orden conceptual F12-Bloque E (solo ordenacion de filtros,
    nunca recalibra Priority): FORGOTTEN+recurrente primero."""
    if state == "FORGOTTEN" and has_recurrent_error:
        return 0
    if state == "FORGOTTEN":
        return 1
    if has_recurrent_error:
        return 2
    if state == "DUE":
        return 3
    if state == "AT_RISK":
        return 4
    return 5


def study_rank(state: str) -> int:
    """Orden conceptual F12-Bloque G para STUDY (filtros, no Priority)."""
    return {"UNSEEN": 0, "FORGOTTEN": 1, "AT_RISK": 2, "DUE": 3}.get(state, 4)
