# PHASE_6_AUDIT — Cierre Fase 6 (Bloques A+B)

14 propiedades verificadas contra código + ejecución el 2026-09-05.
Base: benchmark 20/20 (core) + 24/24 (loop), suites 114 (adaptive+student)
y 428 total (2 LIVE ambientales deseleccionados), fórmula 2896/2896.

## Dependencias (1)

`adaptive` importa solo `examiner.models` (modelos, nunca el engine),
`student.policy` y `SEVERITY_TABLE` (`priority.py:10`). Cero menciones
`adaptive` en `examiner/`, `student/`, `correction/`; `loop.py` inyecta el
engine duck-typed sin importarlo.

## Conocimiento (2, 11, 12)

Cero escrituras en `app/adaptive/` (ningún INSERT/UPDATE/DELETE/CREATE;
única conexión sqlite `mode=ro`, `path.py:51`). `ingest.py` no referencia
`generated/`/`QuestionStore`: el flujo es unidireccional fuentes→KB.
Hashes idénticos pre/post Bloque B: `knowledge.sqlite 15a6d3fd…`,
`eval.sqlite d3b09c44…`, `chunks.jsonl d5811db0…`, `source_manifest
e28a1a9a…`, `questions.sqlite a96cbc64…` (L22/L23 + tests permanentes;
guardia `RuntimeError` anti-siembra en GENDB real).

## Comportamiento (3, 4, 5, 9, 10, 14)

- MASTERED→MAINTAIN residual (L07: 22.5), nunca excluido permanente
  (fallback `inclusion_sin_alternativa`, sonda solo-MASTERED).
- Criticidad→ALLOW en las 3 ramas incl. `debilidad_critica_sobre_spacing`
  (L03/L08/L12 + sonda + test).
- `seed` descartado en `calculate()`; doble ejecución + seeds 7/99 +
  byte-identidad entre procesos (AC20/L14 + test).
- `attempt_id` idempotente (L20 + F5); `replay` exacto en
  score/confidence/conteos (L19, `test_22`); `step()` sin bucles, grafo
  acíclico, 1 iteración por llamada (test).

## Pureza (6, 7, 13)

- Cero refs `REAL_EXAM`/`exam_frequency` en `adaptive/`; `origin` solo se
  valida (default GENERATED); mastery no ramifica por `origin`.
- LLM: 0 tokens en 6 módulos + 0 params proveedor (L21, re-verificado).
- Sin constantes ocultas (D75): `/2.0` y `×100` = fórmula frozen §5;
  `n<4`, `round 4`, `10000`, índices = estructurales; `[-4:]`, `≥0.5` =
  umbral de dominio F5; `confidence<0.5` = etiqueta cosmética de reason.

## Alcance (8, 13)

- Fórmulas 2896/2896 re-ejecutado post-Bloque B (`missed=[]` en los 6
  fragmentos; artefactos byte-idénticos).
- Cero Fase 7 (sin exam_mode/timer/dashboard/agents/FSRS/scheduler/hilos).

## Límites declarados (no hallazgos de bloqueo)

- `replay` no reconstruye `last_correct` (`""`) ni `error_counts` (`{}`)
  (diseño F5, D72).
- `last_correct` se vacía en submits no-correctos (F5, D72).
- Engine con `use_llm=True` inyectado podría redactar (capacidad F4);
  la decisión adaptativa sigue determinista.
- Conceptos sin historial abstienen tema; TUNABLEs sin calibrar.
