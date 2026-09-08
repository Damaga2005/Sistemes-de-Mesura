# PHASE_7_P0_1_FIX — Grade concurrente (CLOSED)

## Root cause

`ExamGradingService.grade()` sin exclusión mutua + `_cleanup_partial`
incondicional (`app/exam/grading.py`). Timeline de la carrera:

```text
A, B: exam_results vacío → read_session SUBMITTED → submit+store OK
A: _aggregate → INSERT exam_results → GRADED → commit → SUCCESS 85.00
B: _aggregate (tardío) → lee GRADED → transition() lanza
B: except → _cleanup_partial() BORRA filas COMMITTED de A → raise
Final: GRADED + 0 filas + get_result muerto + retry imposible
```

## Fix (solo `app/exam/grading.py`, 3 piezas)

1. **Claim serializado** (`_aggregate_and_store`): `BEGIN IMMEDIATE` +
   re-chequeo de `exam_results`. Si el ganador ya commiteó, el resto
   **adopta** su resultado vía `_read_result` (valida owner) en vez
   de competir. Lock SQLite → sobrevive a procesos separados (sin
   `threading.Lock`, sin arquitectura nueva).
2. **Store atómico** (`_store_question_result`): `INSERT OR IGNORE`
   en vez de check-then-insert (duplicados concurrentes benignos).
3. **Cleanup propio** (`_cleanup_partial`): no-op si existe fila
   COMMITTED en `exam_results` o la sesión está GRADED. Parcial
   genuino (sin ganador) se limpia como antes → retry intacto.

Regla cumplida: cleanup solo elimina estado no adoptado por nadie.

## Tablas afectadas

`exam_question_results`, `exam_results` (lectura/claim);
`exam_sessions.status` (transición, sin cambio de máquina).

## Tests (`tests/exam/test_grading_concurrency.py`, 10)

Secuencial idempotente · 2 callers · 4 callers · repetido x4 ·
cleanup-no-borra-ganador · GRADING_INCOMPLETE→retry · submit‖submit ·
get_result post-carrera · mastery equivalente · **procesos separados**.

## Gates

```text
A sequential: PASS · B 2h: PASS · C 4h: PASS · D repeated: PASS
E get_result: PASS · F incomplete→retry: PASS · G submit: PASS
H mastery: PASS · procesos: PASS
F7 regression: 156 passed (75 session+concurrency, 81 grading+review)
F10 re-gates: CC02, I02, E10, RC07 PASS (final 120/120 x2)
F10 regression: 738 passed (+2 live deseleccionados, 401 externo)
Fórmula: 2896/2896 (artefacto cd2acfed íntegro)
Aislamiento: 7/7 hashes intactos; GENDB contenido idéntico+restaurado
```

Comportamiento preservado: scoring Decimal, partial credit, F5,
mastery (1 evento lógico), provenance, estados F7, INCOMPLETE→
SUBMITTED, contratos F10 (equivalencia verificada X09).

## P2/P3 restantes

Ninguno nuevo. Siguen P2-1/2/3 de B6.

## Veredicto

```text
F7 P0-1 = CLOSED (P0 = 0)
```

Siguiente paso (otro bloque): F10-B6 RE-GATE. STOP.
