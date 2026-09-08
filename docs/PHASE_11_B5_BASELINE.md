# F11-B5 — Baseline Review / Results / History

## Preaudit

F7 ya proporciona `ExamResult`, `ExamQuestionResult`, `StudentFeedback`,
`ExamReviewService` y `get_mastery_view`. F10 expone esas lecturas mediante
`ReviewWorkflow` con ownership por `technical_student_id`. F7 también conserva
`created_at`, `started_at`, `submitted_at`, `expires_at` y `graded_at` en las
sesiones/resultados.

Antes de B5, la web tenía `/api/exam/mine`, `/api/exam/result`,
`/api/exam/review` y `/api/exam/mastery`, pero no tenía una proyección de
historial ni páginas directas de Results/Review. `exam.html` mezclaba resumen y
review y el resultado HTTP pasaba más campos de los necesarios.

## Límites

- No se crea persistencia de history.
- No se modifica F0–F10 ni la deuda conocida de SQLite read-only de Study.
- El navegador no calcula score, porcentaje, mastery, severidad, prioridad,
  provenance ni ciclo de vida.
- REAL_EXAM sigue usando la policy F7 y la whitelist de presentación B4-FIX.

## Deudas no bloqueantes

- Gemini live HTTP 401 = `LIVE_ENV_EXTERNAL`.
- Boundary SQLite read-only de Study = deuda F11-B2.
