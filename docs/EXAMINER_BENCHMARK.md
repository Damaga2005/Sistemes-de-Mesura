# EXAMINER_BENCHMARK — 38 specs + live (medido, no ajustado en test)

## Specs (`question_generation_benchmark.jsonl`)

38 fijos: dev = temas 1–5 (20), test = temas 6–10 (18, disjuntos). Cubren los
9 tipos + 4 dificultades. `--live` ejecuta los abiertos con Gemini (coste ~8
llamadas); el resto siempre determinista.

## Resultados congelados (deterministas)

- dev: **20/20 VALID** · test: **18/18 VALID** · `validation_pass_rate` 1.0
- `calculation_accuracy` 1.0 (re-chequeo independiente `safe_eval`)
- `fingerprints` únicos; `unsupported_claim_rate` 0 en generadas
- `data/evaluation/examiner_results.json` con detalle por spec

## Métricas §57 (dónde vive cada una)

`generation_success_rate`/`validation_pass_rate` (runner) · `evidence_support`
(validator `evidence_score`) · `formula_accuracy` (validador, 1.0) ·
`calculation_accuracy` (re-chequeo, 1.0) · `unit_accuracy` (dimensional donde
aplica; resto UNAVAILABLE honesto) · `provenance_rate` 1.0 · `ambiguity_rate`
(MCQ unicidad 1.0) · `duplicate_rate` (fingerprints) · `seed_reproducibility`
(triple, test) · `formula_coverage` 1.0 (gate F3) · `formula_examability`
0.9969 (2887/2896; 9 degeneradas documentadas).
