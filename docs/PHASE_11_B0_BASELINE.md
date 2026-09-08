# PHASE_11_B0_BASELINE — Estado inicial F11 (solo lectura)

Fecha: 2026-09-07. F0–F10 certificadas (F10 CERTIFIED tras RE-GATE,
F7 P0-1 CLOSED). B0 no modifica nada.

## Ficheros modificados (heredados, certificados, sin commit por regla)

```text
M app/exam/grading.py (+claim serializado, FIX P0-1)
M app/examiner/service.py (+2, FIX B4)
M docs/DECISION_LOG.md (D146–D152)
M tests/adaptive/test_adaptive_loop.py (+84)
M tests/examiner/test_examiner_extra.py (+11)
+ app/application/, runners/benchmarks, tests/application/,
  tests/exam/test_grading_concurrency.py, docs de fase
```

B0 añade 0 modificaciones: verificado por `git status` antes/después.

## Hashes (idénticos a baseline B6)

```text
15a6d3fdef805f36 knowledge.sqlite · d5811db08a0dd358 chunks.jsonl
74f3e78f04271473 index/manifest · e28a1a9a94c4d4a4 source_manifest
d3b09c462dd506ee eval.sqlite · d3234b6134e8a249 student.sqlite
d0988f84b0768448 questions.sqlite · cd2acfed formula artifact
```

## Baseline ejecutado en B0

```text
tests/application/: 150 passed (85 s)
```

Suite completa no re-ejecutada (artefactos B6 vigentes:
738 passed + 120/120 ×2 + 2896/2896; repositorio inmutado).
