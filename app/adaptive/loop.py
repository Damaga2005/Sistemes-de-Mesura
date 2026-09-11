"""AdaptiveLoop (Bloque B, §§16-17): cierra el bucle en UNA iteracion.

recommend() = prioridades -> path -> spacing -> recomendaciones.
step() = recommend() + generar la pregunta top con el Examiner.

Una llamada = una iteracion: NO hay agente infinito. Responder/corregir
usa StudentService.submit (API F5 existente); el siguiente step() relee
el estado actualizado. Sin LLM en ninguna decision.
"""
from __future__ import annotations

from dataclasses import replace

from .exam_adapter import to_generate_kwargs
from .models import Recommendation
from .modes import apply_mode_filter, mode_code, validate as validate_mode
from .path import LearningPathSelector
from .priority import PriorityCalculator
from .recommendations import RecommendationBuilder


class AdaptiveLoop:
    def __init__(self, student_service, *,
                 calculator: PriorityCalculator | None = None,
                 selector: LearningPathSelector | None = None,
                 builder: RecommendationBuilder | None = None) -> None:
        self.svc = student_service
        self.calc = calculator or PriorityCalculator(student_service)
        self.selector = selector or LearningPathSelector(student_service)
        self.builder = builder or RecommendationBuilder(student_service)

    def recommend(self, student_id: str, *, limit: int = 5,
                  unit_kind: str | None = None, seed: int = 0,
                  now: str | None = None,
                  mode: str = "PRACTICE") -> list[Recommendation]:
        m = validate_mode(mode)
        if m == "EXAM":
            raise ValueError("exam uses closed blueprint, not selection")
        prios = self.calc.calculate(student_id, limit=10000,
                                    unit_kind=unit_kind, seed=seed, now=now)
        path = self.selector.select(student_id, limit=max(limit, 1),
                                    unit_kind=unit_kind, seed=seed, now=now)
        recs = self.builder.build(student_id, prios, path, limit=limit,
                                  now=now)
        recs = apply_mode_filter(recs, self.svc, student_id, m, now=now)
        code = mode_code(m)
        return [replace(r, reason_codes=tuple(r.reason_codes) + (code,))
                for r in recs]

    def step(self, student_id: str, examiner_engine, *, limit: int = 3,
             seed: int = 0, now: str | None = None,
             origin: str = "GENERATED", novelty: bool = True,
             max_attempts: int = 5,
             mode: str = "PRACTICE") -> dict:
        """Una iteracion: recomendaciones + pregunta para la top-1.

        Si el Examiner rechaza (None + motivos), se devuelve el rechazo
        tal cual: mejor NO_GENERATION que pregunta debil (D44).

        novelty (Fase 8): evita devolver una pregunta que el estudiante
        ya vio. Reintenta con seed+1.. de forma determinista y acotada;
        si todo lo compatible ya fue visto, rechazo honesto
        `no_novel_question_available` en vez de loop infinito.
        novelty=False lo desactiva (repeticion explicita futura).
        """
        recs = self.recommend(student_id, limit=limit, seed=seed,
                              now=now, mode=mode)
        if not recs:
            return {"recommendations": [], "selected": None,
                    "generate_kwargs": None, "question": None,
                    "generate_log": {"rejected": "sin_recomendacion"}}
        top = recs[0]
        attempts = max(1, int(max_attempts))
        last_kwargs: dict = {}
        last_log: dict = {}
        for i in range(attempts):
            kwargs = to_generate_kwargs(top, seed=seed + i, origin=origin)
            q, log = examiner_engine.generate(**kwargs)
            if q is None:
                return {"recommendations": [r.to_dict() for r in recs],
                        "selected": top.to_dict(), "generate_kwargs": kwargs,
                        "question": None, "generate_log": log}
            qid = q.question_id if hasattr(q, "question_id") else q["question_id"]
            if not novelty or not self.svc.has_seen(student_id, qid):
                return {"recommendations": [r.to_dict() for r in recs],
                        "selected": top.to_dict(),
                        "generate_kwargs": kwargs,
                        "question": q.to_dict() if hasattr(q, "to_dict") else dict(q),
                        "generate_log": log}
            last_kwargs, last_log = kwargs, log
        return {"recommendations": [r.to_dict() for r in recs],
                "selected": top.to_dict(), "generate_kwargs": last_kwargs,
                "question": None,
                "generate_log": {**last_log,
                                 "rejected": "no_novel_question_available",
                                 "attempts": attempts}}
