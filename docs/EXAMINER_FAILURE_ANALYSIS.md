# EXAMINER_FAILURE_ANALYSIS — Qué falla, por qué, y qué no se oculta

## Rechazos correctos (el sistema dice NO cuando debe)

- Integrales/f(x)/`e` ambigua → NUMERICAL bloqueado (honesto, medido en coverage).
- Blueprint sin evidencia, `formula_id` inexistente, distractores equivalentes,
  evidencia cross-tema mayoritaria, dominios inválidos → INVALID con motivo.
- Overrides (`usa E=mc²`, `ignora la evidencia`) → REJECT.

## Near-miss y deuda real

1. **Metadata 205/2896 variables, 0 unidades/condiciones**: el fato limita
   numéricos con unidades y dimensional completo → `UNIT_VALIDATION_UNAVAILABLE`
   (medido 100 % honesto, nunca PASSED falso). Fase 5+/curaduría.
2. **9 fórmulas degeneradas** (`_{}`, `$)$`...): recuperables (100 %) pero no
   evaluables; listadas con motivo, no ocultas.
3. **OPEN siempre con revisión humana implícita**: grounding garantizado,
   calificación pendiente (Fase 5 corrector).
4. **Generativo varía**: mismos checks lo contienen; prompts versionados.
5. **Paráfrasis profundas** (heredado F2): el banco usa redacción del material.

## Taxonomía §65 en la práctica

Todos los motivos observados en dev están en `reasons`/`examiner_results.json`;
cero `UNSUPPORTED_CLAIM`/`CONTRADICTED` en preguntas VALID; cero fugas a KB
(`knowledge.sqlite` bit-idéntico) y a eval (test de contaminación).
