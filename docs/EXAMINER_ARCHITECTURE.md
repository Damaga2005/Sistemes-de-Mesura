# EXAMINER_ARCHITECTURE — Motor de evaluación verificable (Fase 4)

```
Knowledge Base ── Retrieval ── EvidencePack ── QuestionBlueprint ─┬─ Deterministic ─┐
(inmutable)      (Fase 2)       (Fase 2+§13)    (evidencia primero) │  TRUE_FALSE     │
                                                                   │  FORMULA/MCQ    │── Candidate
                                                                   │  NUMERICAL      │      │
                                                                   │  MULTI_STEP     │      ▼
                                                                   │  SHORT_ANSWER   │  Parse
                                                                   └─ THEORY (plant.)┘      │
                                                                    LLM (OPEN/teoría  ▼
                                                                    con --llm)      Verify
                                                                                        │
                                              ┌─────────────────────────────────────────┘
                                              ▼
                                    QuestionValidator (8 gates)
                                              │
                                   VALID / NEEDS_REVIEW / INVALID
                                              │
                                              ▼
                                    QuestionStore (data/generated/, separado)
```

## Capas (§5, §72)

`examiner/evidence.py` (KB→pack, sin eval DB) · `blueprints.py` (sin evidencia
no hay blueprint) · `staticgen.py` + `numerical.py` + `distractors.py`
(deterministas, seed) · `llmgenerator.py` + prompts versionados (abiertos) ·
`verify.py` (gate) · `store.py` (fingerprint idempotente) · `exam.py`
(ensamblado) · `service.py` (orquesta, `use_llm=False` por defecto).

## Decisiones

- Determinista primero: reproducible, gratis, verificable; LLM solo donde
  componer es necesario (OPEN/teoría con `--llm`), con la MISMA verificación.
- Dificultad desde rasgos (fórmulas/vars/pasos/opciones), nunca del prompt.
- Rechazar es correcto: blueprint sin evidencia, fórmula ausente/modificada,
  cálculo no reproducible, ambigüedad y evidencia cross-tema mayoritaria
  producen rechazo/NEEDS_REVIEW, nunca pregunta débil.
- `eval.sqlite` ciego al Examiner (test dedicado); KB bit-idéntica tras generar.
