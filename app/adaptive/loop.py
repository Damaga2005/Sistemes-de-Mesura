"""AdaptiveLoop (Bloque B, §§16-17): cierra el bucle en UNA iteracion.

recommend() = prioridades -> path -> spacing -> recomendaciones.
step() = recommend() + generar la pregunta top con el Examiner.

Una llamada = una iteracion: NO hay agente infinito. Responder/corregir
usa StudentService.submit (API F5 existente); el siguiente step() relee
el estado actualizado. Sin LLM en ninguna decision.
"""
from __future__ import annotations

from .exam_adapter import to_generate_kwargs
from .models import Recommendation
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
                  now: str | None = None) -> list[Recommendation]:
        prios = self.calc.calculate(student_id, limit=10000,
                                    unit_kind=unit_kind, seed=seed, now=now)
        path = self.selector.select(student_id, limit=max(limit, 1),
                                    unit_kind=unit_kind, seed=seed, now=now)
        return self.builder.build(student_id, prios, path, limit=limit,
                                  now=now)

    def step(self, student_id: str, examiner_engine, *, limit: int = 3,
             seed: int = 0, now: str | None = None,
             origin: str = "GENERATED") -> dict:
        """Una iteracion: recomendaciones + pregunta para la top-1.

        Si el Examiner rechaza (None + motivos), se devuelve el rechazo
        tal cual: mejor NO_GENERATION que pregunta debil (D44).
        """
        recs = self.recommend(student_id, limit=limit, seed=seed, now=now)
        if not recs:
            return {"recommendations": [], "selected": None,
                    "generate_kwargs": None, "question": None,
                    "generate_log": {"rejected": "sin_recomendacion"}}
        top = recs[0]
        kwargs = to_generate_kwargs(top, seed=seed, origin=origin)
        q, log = examiner_engine.generate(**kwargs)
        return {"recommendations": [r.to_dict() for r in recs],
                "selected": top.to_dict(), "generate_kwargs": kwargs,
                "question": q.to_dict() if q is not None else None,
                "generate_log": log}
