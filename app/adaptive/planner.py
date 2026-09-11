"""Curriculum Planner (Fase 13): WHAT / WHEN sobre el sistema adaptativo.

Capa de planificacion/orquestacion, NO un segundo Adaptive Engine:
no recalcula prioridad, mastery, dificultad, retention ni spacing;
lee esas senales y las convierte en un plan temporal determinista
de unidades academicas (TODAY / NEXT_7_DAYS / LATER).

    CurriculumPlanner = WHAT / WHEN (unidades + horizonte + modo)
    AdaptiveLoop      = WHICH QUESTION (pregunta concreta)

Unidad curricular = `knowledge_unit_id` existente
(topic / section / concept / formula); sin ontologia nueva.
Plan Item != question: nunca contiene question_id. Sin modelo de
lenguaje, sin ML, sin persistencia (plan derivado; se regenera).
"""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from app.student.policy import CURRICULUM_POLICY, Policy

from .path import LearningPathSelector
from .priority import PriorityCalculator
from .retention import calculate_retention

HORIZONS = ("TODAY", "NEXT_7_DAYS", "LATER")
_PLAN_HORIZONS = ("today", "week", "later", "full")


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


def _now_iso(now: str | None) -> str:
    if now:
        dt = _parse_ts(now)
        if dt is not None:
            return dt.isoformat(timespec="seconds")
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ro(path) -> sqlite3.Connection:
    return sqlite3.connect("file:%s?mode=ro" % path, uri=True)


@dataclass(frozen=True)
class PlanItem:
    knowledge_unit_id: str
    unit_kind: str
    topic: int | None = None
    section: str | None = None
    horizon: str = "TODAY"
    rank: int = 0
    priority_score: float = 0.0
    retention_state: str = "UNSEEN"
    coverage_state: str = "unseen"
    reason_codes: tuple = ()
    recommended_mode: str = "STUDY"
    policy_id: str = "curriculum-policy"
    policy_version: str = "v1"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["reason_codes"] = list(d["reason_codes"])
        return d


@dataclass(frozen=True)
class CurriculumPlan:
    student_id: str
    horizon: str
    now: str
    plan_id: str
    today: tuple = ()
    next_7_days: tuple = ()
    later: tuple = ()
    policy_id: str = "curriculum-policy"
    policy_version: str = "v1"

    def items(self) -> list[PlanItem]:
        if self.horizon == "today":
            return list(self.today)
        if self.horizon == "week":
            return list(self.next_7_days)
        if self.horizon == "later":
            return list(self.later)
        return list(self.today) + list(self.next_7_days) + \
            list(self.later)

    def to_dict(self) -> dict:
        return {
            "student_id": self.student_id,
            "horizon": self.horizon,
            "now": self.now,
            "plan_id": self.plan_id,
            "today": [i.to_dict() for i in self.today],
            "next_7_days": [i.to_dict() for i in self.next_7_days],
            "later": [i.to_dict() for i in self.later],
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
        }


def _coverage_class(mastery_status: str, attempts: int) -> str:
    if attempts <= 0:
        return "unseen"
    if mastery_status == "MASTERED":
        return "mastered"
    if mastery_status in ("AT_RISK", "EMERGING"):
        return "weak"
    return "learning"


def _mode_for(retention_state: str, coverage: str,
              recurrent: bool) -> str:
    if retention_state == "FORGOTTEN":
        return "RECOVERY"
    if recurrent:
        return "RECOVERY"
    if coverage == "unseen":
        return "STUDY"
    return "PRACTICE"


class CurriculumPlanner:
    """Genera planes derivados. Solo lectura sobre StudentService + KB."""

    def __init__(self, student_service,
                 calculator: PriorityCalculator | None = None,
                 selector: LearningPathSelector | None = None,
                 policy: Policy | None = None) -> None:
        self.svc = student_service
        self.calc = calculator or PriorityCalculator(student_service)
        self.selector = selector or LearningPathSelector(student_service)
        self.policy = policy or CURRICULUM_POLICY

    def generate(self, student_id: str, *,
                 horizon: str = "full",
                 now: str | None = None,
                 seed: int = 0,
                 today_limit: int | None = None,
                 week_limit: int | None = None,
                 later_limit: int | None = None) -> CurriculumPlan:
        """Plan determinista. `seed` aceptado por API; no altera el
        orden (reservado, como en Priority/Path). Limites validan."""
        _ = seed
        h = (horizon or "").strip().lower()
        if h not in _PLAN_HORIZONS:
            raise ValueError(
                "horizon desconocido: %r (esperado %s)"
                % (horizon, ", ".join(_PLAN_HORIZONS)))
        p = self.policy.parameters
        t_lim = p["today_limit"] if today_limit is None else today_limit
        w_lim = p["week_limit"] if week_limit is None else week_limit
        l_lim = p["later_limit"] if later_limit is None else later_limit
        for name, v in (("today_limit", t_lim), ("week_limit", w_lim),
                        ("later_limit", l_lim)):
            if not isinstance(v, int) or v < 0:
                raise ValueError("%s inválido" % name)
        moment = _now_iso(now)
        ranked = self._ranked_units(student_id, moment)
        today = tuple(i for i in ranked if i.horizon == "TODAY")[:t_lim]
        week = tuple(i for i in ranked
                     if i.horizon == "NEXT_7_DAYS")[:w_lim]
        later = tuple(i for i in ranked
                      if i.horizon == "LATER")[:l_lim]
        plan_id = self._fingerprint(student_id, h, moment,
                                    today + week + later)
        return CurriculumPlan(
            student_id=student_id, horizon=h, now=moment,
            plan_id=plan_id, today=today, next_7_days=week,
            later=later, policy_id=self.policy.policy_id,
            policy_version=self.policy.version)

    # ---------- ranking ----------
    def _ranked_units(self, student_id: str,
                      moment: str) -> list[PlanItem]:
        p = self.policy.parameters
        prios = {pr.knowledge_unit_id: pr.priority_score
                 for pr in self.calc.calculate(
                     student_id, limit=10000, now=moment)}
        touched = self.svc.get_weak_units(student_id, limit=10000)
        recurrent_keys = {r["error_key"] for r in
                          self.svc.get_recurrent_errors(student_id)}
        cands: list[tuple[int, float, str]] = []
        # (clase, -priority, uid) se resuelve al construir items.
        seen: set[str] = set()
        for row in touched:
            uid = row["knowledge_unit_id"]
            if uid in seen:
                continue
            seen.add(uid)
            cands.append((9, prios.get(uid, 0.0), uid))
        for uid in self._unseen_pool(student_id, seen,
                                     int(p["unseen_pool_cap"])):
            seen.add(uid)
            cands.append((9, 0.0, uid))
        items = [self._itemize(student_id, uid, pr, moment,
                               recurrent_keys,
                               int(p["due_soon_days"]))
                 for _, pr, uid in cands]
        # Orden total: (horizonte, clase, -priority, uid). Sin azar,
        # sin orden de SQLite ni de filesystem.
        order = {"TODAY": 0, "NEXT_7_DAYS": 1, "LATER": 2}
        items.sort(key=lambda i: (order[i.horizon], i.rank,
                                  -i.priority_score,
                                  i.knowledge_unit_id))
        out = []
        for pos, item in enumerate(items):
            out.append(PlanItem(
                knowledge_unit_id=item.knowledge_unit_id,
                unit_kind=item.unit_kind,
                topic=item.topic, section=item.section,
                horizon=item.horizon, rank=pos,
                priority_score=item.priority_score,
                retention_state=item.retention_state,
                coverage_state=item.coverage_state,
                reason_codes=item.reason_codes,
                recommended_mode=item.recommended_mode,
                policy_id=item.policy_id,
                policy_version=item.policy_version))
        return out

    def _itemize(self, student_id: str, uid: str, priority: float,
                 moment: str, recurrent_keys: set[str],
                 due_soon_days: int) -> PlanItem:
        kind, _, ref = uid.partition(":")
        m = self.svc.get_mastery(student_id, uid)
        attempts = int((m or {}).get("attempt_count", 0) or 0)
        mstatus = str((m or {}).get("status", "") or "")
        coverage = _coverage_class(mstatus, attempts)
        if attempts <= 0:
            retention = "UNSEEN"
            due_soon = False
            recurrent = False
            reasons = ["coverage_unseen"]
        else:
            retention = calculate_retention(
                self.svc, student_id, uid, now=moment).state
            errors = (m or {}).get("error_counts") or {}
            recurrent = any(k in recurrent_keys for k in errors)
            due_soon = self._due_soon(student_id, kind, ref, moment,
                                      due_soon_days)
            reasons = []
            if coverage == "weak":
                reasons.append("coverage_weak")
            if coverage == "mastered":
                reasons.append("coverage_mastered")
            if retention == "FORGOTTEN":
                reasons.append("retention_forgotten")
            elif retention == "DUE":
                reasons.append("retention_due")
                reasons.append("spacing_due")
            elif retention == "AT_RISK":
                reasons.append("retention_at_risk")
            if recurrent:
                sev = self._recurrent_severity(student_id,
                                               recurrent_keys, errors)
                reasons.append("error_recurrent:%s" % sev)
            if coverage == "weak":
                reasons.append("mastery_weak")
        if retention == "FORGOTTEN":
            horizon, cls = "TODAY", 0
        elif retention == "DUE":
            horizon, cls = "TODAY", 1
        elif recurrent and coverage == "weak":
            horizon, cls = "TODAY", 2
        elif recurrent:
            horizon, cls = "TODAY", 3
        elif coverage == "weak":
            horizon, cls = "TODAY", 4
        elif coverage == "unseen":
            horizon, cls = "TODAY", 5
        elif retention == "AT_RISK":
            horizon, cls = "NEXT_7_DAYS", 6
        elif due_soon:
            horizon, cls = "NEXT_7_DAYS", 7
        elif coverage == "mastered":
            horizon, cls = "LATER", 9
        elif coverage == "learning":
            horizon, cls = "NEXT_7_DAYS", 8
        else:
            horizon, cls = "LATER", 9
        topic = self.selector.resolve_topic(student_id, uid)
        section = ref.partition(":")[2] or None \
            if kind == "section" else None
        return PlanItem(
            knowledge_unit_id=uid, unit_kind=kind, topic=topic,
            section=section, horizon=horizon, rank=cls,
            priority_score=round(float(priority or 0.0), 4),
            retention_state=retention, coverage_state=coverage,
            reason_codes=tuple(reasons),
            recommended_mode=_mode_for(retention, coverage,
                                       recurrent),
            policy_id=self.policy.policy_id,
            policy_version=self.policy.version)

    def _due_soon(self, student_id: str, kind: str, ref: str,
                  moment: str, days: int) -> bool:
        try:
            sp = self.svc.get_spacing(student_id, kind, ref)
        except Exception:
            return False
        if not sp:
            return False
        nxt = _parse_ts(str(sp.get("next_review", "") or ""))
        now_dt = _parse_ts(moment)
        if nxt is None or now_dt is None or nxt <= now_dt:
            return False
        return (nxt - now_dt).days <= days

    def _recurrent_severity(self, student_id: str,
                            recurrent_keys: set[str],
                            errors: dict) -> str:
        try:
            rec = {r["error_key"]: r for r in
                   self.svc.get_recurrent_errors(student_id)}
        except Exception:
            rec = {}
        hits = [k for k in errors if k in recurrent_keys]
        if not hits:
            return "x2"
        key = sorted(hits)[0]
        count = rec.get(key, {}).get("error_count", 2)
        return "%s:x%d" % (key, count)

    def _unseen_pool(self, student_id: str, exclude: set[str],
                     cap: int) -> list[str]:
        """Formulas no-vistas de temas tocados (como exploracion del
        Path) + topics no tocados. Orden curricular, acotado."""
        touched = self._touched_topics(student_id)
        known = self._known_formula_units(student_id)
        pool: list[str] = []
        for t in range(1, 11):
            uid = "topic:T%02d" % t
            if uid not in exclude and uid not in pool:
                pool.append(uid)
        if touched:
            con = _ro(self.svc.kb_path)
            try:
                rows = con.execute(
                    "SELECT equation_id, topic FROM formulas "
                    "ORDER BY topic ASC, equation_id ASC").fetchall()
            finally:
                con.close()
            for eq, t in rows:
                if t not in touched:
                    continue
                uid = "formula:" + eq
                if uid in exclude or uid in known:
                    continue
                pool.append(uid)
                if len(pool) >= cap + 10:
                    break
        else:
            con = _ro(self.svc.kb_path)
            try:
                rows = con.execute(
                    "SELECT equation_id FROM formulas WHERE topic=1 "
                    "ORDER BY equation_id ASC").fetchall()
            finally:
                con.close()
            for (eq,) in rows:
                uid = "formula:" + eq
                if uid in exclude or uid in known:
                    continue
                pool.append(uid)
                if len(pool) >= cap + 10:
                    break
        return [u for u in pool if u not in exclude][:cap]

    def _touched_topics(self, student_id: str) -> list[int]:
        touched: set[int] = set()
        con = self.svc.store.connect()
        try:
            for (uid,) in con.execute(
                    "SELECT knowledge_unit_id FROM mastery_states "
                    "WHERE student_id=?", (student_id,)).fetchall():
                if uid.startswith("topic:T"):
                    try:
                        touched.add(int(uid[len("topic:T"):]))
                    except ValueError:
                        pass
        finally:
            con.close()
        return sorted(touched)

    def _known_formula_units(self, student_id: str) -> set[str]:
        con = self.svc.store.connect()
        try:
            rows = con.execute(
                "SELECT knowledge_unit_id FROM mastery_states "
                "WHERE student_id=? AND knowledge_unit_id LIKE "
                "'formula:%'", (student_id,)).fetchall()
        finally:
            con.close()
        return {r[0] for r in rows}

    def _fingerprint(self, student_id: str, horizon: str,
                     moment: str, items: tuple) -> str:
        body = "|".join(
            [student_id, self.policy.key(), horizon, moment] +
            ["%s:%s:%s" % (i.horizon, i.knowledge_unit_id,
                            i.recommended_mode) for i in items])
        return "plan-" + hashlib.sha256(
            body.encode()).hexdigest()[:12]
