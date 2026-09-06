# PHASE_9_PREAUDIT — Operational Readiness (solo auditado)

## Runtime (B1)

Cero `os.getcwd()/chdir` en `app/`: todo path ancla a `__file__`
(`WORKSPACE`/`ROOT`). Sin dependencia del directorio de trabajo.
Servicios reciben paths explícitos; tests usan tmp.

## Configuración (B1)

Valores consistentes hoy, con duplicación documentada (P2, sin drift):
versiones en sus modelos canónicos + referenciadas (`examiner-4.0` ×3,
`retrieval-2.0` ×4, `mastery-policy-v1` ×5, `rubric/grader-5.0` ×1,
`exam-spec-v1` ×4, `review-policy-v1` ×2); umbrales 0.4/0.7 en
`status_for` y `priority-policy` (intención heredada §12 diseño).
Clasificación: policies versionadas / env (`GEMINI_API_KEY` único) /
constantes de dominio / sin secretos en repo.

## Errores (B2)

Taxonomía determinista en todos los paths: `ExamError` con marcadores,
`CORRECTNESS` 6 estados, `NO_ANSWER`/`NEEDS_REVIEW` explícitos,
`ABSTAIN` con motivo, `RESULT_/REVIEW_NOT_AVAILABLE`,
`REVIEW_POLICY_NOT_FOUND`, `SNAPSHOT_INVALID`, `GRADING_INCOMPLETE`
con reintento. Bare-excepts auditados (F8): todos en dirección segura
(rechazar, omitir assist, degradar orden). Sin `except:` desnudo en
lógica de decisión. `return None/[]` solo en lookups con llamada que
falla cerrado aguas abajo (verificado).

## DB recovery + integridad (B3)

`integrity_check` OK + `foreign_key_check` OK en las 4 DBs. Patrón:
una conexión por operación con commit final (rollback implícito),
`submit` F5 con rollback explícito, grading reanudable idempotente.
Corrupción probada: pregunta ausente → `GRADING_INCOMPLETE` con sesión
intacta; JSON roto → excepción explícita (P2: envolver en `ExamError`).
Backup/restore: ficheros SQLite autocontenidos (copia = backup);
sin migraciones destructivas (solo `CREATE TABLE IF NOT EXISTS`).

## Concurrencia (B4, empírica)

Threads ×8 submits distintos: 8/8 OK. Mismo `attempt_id` ×6: 1 fresco
+ 5 replayed, 1 correction, 0 errores (UNIQUE + `OR IGNORE` aguantan).
Doble save/submit/grade: estados finales consistentes. Sin llamantes
concurrentes reales (sin capa web) → P2 se mantiene, ahora con
evidencia (era teórico en F8).

## Observabilidad (B5, diseño)

Eventos mínimos propuestos (sin implementar): `{ts, op, entity,
status, duration_ms, error_code}` en submit/grade/review/expiry;
jamás respuestas/claves/soluciones/CoT/secretos. Sin infra externa.

## Performance baseline (B5)

retrieval híbrido ~260ms · canal fórmulas ~300ms · submit
corrección+mastery ~28ms · `recommend` adaptativo ~11ms · suite ~6min ·
fórmula exhaustiva ~25min. Sin O(N²) inesperado; índices en PKs y
columnas de filtrado (maestría secundaria: P3). Sin SLAs inventados.

## Logging (B5/B25)

Sin framework ni `print` en servicios (solo CLIs operador: SAFE).
`audit_log` F5 registra `{correction, units}` sin contenido académico.

## Lifecycle (B7)

| Entity | Mutable | Immutable after |
|---|---|---|
| Question | no (dedupe) | creation |
| Exam | no | READY (frozen) |
| Session | solo estado+timestamps | — (máquina) |
| Answer | overwrite | SUBMITTED |
| Attempt | no | creation |
| Correction | no (+regrade versionado) | creation |
| ExamResult | no | GRADED |
| MasteryEvent | no | creation |
| Review | derivada | lectura |

## Versiones/providers (B8/B12)

9 versiones inventariadas (matriz F7-B6 vigente). Solo
`GEMINI_API_KEY` en entorno; core stdlib-only (ingesta PDF
fitz-or-pypdf con fallback, sin requirements: P3). `origin` en
adaptive es passthrough validado, jamás señal (REAL_EXAM boundary OK).
Reintentos 429/5xx + `reasoning_unavailable` explícito (observado en
vivo); assist sin proveedor → omisión segura.

## Aislamento/APIs/CLI (B9–B11, B14–B15)

Canónica única + tmp en tests; eval ciega; GENDB contenido validado;
REAL_EXAM sin vía a KB/adaptive/scoring. 19+10+9 métodos exam con
ownership/estado/efectos conocidos; lecturas puras (retrieval salvo
red, reasoning, review, adaptive); CLIs con exit codes; idempotencia
verificada por capa (ingest bit-idéntica, índices rebuild, benchmarks
re-ejecutables, submits/grades/reviews).

## Tests (B16)

578 con cobertura happy/negative/bordes/seguridad/determinismo/
idempotencia/aislamiento/corrupción. Entorno limpio (censo §49:
0 diffs; GENDB solo crece por vías validadas).

## Hallazgos

P0: 0. P1: 0. P2 nuevos: `JSONDecodeError` sin envolver; submit a
pregunta INVALID sin puerta (sin vía de descubrimiento); P2
heredados vigentes. P3: requirements, índices secundarios.
