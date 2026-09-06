# QUESTION_GENERATION — Cómo nacen las preguntas (sin inventar)

## Rutas deterministas (defecto)

- **TRUE_FALSE**: frase de definición/explicación (V literal) o con concepto
  sustituido por otro tema (F), con la frase verdadera como justificación.
  La F se valida como no-soportada; si resulta soportada, se rechaza.
- **FORMULA/MCQ**: stem desde la sección + canónica + 3 distractores por
  transformaciones (signo, factor ×2/÷2, recíproco, permutación, subíndice).
  Unicidad verificada por `equivalent()` (ningún distractor válido).
- **NUMERICAL**: `to_python` (frac/sqrt/ln/implícitos; rechaza integrales,
  notación `f(x)`, `e` ambigua, construcciones raras) → valores seed
  (k∈{1,2,3}, N enteros; resto rangos sanos) → denominadores ≠0 →
  `safe_eval` → pasos Datos/Fórmula/Sustitución/Cálculo/Unidad/Resultado.
- **MULTI_STEP**: pares F1→F2 por símbolo compartido (hasta 40 candidatos,
  primer encadenable); el resultado alimenta F2 como `DERIVED_VALUE`.
- **SHORT_ANSWER/THEORY**: definición/explicación del chunk + conceptos.

## Ruta LLM (solo `--llm`, tipos abiertos)

Blueprint + evidencia → `question_generation_v1` → JSON estricto →
misma verificación. Sin JSON válido: `INVALID_GENERATION`, nunca texto libre.

## Valores (§18) y dominios (§22)

`GENERATED_TEST_VALUE` con seed, unidades (o ausencia honesta), sin absurdos
(tabla `k`/`N`), sin división por cero (reintento seed+7919 y si no, rechazo),
sin NaN/Inf, sin `sqrt/log` inválidos (el cálculo falla → rechazo).

## Seeds (§19)

Todo `random.Random(seed)` explícito; triple ejecución idéntica (test).
Nada de randomness global.
