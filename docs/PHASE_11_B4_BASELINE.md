# PHASE_11_B4_BASELINE — Contrato Exam UX auditado

## Frontera real

La UI llama a `web/server.py`, que delega en `ExamWorkflow` (F10). El
workflow delega en `ExamSessionService`, `ExamGradingService` y
`ExamReviewService` (F7). El navegador no accede a SQLite ni conserva
respuestas en storage local.

## Proyecciones públicas

- `GET /api/exam/mine`: sesiones del estudiante con título, tipo, estado,
  duración, número de preguntas y temas.
- `GET /api/exam/state`: estado backend, respuestas persistidas, snapshot
  inmutable y metadata segura; no incluye cuerpos de pregunta ni claves.
- `GET /api/exam/question`: vista STEM de F7.
- `POST /api/exam/save`, `/submit`, `/grade`: operaciones F7/F10, con errores
  contractuales y sin decisiones en JavaScript.
- `GET /api/exam/result`, `/review`, `/mastery`: vistas RESULT, REVIEW y
  MASTERY_VIEW separadas.

## Seguridad

La ownership se valida en la application boundary con el estudiante técnico
del contexto. El navegador nunca recibe `correct_answer`, `expected_answer`,
`solution`, prompts internos ni raw LLM. REAL_EXAM conserva la policy de
revisión ciega del backend.

## Limitaciones conocidas

- El endpoint de estado refleja la expiración cuando el backend la declara
  durante una operación contractual; el countdown del navegador nunca cambia
  el estado por sí mismo.
- La UI muestra “no disponible” cuando el backend no expone fórmula o review;
  no genera fallback ni reconstruye datos.

## Veredicto

`NO-GO`: el benchmark F11-B4 ejecutado dos veces fue determinista pero no
alcanzó 100/100. Los detalles y la clasificación están en
`docs/PHASE_11_B4.md`.
