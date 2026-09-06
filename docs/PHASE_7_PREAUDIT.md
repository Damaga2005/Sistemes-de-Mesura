# PHASE_7_PREAUDIT — Qué existe antes de Exam Mode (solo lectura)

Verificado contra código el 2026-09-05. Nada modificado, nada generado.
Regla del bloque respetada: cero cambios funcionales, cero preguntas nuevas,
cero escrituras en KB/eval/student/GENDB, cero commits.

## 1. Estado heredado (GO F0–F6)

KB 2896 fórmulas (`pipeline_version fase1-1.0`); retrieval TF-IDF+RRF local;
reasoning Gemini+extractivo; Examiner determinista 38/38; correction
`grader-5.0`/`rubric-5.0` con snapshot por corrección; mastery event-sourced
con replay; adaptive sin LLM (priority/difficulty/spacing/recommendation);
gate 2896/2896 re-ejecutado post-F6 (`missed=[]`); hashes KB/eval/chunks/
manifest/GENDB estables y testeados.

## 2. Modelos existentes reutilizables

| Modelo | Dónde | Clave para Fase 7 |
|---|---|---|
| `Question` | `app/examiner/models.py:77` | cuerpo canónico + `question_id=q-`+fingerprint (content-addressed) |
| `QuestionBlueprint` | `app/examiner/models.py:26` | spec por pregunta (topic/section/type/difficulty/formulas/concepts/seed) |
| `fingerprint()` | `app/examiner/models.py:110` | sha256 de contenido; `put()` es no-op si existe (inmutabilidad efectiva) |
| `QUESTION_TYPES/DIFFICULTIES/ORIGINS` | `app/examiner/models.py:10` | vocabularios cerrados, no duplicar |
| `assemble_exam()` | `app/examiner/exam.py:16` | selección seeded del pool VALID, cuotas, shortfall registrado, `exam_id` hash |
| `Correction` | `app/correction/models.py:73` | score 0..10 + `rubric_snapshot` + versiones; `NO_ANSWER` existe (vacío→0 sin LLM) |
| `CORRECTNESS` | `app/correction/models.py:9` | 6 estados incl. `NO_ANSWER/NEEDS_REVIEW/UNGRADABLE` (=BLANK y pendientes resueltos) |
| `aggregate()` | `app/correction/scoring.py:10` | nota reproducible + redondeo a 2 dec |
| `StudentAnswer` | `app/correction/models.py:103` | borrador con `exam_id` (a promover) |
| `MasteryEvent/State` + `replay()` | `app/student/` | evidencia post-examen sin lógica nueva |
| `Recommendation→QuestionBlueprint` | `app/adaptive/exam_adapter.py` | patrón adapter ya probado (reutilizar estilo, no el motor) |
| `LLMProvider` (Protocol) | `app/llm/interface.py:25` | `GeminiProvider` + `ExtractiveProvider`; Examiner default `use_llm=False` |

## 3. APIs públicas existentes

- `ExaminerEngine.generate(topic, section?, type, difficulty?, formula_id?, seed, origin)` → `(Question|None, log)`; rechazar es correcto; persiste en questions DB.
- `assemble_exam(store, topics, count, types?, difficulty?, seed, kb_version, retrieval_version)` → `{exam_id, question_ids, blueprint, versions, coverage{shortfall}}`.
- `QuestionStore.{put, count, put_exam, get_exam}` — **no hay `get_question`**: superficie de fuga por diseñar, no heredada.
- `CorrectionService.correct(qid, answer, student_id?, attempt_id?, exam_id?, llm_assist=False)` → `Correction`; vacías nunca tocan LLM (`service.py:100-116`).
- `StudentService.submit(sid, qid, answer, attempt_id?, exam_id?)` → idempotente por `attempt_id`, escribe attempts(+`exam_id`)/corrections/mastery/memories en una transacción.

## 4. Tablas por capa (separación §2 ya real)

- `knowledge.sqlite`: meta/sources/documents/sections/chunks/formulas/tables_t/visuals/concepts/reconciliation (solo ingesta escribe).
- `questions.sqlite` (GENDB): `questions` (body canónico + columnas cobertura + `origin`) y `exams` (`exam_id/seed/blueprint/question_ids/versions/kind/source`).
- student DB (`data/student/student.sqlite` canónica; `data/processed/students.sqlite` legado — unificar referencia): students/attempts(**con `exam_id`**)/corrections/mastery_states/mastery_events/memories/reviews/audit_log.
- `eval.sqlite`: meta + questions (banco V/F ciego, tests de aislamiento vigentes).

## 5. Policies y versiones (registro a extender, no a duplicar)

`mastery-policy-v1`, `priority/difficulty/spacing-policy-v1` (Policy frozen),
`grader-5.0`/`rubric-5.0` (snapshot por corrección), `examiner-4.0`,
`retrieval-2.0`, `reasoning-3.0`, KB `fase1-1.0`. Faltan (gaps, nuevas):
`exam-spec-v1`, `scoring-policy-v1`. Patrón a reutilizar: clase `Policy`
+ snapshot de parámetros en cada artefacto.

## 6. Gaps confirmados (nada de esto existe)

1. Sesión/timer/pause/expiry: 0 matches en `app/`.
2. Scoring de examen (agregación multi-pregunta, puntos, required/optional, redondeo final): solo existe `aggregate()` por pregunta.
3. Snapshot de sesión e instancias (`ExamQuestionInstance`).
4. `Correction` sin `exam_id`/`session_id` (se acepta en `correct()` pero se pierde; el enlace vive solo en `attempts.exam_id`).
5. `knowledge_version` sin estampar en `Correction` (`""` por defecto).
6. `concept_terms` solo lo pueblan SHORT_ANSWER/plantillas; TF/FORMULA/NUMERICAL llevan `[]` → requisitos de concepto solo exigibles donde hay soporte.
7. Sin vistas anti-fuga (el body completo incluye solution/correct_answer/claims).
8. Sin importador REAL_EXAM/IMPORTED (solo columnas `kind/source` + validación).
9. Sin máquina de estados, sin endpoints de sesión, sin DB de sesiones.

## 7. Riesgos heredados a controlar (todos con control diseñado en arquitectura)

Pregunta mutada post-`READY` (control: snapshot + re-verificación por
fingerprint); respuesta post-submit (upsert solo `IN_PROGRESS`); score
editado (nota derivada, fila de grade inmutable + regrade versionado F5);
duración/seed/policy mutados (spec congelado, mismatch invalida);
soluciones antes de submit (`_question_row` devuelve body completo — uso
interno; vistas STEM/REVIEW lo cierran); provenance manipulada
(append-only + joins existentes).

## 8. Veredicto

**GO**: todo lo que Fase 7 necesita existe o es aditivo sin romper F0–F6
(selección, corrección, scoring por pregunta, idempotencia, provenance por
joins, vocabularios, aislamiento). Sin bloqueos arquitectónicos. Dos toques
F5 documentados como decisiones (D81, D83), ambos aditivos y compatibles.
Gate 2896/2896 en pie.
