# PHASE_7_FINAL_PREAUDIT — Cierre arquitectónico Fase 7 (solo lectura)

Verificado contra código el 2026-09-05/06. Cero código, cero DB writes
(hashes §49 idénticos), cero commits. `file:line` salvo indicación.

## 1. Executive Summary

EXAM MODE cerrado y consistente F0–B5: 7 estados, snapshot por
referencia, scoring entero, F5 reutilizado sin duplicar, adaptive fuera,
review sin writes, 0 leaks, 2896/2896 en pie. Hallazgos: 0 P0, 0 P1,
9 P2 (3 de documentación, resto deuda menor instrumentada). Veredicto: GO.

## 2. Scope

`app/exam|examiner|correction|student|adaptive|reasoning|retrieval|llm`,
`data/`, `tests/`, `docs/`, 18 modelos F7-núcleo. Fuera: mejoras
cosméticas, Fase 8.

## 3. F0–F7 Compatibility

F0–F6 intactas post-F7 (suite ×2: 576+576 verdes): F7 solo añade
(`app/exam/`, +2 tablas B2/B3) y extiende aditivamente (3 params F5 con
defaults, filtros `assemble_exam` con defaults, 3 campos de lectura en
`get_result`). `test_09/10/B2-graded` actualizados al implementar lo que
describían (D61/D67/test B3, trazable). Flake D102 ajeno a F7 (mecanismo
caracterizado, 10/10 aislado).

## 4. Architecture Audit

5 stores/5 escritores verificados (§2 B1 real). Sin `ExamCorrectionService`
(grep vacío), sin adaptive en `app/exam` (1 mención en docstring), sin
`random.seed`/logging en servicios (prints solo CLIs), sin imports
benchmark en producción, sin refs al legado salvo 1 docstring. `submit()`
devuelve `Correction` rica (superficie interna sin capa web: P2 acotar a
futuro).

## 5. State Machine

Mapa cerrado y testeado (19 inválidas rechazadas): doble submit estable,
submit-post-expiry bloqueado, grade-pre-submit bloqueado, grade doble
idempotente, cancel-post-grade bloqueado, expiry-post-submit no-op,
review/result por matriz §17. `get_answers` sin puerta de estado es
intencional (respuestas propias siempre legibles).

## 6. Snapshot/Fingerprint

READY congela ids+fingerprints+body_sha+policies; re-verificación en
prepare/start/cada lectura; `SNAPSHOT_INVALID` bloquea. Tabla §7:
question incluye difficulty vía objective (sin colisión); origin/seed
excluidos por diseño (D54/§76); assemble `exam_id` ignora quotas
(mismo set → mismo id; REPLACE del registro F4 descriptivo: P2);
`exm-` canónico completo; sesión/attex/correction/event/state sin
huecos (práctica comparte `attempt_id` a propósito: misma evidencia).

## 7. Timer

`started_at` en start (nunca antes), `expires_at` server-side, `>=`
expira (borde testeado), sin reloj cliente (no hay capa web). Rollback
tolerante, jump expira (direcciones seguras). Naive→UTC asumido: P2
documentar. `duration=0` inválido, `null` sin límite.

## 8. Answers/Submit

Canónica = fila `session_answers` (upsert+versión); log append-only
(sin UPDATE/DELETE en código); blank `""` ≠ incorrecta; verbatim
(normaliza F5); post-expiry/submit/grading bloqueados; submit
idempotente con `submitted_at` estable.

## 9. Grading/Scoring

`Decimal`+HALF_UP, milesimas/centésimas enteras, porcentaje desde
milesimas (sin doble redondeo), denominador required, ABSTAIN sin regla,
cero-división y negativos imposibles por construcción, examen vacío
imposible. Agregación única `ORDER BY position`.

## 10. Correction Integration

`Exam→submit→CorrectionService→Correction` verificado
(`student/service.py:41,65`, `correction/service.py:77`);
taxonomía/rúbrica/numérica/fórmulas F5 sin duplicar; provenance en body.

## 11. Mastery

`submit→events→state` (F5); review 100% lecturas (test conteos);
80% examen ≠ 80% mastery (semántica por unidad preservada).

## 12. Adaptive Isolation

Cero imports/llamadas en `app/exam` (grep). Decisiones adaptativas
durante examen: 0 (no hay ruta de llamada).

## 13. Review

4 vistas auditadas campo a campo (§20 B4 + 38 casos B5): STEM 12 campos,
RESULT sin secretos por construcción, REVIEW con flags, MASTERY
pedagógica. `prompt`+opciones post-`GRADED` (D116). CoT inexistente en
stores (más fuerte que oculto).

## 14. Formula Integrity

Gate en pie (§24); review enlaza `formula_id→KB` sin generar ni
reescribir; `formula_review_resolution` por pregunta (R25–R28);
`2887 examable ≠ 2896 cobertura` consistente en docs (D40); 9
degeneradas bloqueadas con motivo, no borradas.

## 15. Provenance

Cadena completa verificable (G23/R30 + joins): exam_specs→sessions→
instances→answers/log→attempts(`exam_id`)→corrections(body con
`exam_id/session_id/provider`)→results→mastery_events(`attempt_id`).
Sin texto libre como único enlace.

## 16. Version Matrix

| Component | Version | Persisted | Replay | Review |
|---|---|---|---|---|
| Knowledge | fase1-1.0 | SÍ (meta) | fuente | SÍ (pin sesión) |
| Exam spec | exam-spec-v1 | SÍ (blueprint+policy) | SÍ (canónico) | SÍ (citada) |
| Examiner | examiner-4.0 | SÍ (pregunta+sesión) | SÍ | n/a |
| Grader | grader-5.0 | SÍ (corrección) | SÍ | SÍ (bloque) |
| Rubric | rubric-5.0 | SÍ (snapshot) | SÍ | n/a (DENY) |
| Correction | id contenido | SÍ (body) | SÍ (vía attempt) | SÍ (ids) |
| Mastery | mastery-policy-v1 | SÍ (evento+estado) | SÍ | resumida |
| Review policy | review-policy-v1 | NO (derivada; llamante fija) | SÍ (misma versión) | SÍ (citada) |
| Provider | nombre/modelo o "" | SÍ (si actuó) | SÍ | SÍ (bloque) |

## 17. Security Threat Matrix (T01–T20: riesgo/control/test/estado)

T01/T02 IDOR (medio/ownership doble/R08+R10+7-vectores/OK); T03 exam
(medio/sesión-scoped + cross-exam test/OK); T04–T08 leaks
(alto/whitelist+R11–R16+G22/0); T09 secretos provider (bajo/solo
metadata/R31/OK); T10/T11 cross-exam/session (alto/scoping+R09–R10+
cross-exam/OK); T12 cross-student (alto/R08+L24/OK); T13/T14/T15
contaminación (alto/solo-lectura+hashes+L22/R24+G24/OK); T16 replay
(medio/ids contenido+replay F5/OK); T17 snapshot (medio/re-verificación
triple+E13/OK); T18 timer (bajo/servidor+borde/E08/OK); T19 score
(medio/enteros+inmutabilidad+G15/OK); T20 mastery (medio/cero-writes
R29+L19/OK).

## 18. Database Audit

Canónica única `data/student/student.sqlite` (código solo recibe paths;
legado sin referencias funcionales). 6 tablas exam (PK compuestas,
índices, sin FK declaradas pero append-only sin DELETEs salvo rebuilds
pre-READY en-tx y limpieza de fallo). Sin dual-write/dual-read.

## 19. Concurrency Preaudit

submit×submit RISK (mismo contenido; `submitted_at` last-writer);
grade×grade SAFE (IGNORE+replay); submit+expire SAFE (cualquier orden
correcto); grade+review y review+mastery SAFE (lecturas). Sin llamantes
concurrentes (sin capa web) → sin BLOCKER.

## 20. Determinism

Mismo input+seed+policy+KB+versiones → mismo set/orden/score/resultado/
review/eventos (cross-process byte-idéntico B3/B5). Sin `random` global
(`Random(seed)` locales), sin iterar sets desnudos (grep), JSON
`sort_keys`, `ORDER BY` explícitos. `PYTHONHASHSEED` irrelevante
verificado por construcción.

## 21. API Audit

19 métodos públicos exam (7 lecturas puras). Ownership en cada uno con
`student_id`; restricción por estado; efectos solo donde corresponde
(save/submit/grade/cancel); idempotentes submit/grade/lecturas.
Superficie rica interna: `submit()` y cuerpos completos (P2 acotar en
capa web futura).

## 22. Test Coverage

~700 tests: happy/negative/bordes/seguridad/determinismo/aislamiento/
idempotencia cubiertos. Huecos P2: rama ABSTAIN (inaccesible por
validación), orphans (imposibles por construcción, tests por diseñar),
`INCOMPLETE`-review (requiere LLM offline-imposible), D102.

## 23. Documentation Consistency

F1: `EXAM_MODE_ARCHITECTURE.md` "(diseño, sin implementar)" parcial-
mente rancio (B2/B3/B5 implementados) + benchmark futuro superado. F2:
`PHASE_7_SESSION_CORE.md:5` "GRADED reservado" rancio. F3:
`PHASE_7_GRADING.md:57` "GRADING_INCOMPLETE reservado" infravalora
(error+limpieza+reintento implementados). P2 (solo estos 2 ficheros
editables; se registra aquí).

## 24. Remaining Gaps

9 P2: F1–F3 doc-debt; `_is_orphan` duplicada idéntica (`review.py:273`
vs `:286`, inocua); concurrencia teórica; naive-UTC; F4 exam_id ciego
a quotas; ABSTAIN/orphan/`INCOMPLETE` sin test offline; `submit()` rico
como borde futuro; D102.

## 25. P0

```text
(none) — 0 hallazgos bloqueantes
```

## 26. P1

```text
(none) — ningún P1 toca security/provenance/repro/scoring/correction/
mastery/formula/isolation
```

## 27. P2

Los 9 de §24, documentados y sin efecto en gates.

## 28. GO / NO-GO

```text
GO — P0 = 0. Fase 7 arquitectónicamente cerrada. No empezar Fase 8.
```
