# PHASE_6_ADAPTIVE_LOOP — Bloque B (cierre del bucle, sin LLM)

`recommend → generate → submit → correction → mastery → next`.
`AdaptiveLoop.recommend()` + `AdaptiveLoop.step()` (una iteración por
llamada; sin agente infinito). Responder/corregir reutiliza
`StudentService.submit` (F5); el siguiente `step()` relee el estado.

## Spacing (`spacing-policy-v1`, activa)

Buckets discretos sobre días desde `last_attempt` (`buckets_days [1,7,30]`
→ VERY_RECENT/RECENT/NORMAL/OLD; `n==0` → NEVER_SEEN). Sin decay, sin
fórmulas ocultas. Estado 100% derivado de mastery+eventos (nada nuevo
persistido): `last_seen/last_correct/attempt/success/failure/mastery`.

Veredicto: `DEFER` solo si no-crítica + `last_correct` ≤7d + última señal
no es fallo. `ALLOW` en otro caso. Criticidad (cualquiera basta):
`AT_RISK`, `mastery<0.4` con `n≥2`, o raíz causal con `mastery<0.7` y
`≥2` fallos. **Debilidad > spacing siempre** (§9 verificado L08/L12).

Límite conocido (F5, sin cambios): `last_correct` solo sobrevive al submit
que lo establece (signal ≥0.99); un submit posterior no-correcto lo vacía
(`_update_mastery` no recarga `prior.last_correct`). Spacing lo trata como
disponible; el fallo fresco domina igual. No se toca F5 por esto.

## Recommendation + Builder

`Recommendation` (§6 completo + `source_policies` con las keys vivas de
`priority/difficulty-policy@v1`; `policy_id/version` = spacing, la
política propia del Builder). Sin texto libre de LLM.

`RecommendationBuilder.build()`: picks del path como base; las prioridades
solo rescatan (backfill) unidades ausentes — críticas o ALLOW hasta
`limit`; padres cubiertos por hojas conservadas nunca resucitan (§11);
dedupe por `unit_id` (primero en orden gana); orden (categoría, priority
DESC, unit_id ASC); categorías 1–6 (§8, CHALLENGE/REVIEW → práctica
normal); fallback determinista `inclusion_sin_alternativa` si todo es
DEFER (el tutor siempre recomienda algo, y lo declara).

## Adapter + Loop

`to_blueprint()` / `to_generate_kwargs()` → `ExaminerEngine.generate()`.
`learning_objective` = plantilla `ACCION:unit_id` (no LLM, no decisión).
Límite honesto: el Examiner no filtra por concepto; `target_concepts`
viaja como provenance + routing CONCEPTUAL. `step()` devuelve
recomendaciones + kwargs + pregunta (o rechazo tal cual, D44).

## Benchmark (24 casos L01–L24)

`data/evaluation/adaptive_loop_benchmark.jsonl` +
`app/adaptive_loop_benchmark.py` → `adaptive_loop_results.json`.
Cubre §23 completo: never-seen, 1 fallo, repetido, reciente-fallo/exito,
mastered reciente/antiguo, bypass crítico, targeting fórmula/concepto,
padre/hoja, duplicados+backfill, empate, seed, progresión (4/4 → +1 nivel,
nunca EXPERT), rec→Examiner (`q-01982e7de509` VALID reproducido),
correct→next (0.5238→0.697, prioridad 28.667→14.605, DEFER),
wrong→next (`$U=u_c/k$` → FORMULA_ERROR root, 12.0→37.726, ALLOW),
replay F5, idempotencia, LLM=0 (estático+firmas), KB/eval/students.

```
python3 app/adaptive_loop_benchmark.py [--write] [--out P] [--only M,..]
python3 -m pytest tests/adaptive/ -q   # 73 tests (34 Bloque A + 39 Bloque B)
```

Determinismo entre procesos byte-idéntico (detalles sin timestamps;
`--out` comparado en test). Preguntas temporales de submits van a copia
de GENDB: la real jamás se escribe (guardia en el runner + test).

## Deuda (no Bloque B)

Calibración docente de TUNABLEs (`unknown`); REAL_EXAM sin señal
adaptativa; MAINTAIN sube un nivel (revisar con docente); conceptos sin
historial abstienen tema; spacing `last_correct` (límite F5 citado).
Nada de Fase 7.
