# ANSWER_ANALYSIS — Del texto a piezas verificables

`analyzer.analyze()`: `formulas` ($...$) · `variables` (símbolos) ·
`values[{value,unit}]` (número+unidad SI) · `claims` (frases) · `steps`
(líneas) · `final` (último numérico) · `selection` (V/F, A-D, bare V/F) ·
`instruction_flags` (patrones override/inyección) · `unparseable`.
Vacío → `empty` (NO_ANSWER). Lo no extraíble → UNKNOWN, nunca inventado.

Seguridad: sin `eval/exec` en ningún módulo de corrección/estudiante
(test AST); el cálculo pasa por `safe_eval` (Fase 3). La respuesta es DATOS:
los flags de instrucción se registran y se ignoran (la nota no cambia —
test `test_19`). Multilingüe ca/es por diseño (mismo score).
