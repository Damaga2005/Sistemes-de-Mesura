# CORRECTION_ARCHITECTURE — Evaluar sin inventar (Fase 5)

```
QUESTION (inmutable, generated) ── STUDENT ANSWER (datos)
        │                                    │
        ▼                                    ▼
QuestionEvidence ←──────────── ANSWER ANALYZER (formulas/variables/
(canonical solution,              valores+unidades/claims/steps/final;
formulas, conceptos)              instruction-flags; UNKNOWN si no extrae)
        │                                    │
        └─────────┬──────────────────────────┘
                  ▼
        DETERMINISTIC VERIFICATION (siempre primero)
        FormulaValidator · calculator AST · unidades+dimensiones ·
        ClaimVerifier · tolerancias de rubrica (1e-6/1e-9; redondeo 1%)
                  │
                  ▼ (solo criterios REASONING/INTERPRETATION en abiertas)
        LLM ASSIST (opcional): confirma o pide REVIEW con evidence_ids
        reales; jamas sube un 0 ni baja un 1 (validador siempre gana §74)
                  │
                  ▼
        RUBRIC (pesos explicitos, v1 por tipo) → SCORE reproducible
                  │
                  ▼
        ERROR CLASSIFIER (taxonomia + severidad + ROOT/DERIVED)
                  │
                  ▼
        FEEDBACK (plantillas por error: que/por que/como + evidencia)
```

Correccion (`Correction`) ≠ mastery (`MasteryState`): la primera dice que
paso en ESTA respuesta; la segunda, que evidencia acumulada hay. Pesos NO los
inventa el LLM (rubricas `rubric-*-v1`). Vacio → NO_ANSWER (nunca INCORRECT
por defecto); incierto → NEEDS_REVIEW (nunca WRONG, §120/§175).
