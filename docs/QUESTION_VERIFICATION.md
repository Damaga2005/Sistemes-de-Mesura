# QUESTION_VERIFICATION — El gate que convierte candidatas en preguntas

## Pipeline (§48): parse → validate → verify → quality gate → VALID

1. **Evidence**: `evidence_refs` no vacíos y existentes.
2. **Provenance**: toda ref resuelve a chunk/fuente real.
3. **Topic coherence**: mayoría de evidencia del tema (transversal minoritario
   admitido y registrado; todo-foráneo → `EVIDENCE_TOPIC_MISMATCH` INVALID).
4. **Formula**: `formula_id` existe; latex afirmado == canónico o equivalente
   validado (la cita sola NO basta: `$U=u_c/k$` citando `eq-02-0034` es
   CONTRADICTED). Reescrituras del LLM se contrastan, no se confían.
5. **Claims**: `ClaimVerifier` Fase 3 (SUPPORTED/PARTIALLY/UNSUPPORTED/
   CONTRADICTED); académicos malos → INVALID.
6. **Calculation**: bandera `verified` de generación determinista + re-chequeo
   independiente en benchmark (`safe_eval` vs resultado).
7. **Units**: metadata real o `UNIT_VALIDATION_UNAVAILABLE` (nunca PASSED
   falso); dimensional cuando hay unidades.
8. **Unique answer**: MCQ exactamente 1 correcta (equivalencia incluida).

## Veredicto (§30)

`VALID` (todo) · `NEEDS_REVIEW` (solo no-fatales) · `INVALID` (cualquier fatal:
fórmula/cálculo/fuente/claim/unidad/contradicción/datos/ambigüedad).
`evidence_score`: fully/partially/unsupported.

## Adversarial (§50/§78-79)

Batería de 10 candidatos envenenados (fórmula/unidad/signo/factor/variable/
fuente/claim/facto-externo/ambigüedad/numérico) → todos REJECT con motivo.
Overrides (`usa E=mc²`, `ignora la evidencia`) → REJECT. Evidencia con
`IGNORE...` = datos (test de inercia). F=m·a SÍ está en T9 (el validador la
encuentra; E=mc² no).
