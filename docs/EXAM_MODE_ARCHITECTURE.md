# EXAM_MODE_ARCHITECTURE — Diseño Fase 7 (sin implementar)

Especificación verificable futura. Todo lo citado como existente está
probado en `docs/PHASE_7_PREAUDIT.md`. Nada aquí crea código, UI, timer
real, DBs ni preguntas.

## 1. Separación de capas (§2)

Cinco stores físicos, cinco escritores únicos:

```text
knowledge.sqlite   ← ingesta            (Fase 7: solo lectura)
questions.sqlite   ← ExaminerEngine     (Fase 7: lectura + generate previo)
sessions.sqlite    ← Exam Mode  (NUEVA, data/exams/)   (D85)
student.sqlite     ← StudentService     (Fase 7: vía submit, post-submit)
eval.sqlite        ← nadie en runtime   (ciega; tests la vigilan)
```

El examen consume de todas salvo eval; conocimiento nuevo: prohibido.

## 2. ExamBlueprint (spec, no preguntas)

```text
{exam_id?, title, version, seed, duration_seconds|null,
 question_count, topics[], sections?{topic:[prefix]}, types{type:count},
 difficulty{level:proporción Σ=1}, required_formula_ids[],
 concept_requirements[{term, types}], scoring{points_by_position?,
 default_points=1.0, required_default=true}, ordering_policy
 ("seeded_shuffle"|"blueprint_order"), policy_refs{exam_spec, scoring}}
```

Validación (`EXAM NOT READY` si falla): cuenta>0; topics no vacío;
tipos/dificultades en vocabularios; dificultad Σ≈1 (±0.02, patrón
`_proportions`); `duration` null o ≥1 (0 inválido); todo
`required_formula_ids` existe en KB (`FormulaValidator`, P0 §13);
conceptos solo exigibles en tipos que pueblan `concept_terms` (D82);
pool VALID suficiente o shortfall declarado (patrón `assemble_exam`).

## 3. Tipos y orígenes (§5–§6)

`PRACTICE_EXAM` (sin límite si `duration=null`, revisión inmediata),
`MOCK_EXAM` (estricto, revisión post-submit), `REAL_EXAM` (provenance
categoría: fecha/origen/fuente/documento/pregunta original/versión;
**nunca modifica KB**), `IMPORTED_EXAM` (solo VALID + provenance
completa; sin importador en v1). Orígenes reutilizados sin duplicar:
`GENERATED/REAL_EXAM/IMPORTED/MANUAL`. `REAL_EXAM` alimenta evidencia
mastery por la vía normal pero **cero señal adaptativa** (no existe tal
señal; D84). Adaptive OFF durante la sesión (§12): el Builder/Loop no se
invoca; el estado F6 solo se toca vía F5 tras submit (§25).

## 4. Sesión y estados (§7, §34)

```text
ExamSession{session_id, exam_id, exam_kind, student_id, seed,
 started_at:null, submitted_at:null, duration_seconds,
 status, exam_version, policy_versions{...}, frozen_spec_hash}
```

```text
CREATED → READY → IN_PROGRESS → SUBMITTED → GRADED
                ↘ CANCELLED (desde CREATED/READY/IN_PROGRESS)
IN_PROGRESS → EXPIRED (restante 0) → SUBMITTED (auto) → GRADED
```

`PAUSED` fuera de v1 (`PAUSE = no soportado en v1`, §21). Transiciones
únicas, guardadas por estado actual; cualquier otra → error, nunca
silencio.

## 5. Snapshot e instancias (§8–§9, D78)

Las preguntas son content-addressed (`put()` nunca sobrescribe): el
snapshot es **por referencia**. Al pasar a `READY` se congela y verifica:

```text
ExamQuestionInstance{session_id, position, question_id, question_version,
 fingerprint, points, required, blueprint_slot, seed}
```

re-resolviendo cada id y exigiendo fingerprint idéntico; mismatch →
`EXAM NOT READY`. Cuerpo, policies, KB y mastery pueden evolucionar
después sin afectar a la sesión. Orden reproducible: misma tupla
(blueprint, versiones, seed, pool) → mismas preguntas y posiciones;
`seed` distinto → otra selección válida; jamás rowid/filesystem/sets/
azar/tiempo (`rng = random.Random(seed)` sobre lista explícita, patrón
heredado; dedupe por fingerprint también en el pase primario).

## 6. Selección (§11, §10, §14)

Extender `assemble_exam` (no duplicarlo): +filtro `sections` (prefijo
sobre `section`), +`required_formula_ids` (cobertura `formula_ids` +
existencia KB previa), +`concept_requirements` (cobertura
`concept_terms` donde el tipo lo soporta), +exclusión de duplicados por
fingerprint, +`ordering_policy`. Nunca fuera de tipos/cuotas: shortfall
antes que evidencia ajena al blueprint.

## 7. Scoring (§15, §17)

Por pregunta: `Correction` existente (0..10, `aggregate()`). Examen:

```text
final_10 = half_up_2( Σ (score_i/10 × points_i) / Σ points_required × 10 )
```

cómputo en milésimas enteras (sin flotantes). `BLANK` = respuesta vacía
→ `NO_ANSWER` existente → 0 sin LLM. `NEEDS_REVIEW`/`UNGRADABLE` → nota
`PENDING_REVIEW` + provisional con esas a 0 marcadas, jamás 0 silencioso
(D83); `regrade` F5 cierra el ciclo. Sin LLM en la nota. `scoring-policy-v1`
versionada y snapshotada en la sesión.

## 8. Respuestas y submit (§18–§22)

`save_answer` = upsert solo en `IN_PROGRESS` (+ `answer_log` append-only
para disputas); tras `SUBMITTED`, congeladas. `submit(session_id)`:
idempotente (segundo submit devuelve el grade almacenado), irreversible
salvo revisión explícita; no duplica correcciones/eventos/score/mastery
(hereda garantías de `attempt_id` determinista).

## 9. Timer (§20)

Contrato sin UI: `duration_seconds` del spec congelado; `started_at` =
reloj servidor al entrar en `IN_PROGRESS`; cada `save_answer`/`submit`
comprueba `now ≥ started_at+duration` → `EXPIRED` + congelación
determinista. `duration=null` = sin límite; `=0` en blueprint = inválido.

## 10. Corrección y mastery (§16, §23–§24)

`Exam Answer → CorrectionService.correct → Correction` (mismo corrector,
con `rubric_snapshot`). `ExamResult ≠ StudentMastery`: el examen produce
evidencia; mastery se alimenta **post-submit** vía `submit(..., exam_id)`
existente. Provenance respondible por joins
`attempts.exam_id → corrections/mastery_events/memories(attempt_ids)` +
aditivo `Correction.exam_id/session_id` (D81, default `""` compatible).

## 11. Calidad, versiones, determinismo (§28–§31)

Gate `READY`: cuenta, cobertura topics, distribución dificultad,
fórmulas/conceptos válidos, dedupe, todo VALID, provenance completa,
scoring válido, reproducibilidad seed. Versiones por sesión:
`{examiner, knowledge(fase1-1.0), retrieval, reasoning, scoring,
exam_spec}`. Reproducibilidad = misma tupla → mismo examen; misma
sesión + respuestas + policies → misma nota.

## 12. Seguridad y anti-fuga (§32–§33)

`STEM_VIEW` (prompt/opciones/variables/dificultad/posición, sin
solution/correct/claims/evidence-solucionadora) durante `IN_PROGRESS`;
`REVIEW_VIEW` completa solo post-submit según política. Controles:
snapshot+fingerprint, respuestas por estado, nota derivada inmutable,
spec congelado (mutación invalida), provenance append-only, soluciones
jamás en vistas de examen.

## 13. APIs (diseño, §35)

Nuevas finas sobre lo existente: `create_exam(blueprint)→spec`,
`validate_exam→veredicto`, `prepare_session→CREATED`, `start_session→
IN_PROGRESS(+started_at)`, `get_question→STEM_VIEW`, `save_answer`,
`submit→SUBMITTED`, `grade→GRADED/PENDING_REVIEW`, `get_result→vistas
según estado`. Generar/corerregir/seleccionar reutilizan F4/F5/`exam.py`.

## 14. Tests, benchmark, métricas (§36–§39)

Estrategia §36 completa (añadir: vistas por rol, mutación de spec,
`PAUSED` rechazado). Benchmark futuro `exam_mode_benchmark.jsonl` con
los 24 ítems §38 (sin crear hasta implementar). Métricas §39 como
definiciones: tasas sobre intentos/entregas + `reproducibility` (igualdad
byte a byte a igual tupla), `*_leak_rate = 0` exigido,
`isolation_integrity` por hashes. Gate global 2896/2896 en cada fase (§37).
