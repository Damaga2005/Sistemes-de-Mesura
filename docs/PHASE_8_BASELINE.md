# PHASE_8_BASELINE — Estado al iniciar Fase 8 (solo medición)

Generado antes de cualquier cambio Fase 8. Repo sin commits (todo
untracked); `git diff` vacío. Sin commits durante ni después.

## Git y árbol

`git status --short`: `?? .gitignore, AGENTS.md, app/, data/, docs/,
tests/` (6 entradas, sin tracked). Paquetes: adaptive, correction,
curation, embeddings, exam, examiner, llm, reasoning, retrieval,
student (+CLIs sueltos). Tests espejo por paquete.

## Hashes (censo `phase8-baseline.json`, 39 claves)

- knowledge.sqlite `15a6d3fdef805f36`, 2896 fórmulas
- eval.sqlite `d3b09c44...`, chunks.jsonl `d5811db0...`
- source_manifest.json `e28a1a9a...`
- student.sqlite canónica presente (hash registrado)
- GENDB: 76 preguntas / 6 exámenes / 0 sintéticas / solo GENERATED +
  fingerprints de contenido estables
- `data/evaluation/*.json*` hasheados (detector de reescrituras)

## Tests: 576 passed, 2 deselected (LIVE Gemini, red OK el 06/09)

## Fórmula: 2896/2896, missed=0 (5 fragmentos, sin escrituras)

## Benchmarks (salidas en TEMP, artefactos intactos)

- retrieval dev: recall@5 1.0, abst P/R 1.0 · test: recall@5 1.0,
  abst 1.0/1.0, formula_recall@5 0.857 (P1 I03, re-baseline justificado)
- correction 24/24 · examiner det 37/38 (G35 diseño) + live 35/38
  (G35/G38 diseño, G09 rechazo-correcto del validador)
- answer extractive 70/72 (RU01/RP01 gaps D35 documentados)
- adaptive 20/20 + 24/24 · session 20/20 · grading 24/24 · review 38/38
- LIVE hallucination set (20, nuevo B5): 0 alucinaciones
  (6 abstenciones, 11 verdad-adyacente verificada, 2 resoluciones
  correctas, 1 corrección explícita de inexistencia)
