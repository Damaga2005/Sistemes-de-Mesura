# PHASE_6_PRIORITY_DESIGN — Sistema de prioridades adaptativas (SOLO DISEÑO)

> Nada implementado, nada modificado. Este documento es especificación
> verificable para una implementación futura. Todo dato citado existe hoy
> en el proyecto; donde falta evidencia de calibración se marca TUNABLE.

## 1. Objetivo

Responder, con datos y sin LLM: **¿qué unidad debe practicar el estudiante
ahora?** Salida: ranking explicado de `LearningPriority` + acción cerrada.

## 2. Modelo conceptual

```text
MasteryState + MasteryEvents + corrections/detected_errors
  → per-unit features (need, evidence, error, recency)
  → priority-policy-v1 (pesos y umbrales versionados)
  → LearningPriority[] ordenado (score DESC, unit_id ASC)
  → top-down: hoja elegida + ancestros como contexto (no como picks extra)
```

El LLM queda excluido del cálculo; solo podrá explicar después (§16).

## 3. Inputs (todos existen; lecturas con APIs actuales)

| Origen | Campos usados |
|---|---|
| `mastery_states` | `score, confidence, attempt_count, correct_count, error_counts, last_attempt, status` |
| `mastery_events` | `evidence.signal/root_errors, created_at, policy_version` |
| `corrections.body_json` | `status, detected_errors[{error_type, severity, root_cause, derived_from}]` |
| `questions` | `topic, section, concept_terms, formula_ids, difficulty, question_type, origin` |
| `attempts` | `created_at` (recencia), `question_id` (join a dificultad) |

## 4. Unidades

Solo `topic:T02`, `section:T02:...`, `concept:<term>`, `formula:eq-..`
(formatos reales de `_units_for`). Sin `skill`, sin prerrequisitos.

## 5. Fórmula de prioridad propuesta (`priority-policy-v1`)

Componentes en [0,1], pesos con suma 1 (defecto justificable, TUNABLE):

```text
need    = 1 - mastery
evW     = {LOW:0.3, MODERATE:0.7, HIGH:1.0}[evidence_level]   # §6
err     = min(1, Σ sev_w(root distintos) / 2), sev_w={MAJOR:1.0,MODERATE:0.6,MINOR:0.2}
rec     = bucket(días desde last_attempt): ≤7→0.2, ≤30→0.6, >30→1.0;
          si último signal==0.0 y d≤7 → 0.5 (reintento próximo)
P       = 100 * (0.5*need*evW + 0.3*err + 0.2*rec)   # wM/wE/wR TUNABLE
```

Ejemplo resuelto (único fallo, FORMULA_ERROR MAJOR, d=0):
`P = 100*(0.5*1*0.3 + 0.3*0.5 + 0.2*0.5) = 40.0` → media, evidencia LOW,
nunca máxima: la política no permite que 1 fallo domine (§4).

## 6. Evidence levels (anclados a constantes reales, no inventados)

`n = attempt_count`: `n==0`→UNSEEN (vía exploración, §13); `n<2`→LOW
(bajo el mínimo 2 de DEVELOPING); `2–3`→MODERATE; `≥4`→HIGH (mínimo de
evidencia de MASTERED). Alineado con `CONFIDENCE_N=8` (confianza aparte).

## 7. Error weighting (§5)

Solo raíces (`root_cause=True` de `SEVERITY_TABLE`); derivados excluidos
del cómputo (constan en provenance). Pesos ordinales MAJOR/MODERATE/MINOR
→ 1.0/0.6/0.2 (TUNABLE). `FORMULA_ERROR→WRONG_FINAL_RESULT` prioriza la
fórmula, nunca dos debilidades (§5 ejemplo resuelto en el diseño).

## 8. Recency (§7)

Datos disponibles: `last_attempt`, `created_at` de eventos e intentos.
Estados distinguibles: `never_seen` (n=0), `recently_failed` (último
signal 0.0), `recently_mastered` (transición a MASTERED <30d),
`not_recent`/`recently_seen` por buckets de §5. Sin decay implementado
(la fórmula solo premia lo no visto hace tiempo; el historial no se toca).

## 9. Mastery (§12)

Regla existente intacta: MASTERED exige ≥4 intentos y ≥3 correctos.
Efecto en prioridad: `need≈0` la hunde; MAINTAIN la mantiene visible con
prioridad residual (nunca exclusión permanente).

## 10. Aggregation (§11, anti-doble-conteo)

Prioridad a nivel hoja (formula/concept); padre = **max** de hijas (no
suma). La selección recorre de arriba abajo: se elige la hoja top y sus
ancestros viajan como contexto. `Tema 3 + sección 3.2 + concepto X +
F123` débiles por los mismos intentos = **una** carencia (max), no cuatro.

## 11. Exploration (§13)

`ε` slots reservados (TUNABLE, defecto 1/8): unidades UNSEEN ordenadas por
(topic más débil primero, luego nº de tema = orden curricular, luego
`unit_id`). Sin conocimiento externo. Débiles y mantenimiento nunca
desplazados por exploración más allá de ε.

## 12. Recommended actions (vocabulario cerrado, por reglas)

```text
n==0                              → PRACTICE (explorar)
evidencia LOW                     → PRACTICE (cautela, reasons lo dicen)
mastery<0.4, ev≥MODERATE          → PRACTICE
0.4–0.7 o raíz recurrente         → REINFORCE
0.7–0.9 + HIGH                    → CHALLENGE
MASTERED                          → MAINTAIN
AT_RISK                           → REINFORCE (reason: racha)
```

Umbrales 0.4/0.7/0.9 heredados de `status_for` (no nuevos). Toda la tabla
vive en la política versionada, no en código disperso.

## 13. Policy versioning

`priority-policy-v1`: `{wM:0.5, wE:0.3, wR:0.2, evW:{0.3,0.7,1.0},
sev_w:{1.0,0.6,0.2}, buckets:[7,30], epsilon:0.125, action_table:v1}`.
Congelar al implementar; `priority-policy-v2` para recalibrar. Cada
`LearningPriority` cita `policy_id+version`. Replay: mismos eventos +
misma policy = mismo ranking.

## 14. Determinismo (§15)

Orden total: `(priority DESC, knowledge_unit_id ASC)`; seed solo para el
muestreo de exploración (RNG sembrado, documentado). Empates idénticos →
mismo orden byte a byte. Test: doble ejecución + fixtures empatadas.

## 15. API (propuesta, sin implementar)

```text
PriorityCalculator.calculate(student_id, policy, limit, unit_kind?, seed)
  -> LearningPriority[]  # §8: id/kind/score/mastery/confidence/evidence/
                         # reasons[]/error_signals[]/recency/action/policy
get_priorities(...)  # envoltorio con paginación y filtros
```

`priority` y `difficulty` viajan separadas (§10): la segunda la pondrá
`difficulty-policy-v1` en su momento.

## 16. Benchmark (`adaptive_priority_benchmark.jsonl`, futuro)

15 casos (§19): historial vacío, 1 fallo, fallo repetido, mastery baja/
media/alta, MASTERED, error fórmula/conceptual/derivado, empate exacto,
jerarquía relacionada, nunca visto, reciente, multi-debilidad. Expectativa
determinista bajo defaults v1 (p. ej. caso 2 → P=40.0, LOW, no-top).
Métricas (§20): determinismo (bytes idénticos), consistencia de orden
(Kendall vs rangos esperados), causa-raíz (raíz rankeada sobre derivados),
exclusión MASTERED correcta, completitud de explicación, reproducibilidad
de policy. Nada subjetivo.

## 17. Tests (futuros, §21)

Determinismo, empate, pocas muestras, confianza, mastery, errores,
causa raíz, derivados, MASTERED, recencia, nunca-visto, jerarquía, seed,
versión, provenance, aislamiento (solo student DB), LLM OFF (mismo
resultado con y sin proveedor), KB inmutable, 2896/2896.

## 18. Exámenes reales futuros (§14)

`origin=REAL_EXAM` aportará `exam_frequency/exam_recency/exam_question_type`
como término adicional con peso propio, solo bajo política explícita
(`priority-policy-v2`+). `REAL_EXAM ≠ KNOWLEDGE`: pondera, no enseña.

## 19. Riesgos

R1 pocas-muestras (mitigado §6); R2 empates (§14); R3 LLM fuera del cálculo
(§16 + test LLM OFF); R4 escritura solo en student DB; R5 grade inflation
(umbrales MASTERED intactos); R6 deriva de TUNABLEs (congelar + recalibrar
con revisión docente, nunca auto-tuning silencioso).

## 20. GO/NO-GO para implementación

```text
GO
```

Diseño completo con datos reales, sin bloqueos: toda entrada existe,
toda salida es computable deterministicamente, el gate 2896/2896 no se
toca (el selector solo lee `formula_id` opacos). Único trabajo futuro
real: calibración de TUNABLEs con datos docentes.
