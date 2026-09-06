# PHASE_7_GRADING — Bloque 3 (corrección F5 → resultado → mastery única)

`SUBMITTED|EXPIRED → grade() → [submit F5 por posición] →
ExamQuestionResult → ExamResult → GRADED (si COMPLETE) + mastery (la de
F5, una vez)`. Sin corrector paralelo, sin nota por LLM, sin tocar
scoring/mastery/taxonomía F5.

## Integración F5 (aditiva, backward-compatible)

- `Correction.exam_id/session_id` (`correction/models.py:73`, defaults
  `""`); `correct(..., session_id="")` (`service.py:77`);
  `submit(..., session_id="")` (`student/service.py:41`) lo propaga.
- Por pregunta: `attempt_id = attex-sha12(session|position|qid|answer)`
  (determinista por sesión: re-grade rejuega, otra sesión no colisiona).
- `save ≠ correction ≠ mastery` intacto: mastery nace solo del `submit`
  del grading, con las señales F5 (`NO_ANSWER`→sin señal, parcial→0.5).
- `ExamResult 80%` no implica `Mastery 80%`: el score F5 por pregunta
  alimenta mastery por unidad con su semántica propia (D45).

## Scoring entero (B1: milesimas, HALF_UP)

`thou(score, points)` y `pct_hundredths()` en `Decimal` exacto
(`round(2.675,2)==2.67` flotante justifica no usar `round()`).
`points_earned = score/10 × points`; examen sobre required
(`optional_*` informativo; `required=False` sin regla = blueprint
inválido, ABSTAIN §16). Parcial = el de F5 (FORMULA 6.0, NUMERICAL 7.5…
documentado, no inventado). Cero denominador → 0 sin NaN.

## Resultado e idempotencia

`ExamResult{COMPLETE|INCOMPLETE}` + `origin_status{SUBMITTED|EXPIRED}`.
`INCOMPLETE` = revisión pendiente (nunca 0 silencioso, D83); entonces la
sesión queda `SUBMITTED` (GRADED exige COMPLETE, §34). Re-grade devuelve
lo almacenado (`graded_at` estable); submits rejuegan sin duplicar
attempts/corrections/mastery (triple grade probado). Atomicidad por
composición idempotente: F5 confirma por pregunta; el bloque examen
(resultados + flip a GRADED) es una transacción; reintento seguro.

## Lectura y anti-fuga

`get_result`/`get_question_result` solo post-submit con resultado;
`IN_PROGRESS` → `RESULT_NOT_AVAILABLE`. Sin secretos: ids, puntos,
estados, conteos, timestamps, versiones. Sin `correct_answer`,
soluciones, rúbricas, criterios ni prompts.

## Tablas, benchmark, tests

`exam_question_results(PK session,position)` + `exam_results(PK
session)`. Benchmark 24/24 (`exam_grading_benchmark.jsonl`, pool
autocontenido: GENDB real ni se copia). Tests: 97 en `tests/exam/`
(benchmark + scoring + F5-aditivo + puertas + cross-process).

## Límites

Sin revisión avanzada/UI/importador; sin `scoring-policy` objeto (la
declaración viaja en el blueprint bajo `exam-spec-v1`); `NEEDS_REVIEW`
requiere regrade manual futuro; `GRADING_INCOMPLETE` reservado para
fallo inesperado del pipeline (rollback a `SUBMITTED`, D97).
