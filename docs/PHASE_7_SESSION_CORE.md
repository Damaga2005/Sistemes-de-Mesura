# PHASE_7_SESSION_CORE — Bloque 2 (núcleo persistente de sesión)

`ExamBlueprint → prepare_exam (READY) → create_session (CREATED) →
prepare_session (READY) → start (IN_PROGRESS) → get/save →
submit (SUBMITTED) | expiry/cancel`. Sin grading (`GRADED` reservado),
sin adaptive, sin LLM, sin corrección en este bloque (guardar ≠ corregir
≠ mastery; `submit` no crea attempts/corrections/eventos).

## Modelos (`app/exam/models.py`, `exam-spec-v1`)

`ExamBlueprint` frozen con `validate()` pura y `exam_id` derivado
(`exm-`+sha12 del canónico). `ExamSession`, `ExamQuestionInstance`
(id+fingerprint+body_sha+points+required, sin cuerpo duplicado),
`ExamAnswer` (`""` = BLANK futuro). `transition()` única autoridad;
`PAUSED` inexistente. `stem_view()` whitelist de 12 campos.

## Persistencia (aditiva, §3)

Seis tablas `exam_*`/`session_*`/`answer_log` en la student DB canónica
(`data/student/student.sqlite`, constante `CANONICAL_STUDENT_DB`).
`ExamStore` solo crea sus tablas (`CREATE TABLE IF NOT EXISTS`): cero
toques a F5, cero migraciones de datos, legado no referenciado.
`answer_log` append-only; la final es inequívoca (`session_answers`).

## Selección (extensión aditiva de `assemble_exam`)

Mismo comportamiento por defecto (43 tests examiner en verde):
+`sections` (prefijo), +`formula_ids`/`concept_terms` (cobertura dura que
cuenta en cuotas), +`order` unificado a B1 (`seeded_shuffle` por defecto,
`blueprint_order` por (topic,type,qid)). Cobertura reportada; `prepare`
exige shortfall 0 + cobertura total + todo VALID + provenance + dedupe,
o `EXAM NOT READY`.

## Snapshot, timer, submit (D78/D79)

Snapshot por referencia re-verificado en prepare/start/cada lectura
(fingerprint + body_sha; mismatch → `SNAPSHOT_INVALID`, sin continuar).
Reloj inyectable (`clock` o `now` explícito); `expires_at =
started_at+duration` (null = sin límite; 0 en blueprint = inválido);
restante 0 → `EXPIRED` con commit antes de rechazar (sin estados
parciales). `submit` idempotente (repite el resumen almacenado, cero
escrituras); tras `EXPIRED` no vuelve a `SUBMITTED`; `cancel` solo
pre-submit y sin borrado. Aislamiento por `student_id` en cada API y por
`session_id` en cada acceso.

## Benchmark y tests

`exam_session_core_benchmark.jsonl` (20/20) + runner con pool generado
determinista en DBs temporales (KB/índice reales solo lectura).
`tests/exam/`: 63 tests (20 casos + matriz validación + máquina
exhaustiva + anti-fuga + invariantes). F5 intacto: cero modificaciones
(`Correction.exam_id` queda para el bloque de grading).

## Deuda (no Bloque 2)

Grading/nota final/revisión; importador REAL_EXAM; `scoring-policy`
objeto (la declaración vive en el blueprint bajo `exam-spec-v1`);
`knowledge_version` sin estampar en `Correction`; endpoints/UI.
