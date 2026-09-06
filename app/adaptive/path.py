"""LearningPathSelector: prioridades -> ruta de estudio -> QuestionSpec (Bloque A).

Sin LLM, determinista total. Reglas (docs/PHASE_6_PRIORITY_DESIGN.md):

- Jerarquia (§10): la hoja (formula/concept) es el pick; si una hoja cubre
  un tema, los picks padres (section/topic) de ese mismo tema se omiten
  (una carencia = un pick, max no suma).
- Exploracion (§11): floor(limit * exploration_epsilon) slots reservados a
  formulas UNSEEN de temas ya tocados, ordenadas por (tema mas debil
  primero, n. de tema = orden curricular, equation_id). Solo formulas:
  su ID es estable y el loop de mastery las actualiza; los terminos de
  concepto libres no garantizan ese reencuentro (v1, documentado).
- Seed: aceptado por API y propagado a QuestionSpec; NUNCA altera el orden.
- Toda ponderacion vive en priority-policy-v1; la tabla accion->tipo es
  frozen v1 aqui (orquestacion determinista, §10 + error-directed §11).

Solo lee: student DB (mastery/attempts), generated questions DB y KB
(formulas.topic). Nunca escribe, nunca toca KB/eval.
"""
from __future__ import annotations

import json
import sqlite3

from app.examiner.models import DIFFICULTIES, QUESTION_ORIGINS, QUESTION_TYPES

from .difficulty import DifficultySelector
from .models import LearningPathItem, LearningPriority, QuestionSpec
from .priority import PriorityCalculator

# Tabla frozen v1 accion -> estrategia de tipo de pregunta (§10 + §11).
# La dificultad la pone DifficultySelector, nunca esta tabla.
_ACTION_STRATEGY_V1 = {
    "REVIEW": {"formula": "THEORY", "concept": "CONCEPTUAL",
               "section": "THEORY", "topic": "THEORY"},
    "PRACTICE": {"formula": "NUMERICAL", "concept": "CONCEPTUAL",
                 "section": "THEORY", "topic": "THEORY"},
    "REINFORCE": {"formula": "FORMULA", "concept": "CONCEPTUAL",
                  "section": "CONCEPTUAL", "topic": "THEORY"},
    "CHALLENGE": {"formula": "MULTI_STEP", "concept": "CONCEPTUAL",
                  "section": "CONCEPTUAL", "topic": "THEORY"},
    "MAINTAIN": {"formula": "CONCEPTUAL", "concept": "CONCEPTUAL",
                 "section": "THEORY", "topic": "THEORY"},
}
# Raices que fuerzan NUMERICAL aunque la accion diga otra cosa (§11).
_NUMERICAL_ROOTS = {"CALCULATION_ERROR", "UNIT_ERROR"}
_PARENT_KINDS = ("section", "topic")


def _ro(con_path) -> sqlite3.Connection:
    return sqlite3.connect("file:%s?mode=ro" % con_path, uri=True)


def _question_body(questions_path, question_id: str) -> dict:
    if not question_id:
        return {}
    con = _ro(questions_path)
    try:
        row = con.execute("SELECT body_json FROM questions WHERE question_id=?",
                          (question_id,)).fetchone()
    finally:
        con.close()
    if not row:
        return {}
    try:
        return json.loads(row[0])
    except ValueError:
        return {}


def _base_signal(name: str) -> str:
    """'UNIT_ERRORx2' -> 'UNIT_ERROR' (sufijo de recuento de priority)."""
    head, mark, _ = name.partition("x")
    return head if mark and _.isdigit() else name


class LearningPathSelector:
    def __init__(self, student_service, priority_calculator: PriorityCalculator | None = None,
                 difficulty_selector: DifficultySelector | None = None) -> None:
        self.svc = student_service
        self.calc = priority_calculator or PriorityCalculator(student_service)
        self.diff = difficulty_selector or DifficultySelector()

    # ---------- seleccion ----------
    def select(self, student_id: str, *, limit: int = 5,
               unit_kind: str | None = None, seed: int = 0,
               now: str | None = None) -> list[LearningPathItem]:
        """Ruta ordenada. `seed` no altera el orden (solo va a QuestionSpec)."""
        _ = seed
        if limit <= 0:
            return []
        eps = float(self.calc.policy.parameters["exploration_epsilon"])
        explore_n = int(limit * eps)
        if unit_kind not in (None, "formula"):
            explore_n = 0  # pool de exploracion v1: solo formulas
        prios = self.calc.calculate(student_id, limit=10000,
                                    unit_kind=unit_kind, seed=seed, now=now)
        items = self._main_picks(student_id, prios, limit - explore_n)
        if explore_n > 0:
            items += self._exploration_picks(
                student_id, limit=explore_n,
                exclude={i.knowledge_unit_id for i in items}, now=now)
        return items[:limit]

    def _main_picks(self, student_id: str, prios: list[LearningPriority],
                    n: int) -> list[LearningPathItem]:
        # §10: la hoja manda; el padre suprimido viaja como contexto en reasons.
        # Orden final = (priority DESC, unit_id ASC): estable y explicable.
        if n <= 0:
            return []
        leaves = [pr for pr in prios if pr.unit_kind not in _PARENT_KINDS]
        parents = [pr for pr in prios if pr.unit_kind in _PARENT_KINDS]
        keep = list(leaves[:n])
        covered: set[int] = set()
        for pr in keep:
            t = self.resolve_topic(student_id, pr.knowledge_unit_id)
            if t is not None:
                covered.add(t)
        for pr in parents:
            if len(keep) >= n:
                break
            t = self.resolve_topic(student_id, pr.knowledge_unit_id)
            if t is not None and t in covered:
                continue  # misma carencia que una hoja ya elegida (§10)
            keep.append(pr)
        kept_ids = {pr.knowledge_unit_id for pr in keep}
        suppressed_by_topic: dict[int, str] = {}
        for pr in parents:
            if pr.knowledge_unit_id in kept_ids:
                continue
            t = self.resolve_topic(student_id, pr.knowledge_unit_id)
            if t is not None and t in covered:
                suppressed_by_topic.setdefault(t, pr.knowledge_unit_id)
        out = [self._itemize(student_id, pr, explored=False,
                             context=suppressed_by_topic.get(
                                 self.resolve_topic(student_id,
                                                    pr.knowledge_unit_id)))
               for pr in keep]
        out.sort(key=lambda i: (-i.priority, i.knowledge_unit_id))
        return out

    def _itemize(self, student_id: str, pr: LearningPriority,
                 *, explored: bool, context: str | None = None) -> LearningPathItem:
        hist = self.svc.get_unit_history(student_id, pr.knowledge_unit_id)
        state = hist.get("state") or {}
        events = hist.get("events", []) or []
        qhist: list[dict] = []
        for e in events:
            q = _question_body(self.svc.questions.path,
                               e.get("question_id") or "")
            qhist.append({"difficulty": q.get("difficulty", "") or "",
                          "signal": (e.get("evidence") or {}).get("signal")})
        current = qhist[-1]["difficulty"] if qhist else ""
        d = self.diff.select(mastery=float(state.get("score", 0.0)),
                             confidence=float(state.get("confidence", 0.0)),
                             attempt_count=int(state.get("attempt_count", 0)),
                             history=qhist, current_difficulty=current,
                             recommended_action=pr.recommended_action,
                             status=state.get("status", "") or "")
        kind, _, ref = pr.knowledge_unit_id.partition(":")
        topic = self.resolve_topic(student_id, pr.knowledge_unit_id)
        section = ref.partition(":")[2] or None if kind == "section" else None
        if kind == "section" and (not section or not str(section).strip()):
            section = None
        reasons = list(pr.reasons) + ["dificultad:%s(%s)" % (
            d["difficulty"], ",".join(d["reasons"]))]
        if context:
            reasons.append("ancestro_en_contexto:" + context)
        if explored:
            reasons = ["exploracion_unseen"] + reasons
        return LearningPathItem(
            knowledge_unit_id=pr.knowledge_unit_id, unit_kind=kind,
            priority=pr.priority_score, action=pr.recommended_action,
            difficulty=d["difficulty"], target_topic=topic,
            target_section=section,
            target_concepts=(ref,) if kind == "concept" else (),
            target_formulas=(ref,) if kind == "formula" else (),
            reasons=tuple(reasons))

    # ---------- exploracion ----------
    def _exploration_picks(self, student_id: str, *, limit: int,
                           exclude: set[str], now: str | None) -> list[LearningPathItem]:
        touched = self._touched_topics(student_id)
        if not touched or limit <= 0:
            return []
        known = self._known_formula_units(student_id)
        con = _ro(self.svc.kb_path)
        try:
            rows = con.execute(
                "SELECT equation_id, topic FROM formulas ORDER BY topic ASC,"
                " equation_id ASC").fetchall()
        finally:
            con.close()
        scores = {t: self.svc.get_topic_mastery(student_id, t).get("score", 0.0)
                  for t in touched}
        pool = [r for r in rows
                if r[1] in touched and ("formula:" + r[0]) not in known
                and ("formula:" + r[0]) not in exclude]
        pool.sort(key=lambda r: (scores.get(r[1], 0.0), r[1], r[0]))
        cands = [("formula", eq) for eq, _ in pool[:limit]]
        if not cands:
            return []
        prios = self.calc.calculate(student_id, limit=len(cands),
                                    candidates=cands, now=now)
        return [self._itemize(student_id, pr, explored=True) for pr in prios]

    def _touched_topics(self, student_id: str) -> list[int]:
        touched: set[int] = set()
        con = self.svc.store.connect()
        try:
            for (uid,) in con.execute(
                    "SELECT knowledge_unit_id FROM mastery_states WHERE student_id=?",
                    (student_id,)).fetchall():
                if uid.startswith("topic:T"):
                    try:
                        touched.add(int(uid[len("topic:T"):]))
                    except ValueError:
                        pass
        finally:
            con.close()
        for a in self.svc.get_recent_attempts(student_id, limit=20):
            q = _question_body(self.svc.questions.path, a.get("question_id") or "")
            if isinstance(q.get("topic"), int):
                touched.add(q["topic"])
        return sorted(touched)

    def _known_formula_units(self, student_id: str) -> set[str]:
        con = self.svc.store.connect()
        try:
            rows = con.execute(
                "SELECT knowledge_unit_id FROM mastery_states WHERE student_id=?"
                " AND knowledge_unit_id LIKE 'formula:%'", (student_id,)).fetchall()
        finally:
            con.close()
        return {r[0] for r in rows}

    # ---------- resolucion de tema ----------
    def resolve_topic(self, student_id: str, knowledge_unit_id: str) -> int | None:
        kind, _, ref = knowledge_unit_id.partition(":")
        if kind in ("topic", "section"):
            try:
                return int(ref[1:3])
            except (ValueError, IndexError):
                return None
        if kind == "formula":
            con = _ro(self.svc.kb_path)
            try:
                row = con.execute("SELECT topic FROM formulas WHERE equation_id=?",
                                  (ref,)).fetchone()
            finally:
                con.close()
            return int(row[0]) if row else None
        if kind == "concept":
            hist = self.svc.get_unit_history(student_id, knowledge_unit_id)
            for e in reversed(hist.get("events", []) or []):
                q = _question_body(self.svc.questions.path,
                                   e.get("question_id") or "")
                if isinstance(q.get("topic"), int):
                    return q["topic"]
            return None
        return None

    # ---------- spec para el Examiner ----------
    def to_spec(self, item: LearningPathItem, *, seed: int = 0,
                origin: str = "GENERATED") -> QuestionSpec:
        """LearningPathItem -> QuestionSpec consumible por Examiner.generate()."""
        if item.target_topic is None:
            raise ValueError("sin tema resoluble para %r: no invento tema"
                             % item.knowledge_unit_id)
        if origin not in QUESTION_ORIGINS:
            raise ValueError("origin no válido: %r" % origin)
        qtype = self._strategy_for(item)
        if qtype not in QUESTION_TYPES:
            raise ValueError("tipo no válido: %r" % qtype)
        if item.difficulty not in DIFFICULTIES:
            raise ValueError("dificultad no válida: %r" % item.difficulty)
        return QuestionSpec(
            topic=item.target_topic, section=item.target_section or "",
            type=qtype, difficulty=item.difficulty,
            formula_ids=tuple(item.target_formulas),
            concept_terms=tuple(item.target_concepts),
            seed=seed, origin=origin)

    def _strategy_for(self, item: LearningPathItem) -> str:
        return strategy_for(item.action, item.unit_kind, item.reasons)


def strategy_for(action: str, unit_kind: str, reasons) -> str:
    """Tabla frozen v1 accion -> tipo de pregunta (§10 Bloque A + §11).

    Publica para reutilizarla en el adaptador a Examiner sin duplicarla:
    la dificultad la pone DifficultySelector, nunca esta tabla.
    `reasons` son los reason strings del item (para routing por raiz).
    """
    table = _ACTION_STRATEGY_V1.get(action, _ACTION_STRATEGY_V1["PRACTICE"])
    qtype = table.get(unit_kind, "CONCEPTUAL")
    if action == "REINFORCE":
        roots = {_base_signal(r.split(":", 1)[1]) for r in (reasons or ())
                 if r.startswith("raiz:") or r.startswith("raiz_repetida:")}
        if roots & _NUMERICAL_ROOTS:
            return "NUMERICAL"
    return qtype
