# PHASE_10_B6 — Auditoría final (RESULTADO: NO-GO condicional por P0 de F7)

## P0-1 — `grade` concurrente destruye el resultado (fase F7, NO F10)

- **Repro**: 2 hilos misma sesión 4/4 corrupto; 4 hilos 4/4; CC02 (n=4)
  rojo en run1 y run2. Secuencial perfecto (I02).
- **Mecanismo** (`app/exam/grading.py`): `grade()` sin exclusión
  mutua. El ganador commitea filas + `exam_results` + GRADED y
  devuelve 85.00. El perdedor, ya dentro de `_aggregate_and_store`,
  lee GRADED fresco → `transition()` lanza → `except` →
  `_cleanup_partial()` (120-131) **borra las filas COMMITTED del
  ganador** → re-lanza. Final: GRADED + 0 filas.
- **Daño**: `get_result` → RESULT_NOT_AVAILABLE; re-grade imposible
  (86/95); promesa "sesion intacta… reintentable" (115-117) rota;
  SUCCESS devuelto con datos perdidos (fail-loud violado).
- **Alcance**: solo grade‖grade misma sesión. Submit‖submit seguro
  (early-return). Resto de concurrencia PASS.
- **Acción**: NO MODIFICADO (regla: el fallo es F7). Reportado para
  bloque de F7. Guía sin aplicar: retorno temprano si `exam_results`
  existe bajo la misma transacción / `BEGIN IMMEDIATE` / cleanup solo
  con estado SUBMITTED+filas propias / re-grade sobre GRADED-sin-filas
  que recalcule en vez de lanzar.

## B6.17 Benchmark final: 119/120 run1 = 119/120 run2

`app/application_f10_final_benchmark.py` +
`data/evaluation/phase_10_final_benchmark.jsonl` (T/P/A/E/R/X/S×10,
RC/I/V×8, D/CC/RB×6, EB×8). Único rojo: CC02 (P0-1). Todo lo demás
verde en ambas pasadas, incluida concurrencia honesta (CC01, CC03–CC06
con hilos reales) y blind total (RB01–RB06).

## B6.18 Regresión: 728 passed + 2 failed externos

```text
728 passed / 2 failed / 0 skipped (730 total = 727 B5 + 3 concurrencia)
```

Los 2 fallos son `tests/reasoning/test_provider.py` LIVE: Google
responde **401 Unauthorized** (clave `GEMINI_API_KEY` presente en
entorno pero rechazada). Externo a F0–F10; B6 no toca producto ni
LLM; todo F10 corre extractivo. Sin relación con P0-1.

## B6.19 Static audit (`app/application/`)

TODO/FIXME/HACK/pass-crudo/pickle/eval/exec/subprocess/os.system/
`open(`/llm: 0. `sqlite3`: 4 líneas (mapeo a PERSISTENCE_ERROR,
VALID). `except Exception`: 5 sitios (código conocido o re-raise,
VALID). Runners (no producto): `subprocess`/`open` justificados
(harness de benchmark). Clasificación: todo VALID, 0 REVIEW+.

## B6.20 Métricas de certificación

```text
F10-B6 FINAL AUDIT

Baseline: b29a3c6 + F10-B2..B5 (hashes §B6.1, 7/7 intactos al cierre)
Final regression: 728 passed / 2 failed (live-key 401 externa) / 0 skipped
F10 benchmark: 119/120 run1, 119/120 run2 (único rojo CC02 = P0-1)
Formula: 2896/2896 (artefacto íntegro cd2acfed)
Security: 10/10
IDOR: 10/10
Real-exam blind: 6/6 (2 rutas)
Provenance: 8/8
Idempotency: 8/8 (create y complete documentados no-idempotentes)
Recovery: 8/8
Concurrency: 5/6 (CC02 = P0-1; modelo share-nothing PASS)
Determinism: 6/6 + run1=run2
Isolation: PASS (7/7 hashes)
Error boundary: 8/8 + 10 clases auditadas
Direct/Application equivalence: 4/4
P0: 1 (F7 grade concurrente)
P1: 0
P2: 3 (P2-1 THEORY-fallback, P2-2 cabecera GENDB, P2-3 conexión-por-hilo)
P3: 0
```

## Veredicto B6

```text
B6 = NO-GO (condicional, por P0-1 de F7)
F10 = NOT CERTIFIED (bloqueado hasta fix F7 + re-gates)
```

Todo lo propio de F10 está en verde. La certificación queda
pendiente de: fix en F7 (bloque específico) + re-ejecutar CC02,
I02/E10/RC07, regresión y benchmark final.

---

# F10-B6 RE-GATE AFTER F7 P0-1 (CERTIFIED)

Causa del NO-GO: P0-1 grade concurrente (F7). Fix: claim serializado (`BEGIN IMMEDIATE` + adopcion), `INSERT OR IGNORE`, cleanup propio (`docs/PHASE_7_P0_1_FIX.md`, D151). Sin locks Python; Abierto solo `app/exam/grading.py`.

Evidencia ejecutada en esta sesion:

- P0 CLOSED: `test_grading_concurrency` 10/10 (2h, 4h, x4, procesos, cleanup, incomplete-retry, submit, get_result, mastery)
- CC02 PASS · I02 PASS · E10 PASS · RC07 PASS
- F7 regression: 156 passed / 0 failed
- F10 benchmark: 120/120 run1 = 120/120 run2 (finales, sobrescriben los 119/120 del NO-GO)
- Full regression: 738 passed / 0 project failures / 2 deselected (LIVE_ENV_EXTERNAL: Gemini 401 confirmado)
- Formula: 2896/2896 (artefacto cd2acfed integro + 24 tests)
- Isolation: 7/7 hashes (KB, chunks, manifest, source_manifest, eval, student, GENDB contenido+restaurado)
- Security 10/10 · IDOR 10/10 · Blind 6/6 (2 rutas) · Provenance 8/8 · Idempotency 8/8 · Recovery 8/8 · Determinism 6/6 · Error 8/8 · Equivalence 4/4+X09 · LLM boundary estatico PASS
- Static audit: sin imports nuevos, sin catches nuevos, grafo Application->Domain intacto
- P0: 0 · P1: 0 · P2: 3 heredados no-blocking · P3: 0

Historial conservado: B6 fue NO-GO condicional hasta este re-gate; nada reescrito.
