# PHASE_10_APPLICATION_PREAUDIT — Inventario para orquestación (B1)

## A. APIs públicas por servicio

- retrieval `retrieve_evidence(query, top_k, filters)` → EvidencePack
  (abstain incluido). Sin writes.
- reasoning `answer(query, lang)` → VerifiedAnswer + claims con estado.
  Sin writes (red solo si provider LLM).
- examiner `generate(**kwargs)` → `(Question|None, log)`; escribe
  questions DB (dedupe por fingerprint). `assemble_exam(...)` solo lee.
- correction `correct(...)` → `Correction` pura (no persiste sola).
- student `submit(...)` → persiste attempt+correction+mastery+memories
  (idempotente por `attempt_id`); getters puros.
- adaptive `calculate/select/build` puros; `AdaptiveLoop.recommend/step`
  (step genera vía engine inyectado).
- exam `ExamSessionService` (11 ops con máquina), `ExamGradingService.
  grade/get_result/get_question_result`, `ExamReviewService`
  (`get_review[_question]`, `get_mastery_view`, puros).
- llm `LLMProvider.generate` (solo red).

## B. Reutilizables tal cual

Todos los anteriores. Faltan como capacidad: orquestación multi-paso
con contexto de usuario (gap que justifica `app/application/`).

## C/D. Persistentes vs efímeros

Persistentes: KB, questions/exams, attempts/corrections/mastery/
memories/reviews, exam_specs/sessions/questions/answers/results/logs.
Efímeros: packs, blueprints no guardados, vistas, feedbacks,
recomendaciones, `ApplicationSession` futura (diseño B8).

## E/F/G. DB, efectos, idempotencia

KB/eval: lectura. questions: generate (dedupe). student: submit
(idempotente), exam tables (transiciones idempotentes), grading
(reanudable). Puros: retrieval/reasoning-answer/adaptive/review/
getters/assemble. Fallos: `ExamError` taxonómico, `NO_ANSWER`,
`ABSTAIN`, `RESULT_/REVIEW_NOT_AVAILABLE`, `GRADING_INCOMPLETE`
reintentable, `reasoning_unavailable`.

## H–K. Evidencia/sesión/provenance

Evidencia obligatoria en reasoning/examiner/correction/review;
sesión solo en exam; provenance encadenada por IDs en todas las
escrituras (attex-, correction body, attempts.exam_id).

## Veredicto B1

Diseño B2 viable sin duplicar: `app/application/` delgada con 5
workflows sobre estos contratos. GO a diseño.
