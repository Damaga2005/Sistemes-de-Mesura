# PHASE_10_B6_BASELINE — Línea base pre-auditoría (B6.1, sin modificar)

Fecha: 2026-09-07. Commit: `b29a3c6` (+ trabajo F10-B2..B5 sin commit,
según regla del proyecto).

## Git

```text
M app/examiner/service.py (+2: guarda _gen_numerical, FIX B4)
M docs/DECISION_LOG.md (D146–D148)
M tests/adaptive/test_adaptive_loop.py (+84)
M tests/examiner/test_examiner_extra.py (+11)
?? app/application/ (capa F10)
?? app/application_workflow_benchmark.py + app/application_b5_benchmark.py
?? data/evaluation/phase_10_{workflow_benchmark,b5_benchmark}*.jsonl
?? docs/PHASE_10_{APPLICATION_DESIGN,WORKFLOWS,B5,B5_PREAUDIT}.md
?? tests/application/ (147 tests: 132 B4 + 15 B5)
```

## Suite (último verde certificado, B5)

```text
passed: 727 (712 B4 + 15 B5) · failed: 0 · skipped: 0 · deselected: 0
```

B6.18 re-ejecuta la suite completa; no se acepta parcial.

## Hashes sha256 (16 hex) + tamaño

```text
15a6d3fdef805f36 data/processed/knowledge.sqlite 4730880
d5811db08a0dd358 data/processed/chunks.jsonl 3313204
74f3e78f04271473 data/index/manifest.json 582
e28a1a9a94c4d4a4 data/source_manifest.json 46751
d3b09c462dd506ee data/evaluation/eval.sqlite 196608
d3234b6134e8a249 data/student/student.sqlite 450560
d0988f84b0768448 data/generated/questions.sqlite 376832
```

## Fórmula

2896/2896 vía artefacto `data/evaluation/formula_retrieval_results.json`
(tests de artefacto en suite).
