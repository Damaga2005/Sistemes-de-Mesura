# ERROR_TAXONOMY — Clasificación, severidad y causa raíz

16 tipos (§22): CONCEPT/FORMULA/VARIABLE/UNIT/DIMENSION/SIGN/ARITHMETIC/
ALGEBRA/ROUNDING/REASONING/INTERPRETATION/INCOMPLETE/AMBIGUOUS/
NO_JUSTIFICATION/WRONG_METHOD/WRONG_FINAL_RESULT. Severidad documentada en
`errors.SEVERITY_TABLE` (rounding→MINOR, unit→MODERATE, formula→MAJOR,
ley inventada→CRITICAL).

Causa raíz vs derivado (`PROPAGATION`): `FORMULA_ERROR` explica
`CALCULATION/ARITHMETIC/WRONG_FINAL_RESULT/UNIT/DIMENSION`; el perfil del
estudiante cuenta TODO lo observado pero el análisis causal usa raíces
(`derived_from`). Ejemplo medido: fórmula errónea + cálculo mal →
1 raíz + derivados marcados, no 4 errores independientes.
