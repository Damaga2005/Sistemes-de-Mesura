# METADATA_CURATION — Completar sin inventar

## Estado medido (`data/metadata/curation_coverage.json`)

- Variables: 2652 propuestas (83 CONFIRMED por patrón definitorio `on X és`,
  resto PROPOSED). KB base: 205. **Lección registrada**: el patrón `amb X`
  generaba falsos positivos (`amb i/a` = conjunción) y se eliminó.
- Unidades: 181 glosario SI desde `tables_t` (CONFIRMED con tabla).
- Condiciones: 3921 candidatas (`si/quan/cal que`) en NEEDS_REVIEW.
- Overrides: capa derivada versionada con provenance; sin evidencia o
  revisor → rechazado. Fuente y hashes intactos (§136).

## Reglas

Propuesta = {formula, campo, actual, propuesto, evidencia, estado, motivo}.
UNKNOWN si no hay respaldo (§33). Curación manual CONFIRMED/REJECTED posible.
Cada campo curado responde ¿de dónde sale? (source+chunk+formula+review §137).
Tras confirmar: validación de fórmula/unidades/dimensiones + regresión (§135).
Benchmark `metadata_benchmark.jsonl` (8 casos verificados al generar).
