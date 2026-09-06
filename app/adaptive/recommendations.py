"""RecommendationBuilder (Bloque B, §§7-11): prioridades + path + spacing.

Orden conceptual (§8): 1 debilidad critica, 2 practice de alta prioridad,
3 refuerzo de errores, 4 practica normal, 5 mantenimiento, 6 exploracion.
Dentro de cada categoria: (priority DESC, unit_id ASC). Sin rowid, sin
azar, sin orden de sets ni de filesystem.

NO corrige, NO genera preguntas, NO modifica mastery/KB, NO llama al LLM.
La prioridad entra ya calculada (no se toca PriorityCalculator, §5).
"""
from __future__ import annotations

from app.student.policy import (
    DIFFICULTY_POLICY,
    PRIORITY_POLICY,
    SPACING_POLICY,
    Policy,
)

from .models import LearningPathItem, LearningPriority, Recommendation
from .path import LearningPathSelector
from .spacing import ALLOW, DEFER, SpacingState, evaluate

# Categorias §8 (frozen). REVIEW no la emite el calculador; si llegara,
# es practica normal. CHALLENGE tambien practica (para avanzados).
CATEGORIES = ("critical_weakness", "high_priority_practice",
              "reinforce_errors", "normal_practice", "maintenance",
              "exploration")
_PARENT_KINDS = ("section", "topic")


def category_for(*, critical: bool, explored: bool, action: str,
                 priority_score: float, high_min: float) -> int:
    if critical:
        return 1
    if explored:
        return 6
    if action == "REINFORCE":
        return 3
    if action == "MAINTAIN":
        return 5
    if action == "PRACTICE" and priority_score >= high_min:
        return 2
    return 4


class RecommendationBuilder:
    def __init__(self, student_service, *,
                 spacing_policy: Policy | None = None,
                 path_selector: LearningPathSelector | None = None) -> None:
        self.svc = student_service
        self.policy = spacing_policy or SPACING_POLICY
        self.selector = path_selector or LearningPathSelector(student_service)

    def build(self, student_id: str, priorities: list[LearningPriority],
              path_items: list[LearningPathItem], *, limit: int = 5,
              now: str | None = None) -> list[Recommendation]:
        """Ruta final determinista. `priorities` y `path_items` mandan los
        picks del path; las prioridades solo rescatan (backfill) unidades
        ausentes del path: criticas o ALLOW necesarios hasta `limit`.
        Padres cubiertos por hojas conservadas nunca resucitan (§11)."""
        if limit <= 0:
            return []
        p = self.policy.parameters
        high_min = float(p["high_priority_min_score"])
        src = {"priority": PRIORITY_POLICY.key(),
               "difficulty": DIFFICULTY_POLICY.key()}
        seen: dict[str, tuple[LearningPathItem, SpacingState, int]] = {}
        order: list[str] = []
        for item in path_items:
            if item.knowledge_unit_id not in seen:
                sp = evaluate(self.svc.get_unit_history(
                    student_id, item.knowledge_unit_id), now=now,
                    policy=self.policy)
                explored = "exploracion_unseen" in item.reasons
                cat = category_for(critical=sp.critical, explored=explored,
                                   action=item.action,
                                   priority_score=item.priority,
                                   high_min=high_min)
                seen[item.knowledge_unit_id] = (item, sp, cat)
                order.append(item.knowledge_unit_id)
        allow = sorted(
            (u for u in order if seen[u][1].verdict == ALLOW),
            key=lambda u: (seen[u][2], -seen[u][0].priority, u))
        deferred = sorted(
            (u for u in order if seen[u][1].verdict == DEFER),
            key=lambda u: (seen[u][2], -seen[u][0].priority, u))
        kept: list[str] = []
        covered: set[int] = set()
        for u in allow:
            item = seen[u][0]
            if self._covered_parent(item, covered):
                continue
            kept.append(u)
            t = item.target_topic
            if item.unit_kind in ("formula", "concept") and t is not None:
                covered.add(t)
            if len(kept) >= limit:
                break
        if len(kept) < limit:
            for pr in priorities:
                if len(kept) >= limit:
                    break
                if pr.knowledge_unit_id in seen:
                    continue
                seen[pr.knowledge_unit_id] = self._itemize(
                    student_id, pr, high_min, now)
                item, sp, cat = seen[pr.knowledge_unit_id]
                if self._covered_parent(item, covered):
                    continue
                if sp.verdict == DEFER:
                    deferred.append(pr.knowledge_unit_id)
                    continue
                kept.append(pr.knowledge_unit_id)
                t = item.target_topic
                if item.unit_kind in ("formula", "concept") and t is not None:
                    covered.add(t)
        deferred = sorted(deferred,
                          key=lambda u: (seen[u][2], -seen[u][0].priority, u))
        if len(kept) < limit:
            for u in deferred:
                if len(kept) >= limit:
                    break
                if u in kept:
                    continue
                kept.append(u)
        out = []
        for u in kept:
            item, sp, cat = seen[u]
            out.append(self._recommend(student_id, item, sp, cat, src,
                                       bypass=u in deferred
                                       and sp.verdict == DEFER))
        return out

    def _covered_parent(self, item: LearningPathItem,
                        covered: set[int]) -> bool:
        return (item.unit_kind in _PARENT_KINDS
                and item.target_topic is not None
                and item.target_topic in covered)

    def _itemize(self, student_id: str, pr: LearningPriority, high_min: float,
                 now: str | None) -> tuple[LearningPathItem, SpacingState, int]:
        item = self.selector._itemize(student_id, pr, explored=False)
        sp = evaluate(self.svc.get_unit_history(
            student_id, pr.knowledge_unit_id), now=now, policy=self.policy)
        cat = category_for(critical=sp.critical, explored=False,
                           action=item.action, priority_score=item.priority,
                           high_min=high_min)
        return item, sp, cat

    def _recommend(self, student_id: str, item: LearningPathItem,
                   sp: SpacingState, cat: int, src: dict,
                   bypass: bool) -> Recommendation:
        codes = list(item.reasons) + ["categoria:%d:%s" % (cat, CATEGORIES[cat - 1])]
        if sp.critical:
            codes.append("debilidad_critica")
        codes.extend("spacing:%s" % r for r in sp.reasons)
        if bypass:
            codes.append("inclusion_sin_alternativa")
        return Recommendation(
            student_id=student_id, knowledge_unit_id=item.knowledge_unit_id,
            unit_kind=item.unit_kind, priority_score=item.priority,
            action=item.action, difficulty=item.difficulty,
            reason_codes=tuple(codes), target_topic=item.target_topic,
            target_section=item.target_section,
            target_concepts=item.target_concepts,
            target_formulas=item.target_formulas,
            spacing_state=sp.to_dict(), policy_id=self.policy.policy_id,
            policy_version=self.policy.version, source_policies=dict(src))
