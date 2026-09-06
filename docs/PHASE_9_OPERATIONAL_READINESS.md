# PHASE_9_OPERATIONAL_READINESS — Certificación operativa

## 1. Scope

Uso real repetido sin degradar lo certificado F0–F8. Sin UI/cloud/
multi-usuario/agentes (fuera de fase). Preaudit:
`docs/PHASE_9_PREAUDIT.md`.

## 2. Baseline

F8 + censo 39 claves; suite 576; fórmula 2896/2896; benchmarks por
salida. Cambios F8→F9, todos explicados: 5 artefactos re-baseline
(D129/D130), GENDB 76→89 por vías validadas (D132), student.sqlite
con filas `bench-*` del propio benchmark (D135). KB/eval/chunks/
manifest idénticos.

## 3. Runtime audit

Sin `getcwd/chdir`; paths anclados a `__file__`; servicios con paths
explícitos; tests en tmp. Config consistente (duplicación documentada
P2, sin drift).

## 4. Configuration

Policies versionadas + env único (`GEMINI_API_KEY`) + constantes de
dominio + cero secretos en repo.

## 5. Error handling

Taxonomía determinista por capa; bare-excepts auditados en dirección
segura; `return None/[]` solo en lookups con fallo cerrado aguas
abajo; rollback en escrituras F5/exam.

## 6. Database integrity

`integrity_check` + `foreign_key_check` OK en 4 DBs. Una conexión por
operación; grading reanudable; corrupción probada fail-closed
(`GRADING_INCOMPLETE`, JSON explícito). Backup = copia SQLite; solo
`CREATE TABLE IF NOT EXISTS`.

## 7. Recovery

Crash durante save/submit/grade/mastery: rollback o reintento
idempotente (probado: doble/triple submit/grade, replay). Sin
transacciones distribuidas (innecesarias: un solo fichero escribible
por flujo).

## 8. Concurrency

Empírica con threads: 8 submits OK; 6× mismo attempt → 1+5 replayed,
0 errores; doble save/submit/grade consistente. P2 se mantiene con
evidencia (sin llamantes concurrentes reales).

## 9. Observability

Diseño mínimo sin infra: `{ts, op, entity, status, duration_ms,
error_code}`; jamás respuestas/claves/soluciones/CoT/secretos.
`audit_log` F5 ya registra sin contenido académico.

## 10. Security

0 secretos en código/tests/docs; SQL parametrizado (2 restos
inaccesibles/dead → P2); sin path traversal (sin web); logs sin
framework (CLIs operador). Gates B19: 9×0 verificados en benchmarks.

## 11. Student isolation

Canónica única; A≠B en attempts/corrections/mastery/exams/sessions/
answers/reviews (tests). Legado sin referencias funcionales.

## 12. Evaluation isolation

Eval ciega y sin writes (hash idéntico); nunca alimenta mastery/
preguntas/KB.

## 13. Provider resilience

Reintentos 429/5xx + `reasoning_unavailable` explícito (observado en
vivo); assist ausente → omisión segura; core desacoplado
(`LLMProvider`); grading imposible con LLM (sin parámetro).

## 14. API contracts

19+10+9 métodos exam con ownership/estado/efectos; lecturas puras
donde corresponde; `submit()` rico como borde interno (P2 futuro web).

## 15. Idempotency

Verificada por capa: ingest bit-idéntica, índices rebuild, benchmarks
re-ejecutables, submits/grades/reviews idempotentes.

## 16. Test quality

578 (75+30+12+146+43+99+110+41+22) con happy/negative/bordes/
seguridad/determinismo/idempotencia/aislamiento/corrupción. Entorno
limpio (censo §49 repetido: 0 diffs).

## 17. Performance

retrieval ~260ms · corrección+mastery ~28ms · recommend ~11ms ·
suite ~6–9min · fórmula ~25min. Sin O(N²); sin SLAs inventados.

## 18. Remaining debt

P2 heredados + 2 nuevos (`JSONDecodeError` sin envolver, submit a
INVALID sin puerta — ambos sin vía de alcance, fail-loud). P3:
requirements, índices secundarios.

## 19. Certification gates

| Gate | Result |
|---|---|
| Formula coverage | 2896/2896 |
| Formula accuracy | 100% |
| Academic source integrity | PASS |
| Retrieval | PASS |
| Reasoning | PASS (extractive + live spot) |
| Examiner | PASS (det + live) |
| Correction | PASS (24/24) |
| Mastery | PASS |
| Adaptive | PASS (44) |
| Exam Mode | PASS (20+24+38) |
| Review | PASS |
| Security | PASS (9×0) |
| Isolation | PASS |
| Provenance | PASS |
| Determinism | PASS |
| Reproducibility | PASS |
| Database integrity | PASS |
| Recovery | PASS |
| Provider resilience | PASS |
| Full regression | PASS (578) |

## 20. Final verdict

```text
OPERATIONALLY READY
```
