# VERIFICATION_ARCHITECTURE — Claims, fórmulas, números, unidades

## Claims (9 tipos §23)

Toda claim necesita `evidence_ids`; sin citas → UNSUPPORTED. Verificación:

| Tipo | Regla determinista |
|---|---|
| FORMULA | `formula_id` canónico citado → SUPPORTED; latex suelto → `FormulaValidator` (exact/equivalent/MISMATCH); reescritura no canónica → CONTRADICTED |
| VARIABLE/UNIT | todos los términos en evidencia → SUPPORTED; mención sin definición → PARTIALLY |
| NUMERIC | número presente en evidencia → SUPPORTED; si no, PARTIALLY (el cálculo lo decide `verify_calculation`) |
| DEFINITION/FACTUAL/PROCEDURAL/COMPARISON/CONDITION | cobertura total de términos → SUPPORTED; parcial → PARTIALLY; nula → UNSUPPORTED |

Estados: SUPPORTED · PARTIALLY_SUPPORTED · UNSUPPORTED · CONTRADICTED.

## Fórmulas (`FormulaValidator`)

Canónica `canonical()`: `\,`/`\;` como producto implícito (antes de que
`normalize_latex` los borre), `·`/`×`→`*`. Equivalencia: igualdad, conmutatividad
de sumas/productos (`U=k·uc == U=u_c·k`) y reordenación con signo
(`a=b+c <-> a-b-c=0`). `U=uc/k` NO equivale. Desconocida (`E=mc²`, ausente
del temario) → MISSING. F=m·a, presente en T9, se acepta correctamente.

## Números y unidades

`verify_calculation`: AST validado (sin `eval`, rechaza `__import__`/`open`),
tolerancia relativa 1e-6 / absoluta 1e-9, chequeo dimensional SI
(`V/Ω=A` ✓, `V/(V/Ω)`✗). Conversiones por prefijo + °C-diferencia= K;
`°C` absoluto exige contexto. Cifras significativas: las de T2 §8
(existen en KB; se recuperan, no se asumen).

## Abstención tipada (§33)

NO_EVIDENCE · INSUFFICIENT_EVIDENCE · AMBIGUOUS · CONFLICTING_EVIDENCE
(incl. overrides adversariales) · UNSUPPORTED_FORMULA/VARIABLE/UNIT ·
CALCULATION_UNCERTAIN. Mensaje: `No he trobat evidència suficient...`
