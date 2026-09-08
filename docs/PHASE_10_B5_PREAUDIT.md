# PHASE_10_B5_PREAUDIT — Auditoría previa de integración (B5.1, solo lectura)

Fecha: 2026-09-07. Ámbito: `app/application/` (10 ficheros) + fronteras
`app/{exam,examiner,correction,student,adaptive,retrieval,llm}`.
Sin cambios de código durante la auditoría.

## Tabla por workflow

| Workflow | Entrada | Delegaciones | Estado | Persistencia | Salida | Errores |
|---|---|---|---|---|---|---|
| Tutor | `(ctx, query, top_k)` | Retrieval `retrieve_evidence` → Reasoning `answer` | sin estado | ninguna | `{"ok","data"}` proyectada (answer/status/claims/formulas/provenance/versions) | USER/VALIDATION/GENERATION/RETRIEVAL; `RuntimeError`→GENERATION, `KeyError/ValueError`→RETRIEVAL |
| Practice | `(ctx, session, …)` | Examiner `generate` → Correction vía Student `submit` → Student `get_mastery` | `ApplicationSession` efímera (`active_reference` pregunta) | vía F5 (attempt+correction+mastery) | vista STEM + resultado + mastery proyectados | VALIDATION/NOT_FOUND(`_own`)/STATE/GENERATION/CORRECTION/PERSISTENCE |
| Adaptive | `(ctx, session, item/units…)` | AdaptiveLoop `recommend`+`selector.to_spec` → Examiner `generate` → Student `submit/get_mastery` | efímera | vía F5 | recomendaciones proyectadas, pregunta, resultado, mastery | VALIDATION/NOT_FOUND/STATE/GENERATION |
| Exam | `(ctx, session, exam_session_id…)` | `ExamSessionService` + `ExamGradingService` 1:1 | efímera + máquina F7 | vía F7 (+F5 en grading) | envolventes `exam_session/prepared/started/question/saved/submitted/result/review` | vía `guard()`: ExamError→NOT_FOUND/STATE/…; resto propaga |
| Review | `(ctx, session, exam_session_id…)` | `ExamGradingService` + `ExamReviewService` (solo lecturas) | efímera | ninguna | dicts crudos del servicio (result/review/question/mastery_view) | vía `guard()`; pre-GRADED→STATE |

## Verificaciones negativas (todas PASS por inspección + evidencia B4)

- Lógica duplicada: **no**. Sin retrieval/cálculo/grading/corrección/
  mastery/scoring/generación/máquina/policy/validación propios.
- Acceso directo a DB: **no**. `sqlite3` solo aparece en ramas
  `except` para mapear a `PERSISTENCE_ERROR` (`errors.guard`,
  `practice:95`, `adaptive:103`); el resto propaga (`raise` pelado).
- Estado de dominio en aplicación: **no**. `ApplicationSession` efímera,
  sin tabla; lo durable vive en F5/F7.
- `except Exception` como flujo: **no**. 5 sitios, todos traducen a
  código `AppError` conocido o re-lanzan (fail-loud). `guard()` mapea
  `ExamError` por marcadores ordenados, resto intacto.
- Resultado ambiguo: **no**. Éxito `{"ok": True, "data"}`; parcial en
  `result.status` (CORRECT/PARTIAL/…); abstención en `abstain` (+
  `USER_ERROR` en vacío); error siempre `AppError` con código cerrado.
- Pérdida de provenance: **no**. Tutor conserva evidence/provenance/
  versions; practice/adaptive exponen `log` + question_id/version;
  exam/review arrastran fingerprints/scoring/policy (B4 V01–V03).
- Pérdida de idempotencia: **no**. `attempt_id` explícito, replays F5,
  grading/review puros (B4 I01–I03).
- IDOR/enumeración: **no**. `_own()` en toda op con recurso
  (practice/adaptive/exam/review); cross-student → `NOT_FOUND`
  uniforme (B4 S01–S03; el vocabulario no tiene `FORBIDDEN`: el
  contrato existente exige anti-enumeración vía `NOT_FOUND`).
- Dependencia circular: **no**. Dominio nunca importa `app.application`;
  application solo importa modelos/lecturas (`stem_view`,
  `LearningPathItem`, `ExamError` para mapeo).

## Hallazgos

- P0: **0**. P1: **0**.
- P2 (conocidos, no bloqueantes, NO tocar en B5):
  - P2-1: `FORMULA`/`MULTIPLE_CHOICE` sin `formula_ids` cae en
    `_gen_theory_template` manteniendo `type=FORMULA`
    (`app/examiner/service.py:66-78`). Regla especial B5: no corregir.
  - P2-2: la suite abre `data/generated/questions.sqlite` en RW
    (toca cabecera/mtime); contenido verificado idéntico
    (`sha256 2547a6f8…`) y restaurado en B4. Higiene preexistente.
- P3: **0**.

## Contratos correctos (sin cambios)

B5.2 (convención unificada), B5.3 (scope/ownership), B5.4–B5.8
(delegación por workflow), B5.10 (frontera de errores) — todos
verificados por inspección + suite B4 (132 tests) + benchmark B4
(54/54 x2). No se requiere cambio de código en `app/application/`
ni en dominios.

## Cambios mínimos necesarios (solo artefactos B5 nuevos)

1. `app/application_b5_benchmark.py` + `data/evaluation/
   phase_10_b5_benchmark.jsonl` (≥76 casos; reutiliza el motor del
   runner B4 por importación + pasos `subprocess` para recovery).
2. `tests/application/test_{recovery,idempotency,determinism}.py`
   (la matriz B5.16 restante ya existe con otros nombres; se
   documenta el mapeo, sin duplicar ficheros).
3. Docs B5 + D148+.

## Conclusión preaudit

Vía libre para B5.15–B5.20 sin tocar código certificado.
