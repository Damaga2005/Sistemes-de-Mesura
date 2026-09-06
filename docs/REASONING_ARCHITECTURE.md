# REASONING_ARCHITECTURE — Tutor verificable (Fase 3)

```
USER ──override?──abstain(CONFLICTING_EVIDENCE)
  │
  ▼
QueryAnalyzer (= Fase 2: classify + topic + idioma ca/es)
  ▼
RETRIEVER → EvidencePack (primary 3 + supporting + formulas + visuals + sources)
  ▼
LLM (Gemini 3.5-flash-lite t=0 JSON | extractive-fallback)
  ▼ structured {answer, claims[], formulas_used[], calculations[], needs_more_evidence}
  ├──needs_more──► SECOND RETRIEVAL (max 2 rondas, append sin duplicar) ──► LLM
  ▼
ClaimExtractor → ClaimVerifier (tipos §23) + FormulaValidator + Calculator
  ▼
SUPPORTED → ANSWER (VERIFIED/SUPPORTED/PARTIAL) · fallo → ABSTAIN tipado (§33)
```

## Separación (§72)

`retrieval/` (evidencia) · `reasoning/engine.py` (orquesta) · `reasoning/claims.py`
(verifica) · `reasoning/formula_check.py` (fórmulas) · `reasoning/calculator.py`
(cálculo+unidades) · `llm/` (proveedores) · procedencia en cada claim.
Ninguna clase `AIEverything`; el razonador no toca SQLite (§20: solo el pack).

## Presupuesto de evidencia (§21)

primary 5 chunks ×1500 + supporting 5 ×800 + 12 fórmulas + 5 visuales
(referencias, no binario). Señal/ruido medido: sufficiency retrieval 1.0.

## Confianza (§47-48, sin falsa precisión)

VERIFIED (todo SUPPORTED + fórmulas exactas + cálculos ok) · SUPPORTED ·
PARTIAL · UNCERTAIN · ABSTAIN. Construida de retrieval + verificación, nunca
solo del LLM. Fórmulas: EXACT_MATCH / EQUIVALENT_MATCH / MISSING / MISMATCH
(MISMATCH en respuesta dependiente ⇒ no VERIFIED).
