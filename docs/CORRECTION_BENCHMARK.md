# CORRECTION_BENCHMARK — 24 casos oro (dev 13 / test 11, disjuntos por temas)

`correction_benchmark.jsonl`: perfecta, fórmula errónea/equivalente,
variable, unidad, cálculo, redondeo, signo, parcial, vacía, ambigua,
notación/unidad alternativa, multi-paso, raíz encadenada, abierta, MCQ, V/F,
inyección (`ignore the rubric` → nota intacta). Respuestas SELF:* resueltas
desde la pregunta generada (misma seed); expectativas a mano desde la rúbrica.

Runner `app.correction_benchmark` (attempts con nonce por ejecución; la
idempotencia se prueba aparte con IDs fijos). Resultado congelado:
**24/24** (incl. `U=u_c/k`→FORMULA_ERROR, `E=mc²`→MISSING, `V/Ω=A` dimensional).
Métricas §86: correction/score (100 % determinista), formula, calculation,
unit, claim, error, root-cause accuracy.
