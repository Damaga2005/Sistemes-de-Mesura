# FORMULA_VERIFICATION — Cobertura 100 % y exactitud

## Inventario

2896 fórmulas canónicas (`data/processed/formulas.jsonl`): 2858 `latex-comment`
+ 38 `unicode-sub-sup` (T1). Solo 205 traen variables extraídas (evidencia
local `on X és…`); el resto `[]` + Fase 4. Unidades/condiciones por fórmula:
no extraídas aún (limitación declarada).

## Gold (`data/evaluation/formula_retrieval_benchmark.jsonl`, 2896 filas)

Queries mecánicas por registro (sin excepciones por query §2): símbolos
(`U k u_c`), sección (`4Incertesa típica…`), núcleo latex (`R_3=R_1\|R_2`).
Cada fila: `formula_id/topic/section/latex/variables/units/source_id/
acceptable_queries/retrieved_by/rank`.

## Canales generales que suman el 100 % (52,5 % → 100 %)

1. **Lookup exacto** (`covers`, plegado `uc↔u_c`, `IB==ib`, `U!=u`): +símbolos
   crudos (query_terms rompía `{,}`) + unión al pack con contexto.
2. **Secciones nombradas** → sus fórmulas al pack (ordenadas por solape).
3. **Substring latex** (`sqrt{3}`, `-34`) para núcleos numéricos.
4. **Normalización**: elisiones (`l'arròs`), números pegados (`3Angle`),
   `d`/`l` fuera de protegidos, FTS math-punct, stems catalanes.
5. `has_lookup` suprime abstención por masa/OOV (nunca por Tema 20).

## Gate (§86)

```text
FORMULA RETRIEVAL / Total: 2896 / Retrieved: 2896 / Missed: 0 / Coverage: 100.00%
```

`python3 -m app.formula_benchmark` (~15 min). Regresión 100 %→x :
`tests/reasoning/test_formula_coverage.py` (gold completo + spot vivo con seed).

## Exactitud

Las respuestas devuelven registros canónicos (nunca reconstrucciones del LLM).
`FormulaValidator`: EXACT (canónico citado), EQUIVALENT (conmutado),
MISMATCH→abstención. `U=2·uc` sin `k=2` evidenciado = unsupported.
