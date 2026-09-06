# PHASE_7_REVIEW — Bloque 5 (frontera GRADED → vistas, implementada)

`get_result` (B3, +`title`) → `get_review[get_review_question]` →
`get_mastery_view`, bajo `review-policy-v1` y autoridad única
(`check_view`, matriz B4 §8). Determinista, sin LLM, sin writes, sin
store, sin cache.

## Policy (`app/exam/review_policy.py`)

Frozen `review-policy@review-policy-v1`: 8 flags + `feedback_lang`
(ca|es) + `llm_explainer: "off"` (único valor válido). REAL_EXAM ciega
correct/solution/latex. Versión desconocida →
`REVIEW_POLICY_NOT_FOUND` (sin fallback). Cero tablas (D108).

## Vistas

- RESULT: `get_result[_question_result]` endurecido (+`title`,
  `exam_version`, `started_at`, `submitted_at`).
- REVIEW: `ExamReviewService.get_review[get_review_question]` —
  GRADED+COMPLETE o `REVIEW_NOT_AVAILABLE` (D104); `INCOMPLETE` y
  `GRADING_INCOMPLETE` no enseñan.
- MASTERY: `get_mastery_view` pedagógica (banda, motivo, evidencia,
  confianza) solo GRADED; probado cero writes/eventos.
- `StudentFeedback`: proyección whitelist (raíz+consecuencias vía
  `PROPAGATION`, bandas humanas ca/es, hints fijos, abstención
  `INSUFFICIENT_EVIDENCE`, latex solo canónico KB).

## Seguridad y provenance

Whitelist por campo (P0 §23 auditado); `provider/model` registrados
solo si el assist actúa (metadata, jamás raw/prompt/CoT); ownership
doble + scoping por `session_id` en cada API; `attex-`+body como origen
EXAM (D109); i18n por diccionarios con invariantes byte.

## Benchmark, tests, métricas

38/38 (`exam_review_benchmark.jsonl`: 34 exigidos + multilingüe,
abstención, bandas/taxonomía, mastery-view). Tests: 50 en
`test_exam_review.py` (~40 nuevos + benchmark). P0 del §63 medidos en
el informe final (todos 0/100% según exige).

## Límites

Sin historial/cache/Review→Practice/importer/UI; `review-policy`
futura se versiona (sin reinterpretación silenciosa); `NEEDS_REVIEW`
requiere regrade manual; multilingüe solo ca/es.
