# PHASE_7_REVIEW_PREAUDIT — Review/Results/Completion (solo lectura y diseño)

Preauditoría F7-B4 verificada contra código el 2026-09-05. Cero código,
cero tablas, cero DB writes, cero commits. Todo `file:line` existe.

## 1. Alcance

Determinar qué ve el estudiante, cuándo, con qué feedback y qué queda
oculto, sobre `GRADED → RESULT → REVIEW → MASTERY`. Sin implementar.

## 2. Archivos inspeccionados

`app/exam/{models,service,grading,store}.py`, `app/correction/{models,
service,errors,analyzer,scoring}.py`, `app/student/{models,mastery,
memory,service}.py`, `app/adaptive/{models,path,recommendations,
spacing}.py`, `app/examiner/{models,service,store}.py`,
`app/retrieval/models.py`, `app/llm/interface.py`, esquemas
`app/{store,student/store,exam/store}.py`, docs F4–F6 y B1–B3.

## 3. Evidencia file:line (contratos que NO se infieren)

- `Correction` + `CORRECTNESS` 6 estados: `correction/models.py:9,73`.
- 16 `ERROR_TYPES` + `SEVERITY` 4 niveles: `correction/models.py:11,16`.
- `SEVERITY_TABLE` (MAJOR máx. por defecto; CRITICAL sin asignación) +
  `PROPAGATION`: `correction/errors.py:12,33`.
- `CriterionResult.detail` ≤200 (`service.py:427`); `feedback` determinista
  + `_FIX_HINTS` + `feedback-5.0`: `correction/service.py:445,459`.
- LLM solo confirma/pide review, raw NUNCA persiste, provider NO se
  registra: `correction/service.py:368,391,404,415`.
- Fugas internas reales: `formula_results[].detail` = equation_id
  (`service.py:224,247`); `calc_entry{expected,claimed,expression}`
  (`service.py:269`); detalles `"difiere: got vs expected"`
  (`service.py:278,291`). Todo INTERNAL, jamás en vistas.
- `stem_view()` whitelist 12 campos: `exam/models.py:253,260`.
- `get_result/get_question_result` (puerta `RESULT_NOT_AVAILABLE`,
  sin secretos por construcción): `exam/grading.py`.
- Memories deterministas PERFORMANCE con ids (hasta 50):
  `student/memory.py:22,49`.
- Retrieval scores internos (`final_score`, `confidence`, packs):
  `retrieval/models.py:29,51,61`.
- `NO_ANSWER`→sin señal, vacíos nunca tocan LLM:
  `correction/service.py:100,114`; `student/service.py:125`.
- Mastery replay con límites (`last_correct=""`, `error_counts={}`):
  `student/mastery.py:78,102`.

## 4. Arquitectura existente (mapa de capas §3)

| Capa | Owner | Storage | Mutabilidad | Versión |
|---|---|---|---|---|
| KNOWLEDGE | ingesta | knowledge.sqlite | inmutable | fase1-1.0 |
| QUESTION | ExaminerEngine | questions.sqlite | content-addressed | examiner-4.0 |
| SESSION | exam service | student.sqlite exam_* | máquina estados | exam-spec-v1 |
| ANSWER | exam service | session_answers+log | hasta SUBMITTED | — |
| CORRECTION | F5 | corrections(body) | inmutable + regrade | grader/rubric-5.0 |
| RESULT | grading | exam_results | inmutable | exam-spec-v1 |
| REVIEW | — | derivada, sin store | N/A (diseño) | review-policy-v1 (futura) |
| MASTERY | F5/F6 | mastery_* | event-sourced | mastery-policy-v1 |

## 5. Reutilización (sin duplicar)

Rubric+aggregate, taxonomía+PROPAGATION, feedback-5.0+HINTS (base de
`StudentFeedback`), memories con provenance, `get_result` (counts),
snapshot/fingerprint, `attempt/correction` ids, policies registry,
`random.Random(seed)` para orden.

## 6. Gaps (clasificados)

- P0: vistas REVIEW/MASTERY inexistentes; `provider` del assist no
  registrado; `Correction` sin campo `origin` (derivación por
  `attex-`+body documentada, sin tocar F5).
- P1: `review-policy-v1` inexistente (diseño); `Solution` sin contrato
  uniforme por tipo; `NEEDS_REVIEW` sin flujo de cierre; multilingüe sin
  diccionarios; `GRADING_INCOMPLETE` solo como error con reintento.
- P2: `ExamHistory` conceptual; `REVIEW_VIEW` post-`INCOMPLETE`;
  caché de review (innecesaria: todo derivable, D+).

## 7. Incompatibilidades

Ninguna bloqueante. §5 lista `prompt` en denegados: se resuelve como
DENY pre-`IN_PROGRESS` + ALLOW vía `get_question` (D103). `MAINTAIN`/
`REVIEW` nunca filtran vistas (son de práctica, no de examen).

## 8. Data-leak matrix (STATE × VIEW)

| Estado | STEM | RESULT | REVIEW | MASTERY* |
|---|---|---|---|---|
| CREATED | DENY | DENY | DENY | DENY |
| READY | DENY | DENY | DENY | DENY |
| IN_PROGRESS | ALLOW | DENY | DENY | DENY |
| SUBMITTED | DENY | CONDITIONAL† | DENY | DENY |
| EXPIRED | DENY | DENY | DENY | DENY |
| GRADED | DENY | ALLOW | ALLOW‡ | ALLOW |
| CANCELLED | DENY | DENY | DENY | DENY |

*resumen pedagógico propio, no estado crudo. †Solo si existe fila de
resultado (`INCOMPLETE` incluido, con banner). ‡Solo `COMPLETE`;
`INCOMPLETE`→`REVIEW_NOT_AVAILABLE` (lo correcto se desconoce).

## 9. Threat model (riesgo/control/test/estado)

T1 IDOR (medio/ownership en cada API+tests aislamiento/OK-diseño); T2
resultado pre-submit (alto/puerta `RESULT_NOT_AVAILABLE`/G21/OK); T3
solución (alto/whitelist+ausencia en result/T15+G22/OK); T4 answer-key
(alto/opciones solo-texto+G16+G22/OK); T5 rúbrica (medio/DENY en
vistas+G15/OK); T6 prompt (medio/DENY pre-start+D103/OK); T7 reasoning
interno (alto/no persiste + whitelist/test/OK); T8/T9 cross-student/
session (alto/`student_id`+`session_id` en cada acceso/G20+L24/OK); T10
resultado rancio (medio/inmutabilidad+graded_at/test/OK); T11 mutación
histórica (alto/sin UPDATE en result+test/OK); T12 KB (alto/solo-lectura
+hashes/OK); T13 mastery (alto/review sin writes+test futuro/OK-diseño);
T14 LLM fabula (alto/determinista-primero+abstención/OK-diseño); T15/T16
source/fórmula mismatch (medio/KB-canónica+gate/OK); T17/T18
expired/cancelled (bajo/matriz §8+tests/OK).

## 10. Controles de seguridad

Ownership doble en cada acceso; vistas por whitelist (nunca blacklist);
resultado inmutable (sin UPDATE); review derivada sin store; mastery
solo-lectura; hashes KB/eval; `attex-` trazable; sin secretos en
detalles (auditoría §12).

## 11. Review policy propuesta (`review-policy-v1`, futura, versionada)

Flags: `reveal_correct_answer` (def true; REAL_EXAM false),
`reveal_solution` (true), `reveal_formula` (true, solo canónica),
`reveal_source` (true, sin hashes), `reveal_errors` (true, raíz+
consecuencias), `reveal_score` (true), `reveal_rubric` (false),
`feedback_lang` (ca|es), `llm_explainer` (off). Nada se reinterpreta
sin bump de versión + `graded_at` intacto.

## 12. Result policy propuesta

`get_result` actual ya es RESULT_VIEW (counts, sin secretos). Sin
cambios: documentar como contrato (D+). `INCOMPLETE` con banner, nunca
0 silencioso.

## 13. Mastery boundaries

Leer ≠ escribir (test futuro: review sin `INSERT` en mastery_*).
Resumen pedagógico `{topic, banda, motivo}` desde `score/status`+
`error_profile`+reasons F6; jamás `attempt_ids` crudos ni `confidence`
interna. Origen EXAM derivado (`attex-` + body con `session_id`), sin
campo nuevo (D+). Contaminación imposible por construcción (cero writes).

## 14. Formula review

Enlace `formula_id → {latex, topic, section_h2, variables, units,
source, source_hash}` solo lectura KB; mostrar según flags (latex y
fuente sí; hash solo interno). `formula_review_resolution` por pregunta:
resuelto si `formula_id` existe en KB (siempre, por gate de
preparación). Cobertura global 2896 intacta: el review no genera,
reordena ni reescribe fórmulas (P0 §68 verificado en diseño).

## 15. API design (contratos §45)

`get_result/get_question_result` (existen, documentar). Futuras:
`get_review(session, student)` (GRADED+COMPLETE, vista REVIEW),
`get_review_question(session, position, student)`,
`get_exam_history(student)` (specs+status+provenance, sin contenido),
`get_mastery_summary(student[, session])` (pedagógico). Todas con
auth doble, estados §8, sin campos §44-denegados, idempotentes (lecturas),
errores §46 (`RESULT_NOT_AVAILABLE`/`REVIEW_NOT_AVAILABLE` existen como
patrón; resto nuevos con owners).

## 16. Tests (plan: ~40)

Acceso 7 (matriz §8) + seguridad 9 (T1–T9) + corrección 8 (tipos F5
reales) + fórmula 4 + mastery 2 (no-write + provenance) + versionado 2
+ determinismo 2 + multilingüe 2 + IDOR 4 ≈ 40. Sin mocks de F5.

## 17. Benchmark (30+ §56 + 4 de auditoría)

31. multistep-formula link, 32. `INCOMPLETE` sin review, 33. REAL_EXAM
compatible (provenance sin importer), 34. `attex-` origin derivation.

## 18. Métricas (§57)

17 definidas; P0 con umbrales del brief (`*_leak_rate=0`,
`mastery_write_rate_from_review=0`, `formula_review_coverage=100%`).

## 19. Riesgos residuales

Deriva LLM futura (contenida por §22); `provider` no registrado (P0
gap con control: `source` por criterio + abstención); `NEEDS_REVIEW`
sin cierre (P1); `review-policy-v1` inexistente (P1, diseño listo).

## 20. GO/NO-GO

**GO**: los 10 P0 tienen control diseñado y verificable contra código
existente; ningún gap es arquitectónico; el gate de fórmulas no se toca.
