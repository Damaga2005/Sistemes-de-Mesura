# RUBRIC_ARCHITECTURE — Criterios objetivos y trazables

Rúbricas por tipo (`rubric-<tipo>-v1`, versión `rubric-5.0`), p. ej. numérica:
Formula 20 % · Variables 15 % · Sustitución 15 % · Cálculo 25 % · Units 10 % ·
Result 10 % · Interpretation 5 %. Pesos explícitos en código, nunca del LLM.

Tipos: CONCEPT·FORMULA·VARIABLES·UNITS·CALCULATION·REASONING·INTERPRETATION·
FINAL_RESULT·COMPLETENESS·PRECISION. Cada `CriterionResult`: score 0..1,
estado, `evidence_ref`, detalle y fuente (deterministic|llm-assisted).

Versionado: la rúbrica viaja serializada en cada corrección (`rubric_snapshot`
+ `rubric_version`); v1 jamás se edita (v2 si cambia la lógica, §146).
Regrade conserva historial v1→v2 con motivo. Nota = Σ(score·peso), 0..10.
