# QUESTION_SCHEMA — Modelo de datos (§6)

Tipos: `THEORY|CONCEPTUAL|FORMULA|NUMERICAL|MULTIPLE_CHOICE|TRUE_FALSE|
SHORT_ANSWER|OPEN|MULTI_STEP`. Dificultad: `EASY|MEDIUM|HARD|EXPERT`
(observables §8). Validación: `VALID|INVALID|NEEDS_REVIEW`. Fallos: taxonomía
§65 + `EVIDENCE_TOPIC_MISMATCH` (mayoría de evidencia fuera del tema).

## Question (JSON completo en `body_json`, columnas de cobertura aparte)

`question_id` (`q-`+12 hex del fingerprint) · `version` (4.0) · `topic/section` ·
`type/difficulty` · `prompt` · `options[{text,correct,distractor_reason,
formula_id}]` · `correct_answer/expected_answer` · `solution{final_answer,
reasoning_steps,formula_application,calculation{expression,result,verified,
unit},interpretation}` · `hints` · `formula_ids/concept_terms` ·
`source_refs/evidence_refs` (chunks) · `variables{sym:{value,unit,kind}}`
(`SOURCE|DERIVED|GENERATED_TEST_VALUE`) · `units` (`__status__` honesto:
`UNIT_VALIDATION_UNAVAILABLE` si no hay metadata) · `conditions` ·
`claims[{text,type,status,evidence_ids}]` · `validation{status,reasons,
evidence_score,checks}` · `generator_version/prompt_version/seed/fingerprint`.

## QuestionBlueprint

`topic/section/type/difficulty/objective/formula_ids/concepts/variables/
units/conditions/expected_reasoning_steps/answer_constraints/seed`.
Se construye SOLO con evidencia verificada; sin ella no existe blueprint.

## Fingerprint (§35)

`sha256(topic|section|type|objective|formula_ids|concepts|prompt-normalizado)`.
Mismo fingerprint → `put()` es no-op (idempotencia §76).

## Exam

`exam_id` (`ex-`+12 hex de seed|topics|ids|versiones) · `seed` ·
`blueprint{topics,count,types,difficulty}` · `question_ids` · `versions
{examiner,knowledge,retrieval,reasoning}`. Reproducible bit a bit (§40).
