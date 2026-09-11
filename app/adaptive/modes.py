"""Learning modes (Fase 11) + Retention (Fase 12): un solo Adaptive Engine.

STUDY / PRACTICE / RECOVERY / EXAM. Los modos NO recalculan nada:
actuan como filtros deterministas con fallback sobre la salida normal
del loop (prioridad, path, spacing y dificultad intactos). Sin LLM,
sin estado propio, sin tablas nuevas.

Fase 12: STUDY distingue UNSEEN de FORGOTTEN / AT_RISK / DUE mediante
el calculo canonico de retention (app.adaptive.retention); RECOVERY
considera FORGOTTEN / AT_RISK / DUE ademas de errores recurrentes.
Solo filtrado + orden estable; la formula de Priority sigue congelada.
"""
from __future__ import annotations

from .retention import calculate_retention, recovery_rank, study_rank

MODES = ("STUDY", "PRACTICE", "RECOVERY", "EXAM")


def validate(mode: str) -> str:
    """Normaliza y valida. ValueError ante modo desconocido."""
    if not isinstance(mode, str):
        raise ValueError("modo desconocido: %r (esperado uno de %s)"
                         % (mode, ", ".join(MODES)))
    m = mode.strip().upper()
    if m not in MODES:
        raise ValueError("modo desconocido: %r (esperado uno de %s)"
                         % (mode, ", ".join(MODES)))
    return m


def mode_code(mode: str) -> str:
    """Reason code de trazabilidad. Ningun prefijo consumido aguas
    abajo lo interpreta (strategy_for solo lee raiz:)."""
    return "mode_" + validate(mode).lower()


def _mastery_of(svc, student_id: str, uid: str):
    return svc.get_mastery(student_id, uid)


def _is_unseen(svc, student_id: str, uid: str) -> bool:
    m = _mastery_of(svc, student_id, uid)
    return m is None or int(m.get("attempt_count", 0) or 0) <= 0


def _has_recurrent_error(svc, student_id: str, uid: str) -> bool:
    rec = {r["error_key"] for r in
           svc.get_recurrent_errors(student_id)}
    if not rec:
        return False
    m = _mastery_of(svc, student_id, uid)
    if m is None:
        return False
    counts = m.get("error_counts") or {}
    return any(k in rec for k in counts)


def _retention_of(svc, student_id: str, uid: str,
                  now: str | None) -> str:
    try:
        return calculate_retention(
            svc, student_id, uid, now=now).state
    except Exception:
        return "LEARNING"


def apply_mode_filter(items: list, svc, student_id: str,
                      mode: str, now: str | None = None) -> list:
    """Filtra preservando orden determinista. STUDY: UNSEEN primero,
    luego FORGOTTEN / AT_RISK / DUE (retention canonica); RECOVERY:
    FORGOTTEN / AT_RISK / DUE o error recurrente. PRACTICE: intacto.
    Vacío -> fallback a la lista completa (documentado, determinista)."""
    m = validate(mode)
    if m == "PRACTICE":
        return list(items)
    if m == "STUDY":
        ranked = []
        for pos, i in enumerate(items):
            uid = i.knowledge_unit_id
            if _is_unseen(svc, student_id, uid):
                ranked.append((0, pos, i))
                continue
            st = _retention_of(svc, student_id, uid, now)
            r = study_rank(st)
            if r < 4:
                ranked.append((r, pos, i))
        if not ranked:
            return list(items)
        ranked.sort(key=lambda t: (t[0], t[1]))
        return [t[2] for t in ranked]
    if m == "RECOVERY":
        ranked = []
        for pos, i in enumerate(items):
            uid = i.knowledge_unit_id
            rec = _has_recurrent_error(svc, student_id, uid)
            st = _retention_of(svc, student_id, uid, now)
            if rec or st in ("FORGOTTEN", "AT_RISK", "DUE"):
                ranked.append((recovery_rank(st, rec), pos, i))
        if not ranked:
            return list(items)
        ranked.sort(key=lambda t: (t[0], t[1]))
        return [t[2] for t in ranked]
    raise ValueError("exam uses closed blueprint, not selection")
