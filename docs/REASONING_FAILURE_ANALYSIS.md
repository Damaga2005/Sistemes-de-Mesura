# REASONING_FAILURE_ANALYSIS — Fallos, near-miss y lecciones

## Fallos residuales (conocidos, acotados)

1. **RU01/RP01 con extractive** (70/72): el fallback copia el top-chunk sin
   componer (`ohm` no nombrado; `cobertura` ausente). Con Gemini ambos PASS.
   No es alucinación (VERIFIED sobre evidencia) sino infrarrespuesta.
2. **RF03-live**: el modelo reescribió coeficientes Steinhart (`a,b,c` por
   `A,B,C`) → validador estricto → ABSTAIN. Correcto por diseño (§16);
   mitigado con `reasoning_v2` (copia exacta + citar `formula_id`).
3. **RU05/RP01-live iniciales**: abstención sobre evidencia fina (menciones
   `dB` sin definición; procedimiento sin `pas a pas` literal). Tras v2:
   RU05 sigue exigente — documentado como conservadurismo sano.
4. **429 de API**: backoff ×3 + 1 s entre llamadas del benchmark.

## Lecciones de cobertura (52,5 % → 100 %, todas generales)

- Metadata SVG en chunks (Fase 1) · substrings (`units⊂unitats`) ·
  fuzzy (`president→precedent`) · `query_terms` rompía `{,}` ·
  minmax ocultaba debilidad (masa IDF) · `sorted()` destruía orden de unión ·
  `re.match` unilateral en vecinos · `\,` borrado pegaba símbolos (`ku_c`) ·
  `de/la` como "símbolos" (scores 1.05 fantasma) · `sorted(extra)` idem.

## Taxonomía §69 en test final

MISS 0 · WRONG_TOPIC 0 · WRONG_FORMULA 0 (canónicas) · WRONG_SOURCE 0 ·
DUPLICATE n/a · INSUFFICIENT_CONTEXT (RU01/RP01-extractive, acotado) ·
AMBIGUOUS 0 · FALSE_POSITIVE 0 · FAILURE_TO_ABSTAIN 0 · OVER_ABSTENTION 0
(fuera de RF03-live estricto, seguro por diseño).

## Divergencia extractive vs generativo (medida)

Extractive: conservador-compositivo (70/72, 0 tokens). Gemini: compone y
calcula (16/16) pero varía entre ejecuciones (RP01: `cobertura` vs `factor k`)
y a veces reescribe latex (→ abstención estricta). El verificador determinista
es el que iguala ambos: ninguna respuesta sin citas pasa.
