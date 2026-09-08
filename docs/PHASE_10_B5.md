# PHASE_10_B5 — Integración real de workflows (RESULTADO GO)

## Alcance

B5 no implementa producto nuevo: `app/application/` y dominios quedan
intactos (cero ficheros certificados tocados). B5 aporta evidencia de
integración: preaudit, benchmark de 76 casos x2, 3 ficheros de tests
nuevos, regresión completa y veredicto.

## B5.1 Preaudit (solo lectura)

`docs/PHASE_10_B5_PREAUDIT.md`: tabla Entrada/Delegaciones/Estado/
Persistencia/Salida/Errores por workflow; 0 duplicación, 0 acceso
directo a DB (solo mapeo de errores), 0 circulares, `_own()` en toda
op con recurso, cross-student → `NOT_FOUND` (anti-enumeración, sin
`FORBIDDEN` en el vocabulario). P0: 0, P1: 0.

## B5.2–B5.14 Verificación

Contrato unificado ya existente (D141): `(ctx, session, kwargs)` →
`{"ok", "data"}` / `AppError`; SUCCESS / PARTIAL (`result.status`) /
ABSTAIN (`abstain` + `USER_ERROR`) / ERROR (códigos cerrados). Sin
clase base (no aporta valor). Scope, delegación por workflow,
frontera de errores, idempotencia y provenance verificados por
inspección + suite + benchmark. Recovery/determinismo con evidencia
nueva (RC/D + tests). Sin cambios de código.

## B5.15 Benchmark: 76/76 (run1 + run2 equivalentes)

`app/application_b5_benchmark.py` (reutiliza el motor B4 + pasos
`break`, `subprocess` real y proveedor roto) y
`data/evaluation/phase_10_b5_benchmark.jsonl`:
T01–T08 · P01–P10 · A01–A08 · E01–E08 · R01–R08 · X01–X08 ·
S01–S08 · RC01–RC05 · I01–I05 · V01–V05 · D01–D03.
Evidencia: `phase_10_b5_benchmark_run1.json` + `run2.json`.

Deltas fijados (conducta certificada, sin cambios): tutor fórmula →
VERIFIED + `formulas`; ambigua/fuera-KB → ABSTAIN; `query: 42` →
USER_ERROR (no str); proveedor roto → GENERATION_ERROR; idioma `fr`
→ VALIDATION_ERROR; resave pre-submit versiona (1, 2, gana última);
REAL_EXAM ciega (`correct_answer/solution/formula` = None, score
visible); `complete` x2 → STATE_ERROR (terminal documentado).

## B5.16 Matriz de tests

Existe (B3/B4): `test_application_core`, `test_{tutor,practice,
adaptive,exam,review}_workflow`, `test_cross_workflow`,
`test_application_security`, `test_application_provenance`.
Nuevos B5 (15 tests): `test_recovery.py` (5: exam/practice/adaptive/
review por `reopen_app` sin copiar GENDB + 1 subproceso real),
`test_idempotency.py` (6: x3 practice/exam/review, x2 tutor/
adaptive, `complete` no idempotente), `test_determinism.py` (4:
qid fijado + igualdad entre instancias exam/adaptive/tutor).
Nada anterior eliminado.

## B5.17–B5.19 Puertas

- Regresión: **727 passed, 0 failed** (712 B4 + 15 B5).
- Fórmula: **2896/2896** (tests de artefacto dentro de los 727).
- GENDB: benchmarks y tests en copias tmp; `questions.sqlite`
  canónica con contenido idéntico (`sha256 2547a6f8…`, restaurada).
- Aislamiento: KB y `eval.sqlite` intactas; `git status` solo muestra
  el FIX B4 + artefactos B4/B5 nuevos.

## B5.20 Métricas

```text
B5 benchmark: 76/76 (run1) = 76/76 (run2)
Determinism: PASS
Regression: 727 passed / 0 failed / 0 skipped
Formula: 2896/2896
Security: 8/8 (IDOR 6/6 dentro)
Provenance: 5/5
Idempotency: 5/5
Recovery: 5/5 (3 break + 2 subproceso real)
Isolation: PASS
P0: 0 / P1: 0 / P2: 2 (P2-1 THEORY-fallback, P2-2 cabecera GENDB) / P3: 0
```

## P2 (no bloqueantes, NO tocados por regla especial)

- P2-1: `FORMULA` sin `formula_id` → template THEORY con
  `type=FORMULA` (`app/examiner/service.py:66-78`).
- P2-2: la suite abre GENDB en RW (cabecera); contenido verificado.

## Limitaciones

Cross-topic en tutor no aplica (sin filtro de topic en `ask`);
`FORBIDDEN` no existe (contrato: `NOT_FOUND`); `complete` terminal
no idempotente (documentado en test).

## Veredicto

```text
B5 = GO
```
