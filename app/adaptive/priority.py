"""PriorityCalculator: implementa docs/PHASE_6_PRIORITY_DESIGN.md §5-9.

P = 100 * (wM*need*evW + wE*err + wR*rec). Toda constante viene de la policy
versionada; aqui no hay numeros magicos. Sin LLM, determinista total.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.correction.errors import SEVERITY_TABLE
from app.student.policy import PRIORITY_POLICY, Policy

from .models import LearningPriority


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


def _evidence_level(n: int) -> str:
    if n <= 0:
        return "UNSEEN"
    if n < 2:
        return "LOW"
    if n < 4:
        return "MODERATE"
    return "HIGH"


class PriorityCalculator:
    """Calcula prioridades explicables desde rendimiento observado."""

    def __init__(self, student_service, policy: Policy | None = None) -> None:
        self.svc = student_service
        self.policy = policy or PRIORITY_POLICY

    def calculate(self, student_id: str, *, limit: int = 10,
                  unit_kind: str | None = None, seed: int = 0,
                  candidates: list[tuple[str, str]] | None = None,
                  now: str | None = None) -> list[LearningPriority]:
        """Orden total: (score DESC, unit_id ASC). `seed` aceptado por API;
        no altera el orden (reservado al muestreo de exploracion en path)."""
        _ = seed
        p = self.policy.parameters
        now_dt = _parse_ts(now) if now else datetime.now(timezone.utc)
        if candidates is None:
            candidates = self._known_candidates(student_id, unit_kind)
        out: list[LearningPriority] = []
        for kind, ref in candidates:
            uid = "%s:%s" % (kind, ref)
            hist = self.svc.get_unit_history(student_id, uid)
            out.append(self._score_one(uid, kind, hist, p, now_dt))
        out.sort(key=lambda x: (-x.priority_score, x.knowledge_unit_id))
        return out[:limit]

    def _known_candidates(self, student_id: str,
                          unit_kind: str | None) -> list[tuple[str, str]]:
        rows = self.svc.get_weak_units(student_id, kind=unit_kind or "", limit=10000)
        out = []
        for r in rows:
            kind, _, ref = r["knowledge_unit_id"].partition(":")
            if unit_kind and kind != unit_kind:
                continue
            out.append((kind, ref))
        return out

    def _score_one(self, uid: str, kind: str, hist: dict, p: dict,
                   now_dt: datetime) -> LearningPriority:
        state = hist.get("state") or {}
        events = hist.get("events", []) or []
        mastery = float(state.get("score", 0.0))
        confidence = float(state.get("confidence", 0.0))
        n = int(state.get("attempt_count", 0))
        level = _evidence_level(n)
        need = round(1.0 - mastery, 4)

        root_counts: dict[str, int] = {}
        for e in events:
            for err in (e.get("evidence") or {}).get("root_errors", []) or []:
                root_counts[err] = root_counts.get(err, 0) + 1
        sev_w = p["severity_weight"]
        err_total = 0.0
        for err in root_counts:
            sev = SEVERITY_TABLE[err][0]  # tipo desconocido: KeyError, nunca severidad inventada
            err_total += sev_w[sev]  # severidad desconocida: KeyError, nunca valor inventado
        err = round(min(1.0, err_total / 2.0), 4)

        last = events[-1] if events else None
        last_signal = (last.get("evidence") or {}).get("signal") if last else None
        last_ts = _parse_ts(state.get("last_attempt", "") or "")
        if n == 0 or last_ts is None:
            rec, days = float(p["recency_unseen"]), None
        else:
            days = max(0, (now_dt - last_ts).days)
            buckets, values = p["recency_buckets_days"], p["recency_values"]
            rec = float(values[-1])
            for edge, val in zip(buckets, values):
                if days <= edge:
                    rec = float(val)
                    break
            if last_signal == 0.0 and days <= p["recent_failure_window_days"]:
                rec = max(rec, float(p["recent_failure_boost"]))

        ev_w = {"UNSEEN": p["evidence_weight"]["LOW"], "LOW": p["evidence_weight"]["LOW"],
                "MODERATE": p["evidence_weight"]["MODERATE"],
                "HIGH": p["evidence_weight"]["HIGH"]}[level]
        score = round(100.0 * (p["w_mastery"] * need * ev_w
                               + p["w_error"] * err
                               + p["w_recency"] * rec), 4)
        reasons = self._reasons(mastery, confidence, n, level, root_counts,
                                days, last_signal, p)
        signals = tuple(sorted("%s%s" % (e, ("x%d" % c) if c > 1 else "")
                               for e, c in root_counts.items()))
        action = self._action(mastery, level, root_counts, state.get("status", ""), p)
        return LearningPriority(
            knowledge_unit_id=uid, unit_kind=kind, priority_score=score,
            mastery=round(mastery, 4), confidence=round(confidence, 4),
            evidence_level=level, reasons=tuple(reasons), error_signals=signals,
            recency_signal=round(rec, 4), recommended_action=action,
            policy_id=self.policy.policy_id, policy_version=self.policy.version)

    @staticmethod
    def _reasons(mastery: float, confidence: float, n: int, level: str,
                 root_counts: dict[str, int], days: int | None,
                 last_signal: float | None, p: dict) -> list[str]:
        reasons = []
        if n == 0:
            reasons.append("nunca_practicado")
        else:
            reasons.append("mastery:%.2f" % mastery)
            reasons.append("evidencia:%s(n=%d)" % (level, n))
        if confidence < 0.5:
            reasons.append("confianza_baja:%.2f" % confidence)
        for err in sorted(root_counts):
            reasons.append("raiz_repetida:%s" % err if root_counts[err] > 1
                           else "raiz:%s" % err)
        if days is None:
            reasons.append("sin_recencia")
        elif last_signal == 0.0 and days <= p["recent_failure_window_days"]:
            reasons.append("fallo_reciente:%dd" % days)
        elif days > p["recency_buckets_days"][-1]:
            reasons.append("sin_practicar_desde:%dd" % days)
        return reasons

    @staticmethod
    def _action(mastery: float, level: str, root_counts: dict[str, int],
                status: str, p: dict) -> str:
        if level == "UNSEEN":
            return "PRACTICE"
        if status == "MASTERED":
            return "MAINTAIN"
        if status == "AT_RISK":
            return "REINFORCE"
        if level == "LOW":
            return "PRACTICE"
        if mastery < p["action_mastery_low"] or root_counts:
            return "PRACTICE" if mastery < p["action_mastery_low"] else "REINFORCE"
        if mastery < p["action_mastery_high"]:
            return "REINFORCE"
        return "CHALLENGE"
