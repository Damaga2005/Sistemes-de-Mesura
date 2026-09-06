# MASTERY_BENCHMARK — 12 historiales sintéticos autoverificados

`mastery_benchmark.jsonl`: [1×4]→MASTERED, [0×3]→AT_RISK, [1,0,1,0]→0.4783
DEVELOPING, [1]→EMERGING con confianza 0.125 (nunca MASTERED por 1 acierto),
rachas, alternancia, inactividad implícita. El generador ASEVERA cada valor
contra la política (si discrepa, aborta: el gold no puede mentir).

Métricas §87: determinismo (misma secuencia ×2 estudiantes), replay ==
estado, idempotencia por `attempt_id`, provenance (memorias con IDs),
confianza calibrada (1 intento → 0.125). Adversarial: un correcto, muchos
errores, alternancia, mismo error repetido (AT_RISK + perfil), fórmula bien
+ cálculo mal (raíz FORMULA, derivado cálculo).
