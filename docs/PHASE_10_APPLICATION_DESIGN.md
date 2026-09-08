# PHASE_10_APPLICATION_DESIGN — Diseño B2 (DESIGN ONLY, sin implementar)

## B2.1 — Mapa de servicios (verificado en código)

| Workflow | Service → Method | Input → Output | Side effects |
|---|---|---|---|
| Tutor | Retrieval `retrieve_evidence(query, top_k, filters)` → EvidencePack | lectura KB+índice | ninguno |
| Tutor | Reasoning `answer(query, filters, top_k)` → VerifiedAnswer (lang auto) | red si provider LLM | ninguno en DB |
| Practice | Examiner `generate(topic, section, type, difficulty, formula_id, seed, origin)` → `(Question\|None, log)` | escribe questions (dedupe) | — |
| Practice | Correction `correct(qid, answer, student, attempt, exam, session, llm_assist, provider)` → Correction pura | ninguno | — |
| Practice | Student `submit(...)` → attempt+correction+mastery | escribe student DB, idempotente por `attempt_id` | — |
| Adaptive | Priority/Difficulty/Path/Builder `calculate/select/build` | lecturas student/KB | ninguno |
| Adaptive | `AdaptiveLoop.recommend/step` | genera vía engine inyectado | según engine |
| Exam | `ExamSessionService` (11 ops, máquina CREATED→…→GRADED) | escribe tablas exam_* | transacciones unitarias |
| Exam | `ExamGradingService.grade/get_result/get_question_result` | escribe results una vez | idempotente |
| Review | `ExamReviewService.get_review[_question]/get_mastery_view` | lecturas | ninguno |

Persistentes: KB, questions/exams, attempts/corrections/mastery/memories, exam_specs/sessions/questions/answers/results/logs. Efímeros: packs, vistas, feedbacks, recomendaciones, contexto/sesión de aplicación.

## B2.2 — ApplicationContext

```text
{app_session_id, technical_student_id, language: ca|es, workflow,
 active_reference: {kind, id}|null, created_at, policy_versions{...}}
```
Efímero y serializable. Sin answer keys/solutions/rubrics/CoT/prompts/secretos/conocimiento.

## B2.3 — ApplicationSession

```text
{session_id: "apps-"+hash12, student_id, workflow, status:
 ACTIVE|COMPLETED|ABANDONED, language, active_reference,
 created_at, updated_at}
```
Distinta de ExamSession/Attempt/Correction/Mastery. Efímera (sin tabla:
el estado durable ya vive en F5/F7); serializable a dict para el caller.

## B2.4 — Contrato común

Sin clase base (complejidad innecesaria). Convención: cada operación
recibe `(ctx, ...)` primero, devuelve `{"ok": True, "data": ...}` o
lanza `AppError`; sin bucles ocultos (una llamada = transiciones explícitas).

## B2.5–B2.9 — Workflows (delegación exacta)

- **Tutor**: `ask(ctx, query)` → retrieval → reasoning.answer →
  VerifiedAnswer proyectada (answer/status/citas/provenance). Nunca LLM
  directo ni saltos de verificación.
- **Practice**: `start/get_question/submit_answer/get_result/complete` →
  Examiner.generate → Correction.correct → Student.submit. `attempt_id`
  derivado `app-<session>-<n>` para idempotencia.
- **AdaptivePractice**: `recommend/generate/answer/result/next` →
  AdaptiveLoop con servicios inyectados; la app no decide prioridad/
  dificultad/score (solo orquesta llamadas explícitas, sin `while`).
- **Exam**: fachada 1:1 sobre F7 (`create/prepare/start/get_question/
  save_answer/submit/grade/get_result/review`); preserva máquina,
  timer, snapshot, scoring, policies, anti-leak.
- **Review**: fachada sobre `ExamReviewService` (4 lecturas); respeta
  `review-policy-v1` y vistas.

## B2.10 — Matrices

1. **Workflow×Service**: Tutor→retrieval/reasoning; Practice→examiner/
   correction/student; Adaptive→adaptive+examiner+correction+student;
   Exam→exam/grading; Review→review.
2. **Workflow×Side effects**: solo Practice (writes F5), Exam (writes
   F7+F5 vía grading), resto lecturas.
3. **Data×Owner**: KB→ingesta; questions→Examiner; student→StudentService;
   exam_*→ExamSessionService; results→GradingService; vistas→nadie.
4. **State×Workflow**: Tutor sin estado; Practice por question (open/
   answered); Adaptive por recomendación; Exam máquina F7; Review solo
   GRADED(+COMPLETE).
5. **Error×Boundary**: ExamError→AppError(STATE/NOT_FOUND...);
   RuntimeError red→RETRIEVAL/GENERATION; KeyError→NOT_FOUND;
   ValueError→VALIDATION; resto propaga (fail-loud).
6. **Operation×Idempotency**: ask (pura), submits/grades por `attempt_id`
   y filas, reviews/lecturas puras, creates con IDs derivados.
7. **Operation×Provenance**: cada write conserva cadena F5/F7 + `ctx`
   (`app_session_id`) en el retorno, sin duplicar IDs.

## B2.11 — Seguridad

Toda op valida `ctx.student_id` contra el owner del recurso referenciado
(sesión/examen/attempt) ANTES de delegar (defensa en profundidad sobre
los checks F7). Sin secretos en contexto; sin answer keys en tránsito
salvo vistas autorizadas.

## B2.12 — Errores (`app/application/errors.py`)

`AppError(code, message, cause?)`, códigos: USER/VALIDATION/NOT_FOUND/
STATE/KNOWLEDGE/RETRIEVAL/GENERATION/CORRECTION/PERSISTENCE/POLICY/
INTERNAL_ERROR. Mapeo explícito, sin `except Exception` como flujo.

## B2.13 — Red-team de diseño

Vacía→USER_ERROR; unsupported→ABSTAIN heredado; retrieval vacío→ABSTAIN;
provider caído→GENERATION_ERROR explícito; inválida→VALIDATION_ERROR;
blank→NO_ANSWER; doble submit→idempotente; inexistente/ajeno→NOT_FOUND
(sin enumeración); cancelled/expired/incomplete→STATE_ERROR;
grading-incompleto→POLICY/STATE; review-no-disponible→NOT_AVAILABLE;
persistencia→PERSISTENCE_ERROR + rollback; policy ausente→POLICY_ERROR;
malformado→VALIDATION_ERROR; restart→recupera por estado persistido;
repetida→idempotente; concurrentes→serializa SQLite + claves idempotentes.

## B2.14 — Decisiones (D141+ en log)

Estructura `app/application/{__init__,context,session,errors,service,
tutor,practice,adaptive_practice,exam,review}.py` (módulos por workflow,
fachada fina, sin God Object).

## B2.15 — Gate B2

Diseño completo, sin duplicación, ownership y provenance claros,
idempotencia preservada, seguridad y errores definidos, 5 workflows,
P0=0, P1=0, gate fórmulas intacto (sin código tocado). **GO a B3.**
