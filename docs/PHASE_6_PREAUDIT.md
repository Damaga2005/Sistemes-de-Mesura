# PHASE_6_PREAUDIT — Auditoría previa del Adaptive Learning Engine

> Solo lectura. Ningún código, KB, `eval.sqlite` ni documento modificado.
> Alcance verificado por inspección directa de `app/student`, `app/correction`,
> `app/examiner`, `app/reasoning`, `app/retrieval` y las tres SQLite.

## 1. Estado de la arquitectura

El ciclo requerido existe casi completo con piezas deterministas:

```text
StudentAttempt → CorrectionService.correct() → Correction (score, errores, claims)
        ↓
StudentService.submit() [transacción atómica]
        ↓
MasteryEvent (inmutable) → MasteryState (derivado) → get_weak_units()
        ↓
[FALTA] PriorityCalculator / LearningPathSelector / DifficultySelector
        ↓
[EXISTE] ExaminerEngine.generate(topic/section/type/difficulty/formula/seed)
        ↓
submit() … (ciclo cerrado, probado en tests/student)
```

**Veredicto por tramo**: performance→errores→mastery→weak-units → **AVAILABLE**;
weak-units→pregunta dirigida → **AVAILABLE** (vía `ExaminerEngine.generate`
con filtros); dificultad siguiente y repetición espaciada → **PARTIAL**
(sin política documentada); contenido ya dominado excluible → **AVAILABLE**
(`MASTERED` + `get_weak_units` ordenado).

## 2. Componentes reutilizables (sin cambios)

- `StudentService.submit/get_mastery/get_topic_mastery/get_formula_mastery/`
  `get_error_profile/get_recent_attempts/get_memory/get_weak_units`
- `CorrectionService.correct()` + `FormulaValidator` + `safe_eval` + rúbricas
- `ExaminerEngine.generate()` + `assemble_exam()` + `QuestionStore`
- `MasteryEvent` replay, `mastery-policy-v1`, `detect_override`

## 3. Campos disponibles (verificados en código y SQLite)

| Campo | Ubicación | Estado |
|---|---|---|
| topic / section / concept / formula | `MasteryState.knowledge_unit_id` (`topic:`/`section:`/`concept:`/`formula:`), `questions.formula_ids`, `body_json.concept_terms` | AVAILABLE |
| skill | `unit_kind` admite `"skill"` | PARTIAL (ningún escritor lo emite) |
| error_type / severity / root/derived | `corrections.body_json.detected_errors[]` | AVAILABLE |
| attempt/success/failure counts | `MasteryState.*_count` | AVAILABLE |
| mastery / confidence | `MasteryState.score/confidence` (+ política aparte) | AVAILABLE |
| last_seen / last_correct | `MasteryState.last_attempt/last_correct` | AVAILABLE |
| difficulty por intento | vía join `attempts.question_id → questions.difficulty` | PARTIAL (no desnormalizado) |
| provenance | `MasteryEvent` + `memories.attempt_ids/correction_ids` | AVAILABLE |
| `question_version` por intento | `attempts.question_version` | AVAILABLE |

## 4. Campos faltantes

1. **`origin` en preguntas** (MISSING): nada distingue `GENERATED` de una
   futura `REAL_EXAM`/`IMPORTED`/`MANUAL`. Añadir columna + valor por defecto
   `GENERATED` antes de importar exámenes reales.
2. **Skill graph** (MISSING): sin dependencias concepto→fórmula en KB; el
   rollup actual por co-ocurrencia basta para v1, no para prerrequisitos.
3. **Política de dificultad/spacing** (MISSING): no hay `difficulty_policy`
   ni `spacing_policy` versionadas (análogas a `mastery-policy-v1`).
4. **skill units emitidas** (PARTIAL): el tipo existe, ningún productor.

## 5. `get_weak_units`: auditoría específica (§3)

1. Devuelve `[{knowledge_unit_id, unit_kind, score, confidence,
   attempt_count, status}]`, ordenado por `(score, -attempt_count)`, con
   `limit` y filtro opcional `kind`. 2. Fuente: solo `mastery_states`
   (rendimiento real agregado, cero LLM). 3. **Determinista**: orden total
   salvo empate exacto en `(score, attempt_count)` (mismo orden rowid del
   fichero; documentar `ORDER BY` secundario en Fase 6). 4. Distingue
   topic/section/concept/formula; `skill` solo cuando exista. 5. Ordena por
   debilidad de forma monótona y reproducible. 6. **Apta como entrada del
   motor**: es exactamente la señal que `PriorityCalculator` necesita.
   No modificarla; envolverla.

## 6. Riesgos

- **R1. Oscilación por muestra pequeña**: 1–2 intentos generan prioridades
  ruidosas → exigir `confidence` mínima y `attempt_count` en el selector.
- **R2. Empates no ordenados** (§5.3): añadir desempate explícito.
- **R3. LLM en corrección abierta** (`llm_assist`): acotado a confirm/REVIEW,
  pero introduce varianza en mastery si se usa como entrada. **Regla Fase 6**:
  el loop adaptativo usará corrección determinista (`llm_assist=False`);
  el assist queda para feedback.
- **R4. Contaminación invertida**: el selector lee `questions`+`student`;
  prohibir escritura en ambas desde adaptación (solo `student.sqlite` recibe
  eventos, como hoy).
- **R5. Dificultad sin grade inflation**: `MASTERED` exige ≥4 intentos y ≥3
  correctos; no relajarlo para "motivar".
- **R6. Confusión `EVALUATION ↔ KNOWLEDGE`**: los exámenes reales futuros
  deben entrar como `questions(origin=REAL_EXAM)` + estadísticas aparte,
  jamás a `knowledge.sqlite`.

## 7. Dependencias (orden de construcción Fase 6)

`PriorityCalculator` (sobre `get_weak_units` + `error_profile`) →
`DifficultySelector` (nueva policy versionada) → `LearningPathSelector`
(reutiliza `ExaminerEngine.generate` + `assemble_exam`) →
`RecommendationBuilder` (estructura + provenance) → tests → docs.

## 8. Protección del gate 2896/2896

- Cobertura blindada por `test_20_formula_regression_gate` + benchmark
  comprometido + `test_formula_table_integrity` (2858 látex).
- El selector adaptativo solo leerá `formula_id` canónicos y los pasará
  opacos a `ExaminerEngine`/`FormulaValidator`; ninguna ruta los reescribe
  (verificado: `expression` solo se lee en `store/verify/service`).
- Regla de revisión Fase 6: cualquier PR que toque `app/retrieval`,
  `formula_check.py` o el gold debe re-ejecutar el gate; `Missed: 0` o NO-GO.
- Memoria del estudiante jamás alimenta fórmulas (test de aislamiento exige
  `eval.sqlite` ausente del servicio; extender a `student.sqlite` → KB).

## 9. Compatibilidad con exámenes reales

Añadir `questions.origin` (`GENERATED` por defecto) + `exams.kind`
(`GENERATED`/`REAL_EXAM`) antes de importar nada. Un examen real aporta
`attempts`/`corrections` (evidencia estadística del patrón de evaluación)
sin tocar `knowledge.sqlite`, `chunks.jsonl` ni el benchmark de fórmulas.
Las preguntas `REAL_EXAM` reutilizan `CorrectionService` + rúbricas con
`rubric_version` propia si difieren los criterios.

## 10. Tabla de información faltante (§9)

| Requisito | Estado | Evidencia | Falta |
|---|---|---|---|
| Student mastery | AVAILABLE | `MasteryState` + policy v1 | nada |
| Weak units | AVAILABLE | `get_weak_units` + tests | desempate explícito |
| Error history | AVAILABLE | `mastery_events.evidence_json` + `error_counts` | nada |
| Formula mastery | AVAILABLE | `formula:<id>` + `get_formula_mastery` | nada |
| Concept mastery | AVAILABLE | `concept:<term>` (donde el examen los emite) | más emisores |
| Difficulty history | PARTIAL | join attempts→questions | desnormalizar o vista |
| Question linkage | AVAILABLE | `formula_ids/concept_terms/section/topic/difficulty` | `origin` |
| Recommendation input | AVAILABLE | débil ordenado + perfil + memoria con IDs | policy de prioridad |
| Determinism | AVAILABLE | seeds + hashes + tests triple/idempotencia | auditar empates (§5.3) |
| Provenance | AVAILABLE | eventos, memorias, `audit_log`, versiones | nada |

## Recomendación

```text
GO
```

Con condiciones: (a) no tocar retrieval/KB/golds salvo gate verde;
(b) `origin` + policies versionadas antes que el selector;
(c) loop adaptativo sobre corrección determinista; (d) tests de
no-regresión F0–F5 en cada cambio. Ninguna condición exige rediseño:
la arquitectura actual soporta Fase 6 por composición.

---

## Anexo PASO 2 — Cierre de gaps (implementado, sin motor adaptativo)

1. **GAP 1/1B — origin/kind**: `Question.origin` (`GENERATED` por defecto;
   `REAL_EXAM|IMPORTED|MANUAL` validados) y `exams.kind/source`
   (`GENERATED` por defecto) vía migración idempotente; fingerprint sin
   `origin` (identidad de contenido, sin reinserciones); provenance intacta.
2. **GAP 2 — políticas**: `Policy` frozen (`policy_id/version/parameters`,
   `dumps()` determinista con `sort_keys`); registro con
   `mastery-policy-v1` (activa, parámetros = constantes reales),
   `difficulty-policy-v1` y `spacing-policy-v1` (`reserved`, sin algoritmo);
   eventos históricos conservan su versión.
3. **GAP 3 — desempate**: `(score, -attempt_count, knowledge_unit_id)`;
   empate exacto verificado idéntico entre dos ejecuciones independientes.
4. **GAP 4 — skill (opción B)**: ningún productor lo emite (verificado en
   store tras submits multiformato); contrato efectivo =
   topic/section/concept/formula; `Skill graph|mastery|prerequisites → FUTURO`.
5. **Corrección determinista**: el loop usará `llm_assist=False` (defecto ya
   vigente); test con provider que lanza excepción lo demuestra.
6. **Gate intacto**: retrieval/ranking/formula sin cambios; regresión y
   aislamiento abajo.
