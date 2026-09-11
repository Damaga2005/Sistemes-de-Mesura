# PHASE_11_B4 — Exam UX

## Implementación

Se implementó la experiencia Exam UX sobre los contratos existentes:

- overview y creación con solo parámetros soportados;
- READY, start, active exam, navegación por snapshot, guardado backend,
  countdown visual y confirmación de entrega;
- estados SUBMITTED, GRADED, EXPIRED y CANCELLED;
- resultados, review y mastery como vistas separadas;
- recuperación por refresh/reentrada mediante estado persistido;
- layout responsive y controles semánticos con foco visible y `aria-current`;
- protección explícita de REAL_EXAM: la UI no presenta claves de respuesta.

La configuración y el estado se proyectan desde `ExamWorkflow`; la web no
consulta SQLite ni duplica selección, scoring, timer, review policy o mastery.
La metadata deja de depender de memoria del hilo y se recupera del snapshot
persistido.

## Evidencia

- Tests dedicados: `tests/web/test_exam_ux_contract.py`.
- Benchmark: `data/evaluation/phase_11_b4_exam_ux_benchmark.jsonl`, ejecutado
  dos veces con el runner F11-B4.
- Regresión obligatoria: `pytest tests/`.

## Gate — FIX aplicado

El NO-GO histórico queda cerrado quirúrgicamente en la capa de presentación.
El benchmark actualizado ejecuta `100/100` en RUN 1 y RUN 2, con payloads
idénticos. `MULTI_STEP` conserva la respuesta honesta `GENERATION_ERROR` del
backend cuando el caso no está soportado; no se simula soporte en la UI.

La revisión REAL_EXAM ya no transmite `formula`, `correct_answer`, `solution`
ni metadata de provider/model. No se modificaron scoring, grading, selección
ni generación de F7/F10.

Regresión completa: `802 passed`; los 2 fallos restantes son externos al
proyecto (`Gemini HTTP 401`). Fórmula `2896/2896` e aislamiento final PASS.

## Fase 7 — Practice Learning Loop Closure

Cierre del loop en modo adaptive reutilizando `AdaptiveLoop.step()`
(recomendación + generación canónicas, sin duplicar `to_spec` ni
`examiner.generate`). `PracticeWorkflow.submit_answer()` acepta
`adaptive: bool = False, seed: int = 7`; en manual `next` es `None`.
El DTO conserva feedback pedagógico existente (`feedback`,
`claims`, `formulas`, `calculations` sin `expected`, `units` sin
`expected`, `provenance`, `mastery_updates`); la sesión apunta a Q2
para el siguiente submit. Frontend: corrección muestra porqués,
cómo corregir y mastery; botón explícito de siguiente adaptativa
que conserva la corrección visible. Sin LLM en decisiones, sin
answer keys (`correct_answer`/`expected` jamás salen), fórmula
`2896/2896`, idempotencia intacta. Límite documentado: sin
historial visto-por-alumno (dedupe solo por fingerprint).
