# PHASE_10_B6_PREAUDIT — Auditoría adversarial (B6.2–B6.16)

## B6.2 Arquitectura y dependencias (grafo estático)

```text
app/application/ -> app.adaptive (modelos), app.exam (modelos/errores)
app/application/ -> servicios inyectados (retrieval/reasoning/examiner/
  correction/student/adaptive/exam/grading/review) vía ApplicationService
Dominio -> app/application: VACÍO (solo los 2 runners de benchmark,
  herramienta de prueba, no lógica de producto)
Application A -> Application B -> A: no existe (fachadas independientes)
```

`app/application/*.py` no importa `llm/sqlite(persistencia)/pickle/
eval/exec/subprocess/open/TODO`. `sqlite3` solo en ramas `except`
para mapear a `PERSISTENCE_ERROR` (4 sitios, justificados B5.10).
Application PUEDE: contexto, scope, workflow, delegar, normalizar,
estructurar. NO implementa: retrieval, fórmulas, corrección, mastery,
policy adaptativa, generación, máquinas de estado, KB/SQLite directo,
`eval.sqlite`, conocimiento canónico.

## B6.3 Ownership (matriz A→A/A→B/B→A/ausente/tipo)

10 ataques (S01–S10 del benchmark, todos PASS → `NOT_FOUND`):
cross-student exam/practice/adaptive/review, 2 sesiones forjadas exam
+ 2 practice, SQLi neutra, sesión null → VALIDATION, tipo de recurso
equivocado, qid inexistente. Anti-enumeración: mismo código para
inexistente y ajeno. `FORBIDDEN` no existe en el vocabulario (contrato).

## B6.4 Estados

Tutor sin estado; Practice por pregunta (ACTIVE→COMPLETED terminal,
doble `complete` → STATE_ERROR documentado); Adaptive sin estado
propio; Exam = máquina F7 sin duplicar (atrasos/imposibles →
STATE_ERROR F7); Review solo GRADED+COMPLETE; ApplicationSession
ACTIVE→{COMPLETED,ABANDONED} terminal. Restart probado (RC/E).

## B6.5 Idempotencia (con final de DB donde aplica)

IDEMPOTENT: practice correction (replay, 1 fila attempt), exam submit
(early-return + update único), exam grade SECUENCIAL (x3 → 85.00),
review x3 (byte-igual), tutor/adaptive/recommend (puros), exam save
(versiona 1,2,3, gana última), get_question x2.
NON_IDEMPOTENT_BY_DESIGN: exam create (sid derivado de seq: cada
create = nuevo slot, `exs-4e5da…` vs `exs-40eb6…`), practice
`complete` (terminal → STATE_ERROR).
EXCEPCIÓN P0: exam grade CONCURRENTE (ver B6.6).

## B6.6 Recovery / crash consistency → P0 (F7, no F10)

`grade‖grade` misma sesión (2 hilos 4/4, 4 hilos 4/4, CC02 n=4 rojo
en run1+run2): ganador devuelve SUCCESS 85.00 pero el perdedor
ejecuta `_cleanup_partial` sobre datos COMMITTED del ganador.
Final: GRADED + 0 filas + `get_result` muerto + reintento imposible.
Resto de recovery PASS (create/submit/grade-restart secuencial,
practice/adaptive/review/tutor, 2 subprocesos reales).

## B6.7 Provenance

Cadena `source→retrieval→question→session→answer→correction→
mastery→review` verificada (V01–V08 + X09 equivalencia directa).
GENDB canónica: 89 preguntas, origen 100% GENERATED (REAL_EXAM es
`exam_kind` de sesión, no origen; IMPORTED/MANUAL sin filas: sin
mezcla posible). Sin UNKNOWN/MISSING/NULL donde hay contrato.

## B6.8 REAL_EXAM blind (red-team, 2 rutas)

Directa (`ExamReviewService`) y application: `correct_answer/
solution/formula/expected_answer/correct_selection` = None,
`score`+`student_answer` visibles, policy `review-policy-v1` con
`reveal_*` False. Mastery view sin claves. Stem sin leaks (RB06).
MOCK control revela (RB05). 6/6.

## B6.9 IDOR red-team: 10/10 PASS (S01–S10, ver B6.3)

## B6.10 Fórmula

Artefacto `formula_retrieval_results.json` íntegro (hash worktree =
índice `cd2acfed…`, comprometido). Suite: 2896/2896 en verde.
Application no pierde `formula_id` (tutor→`formulas`, practice
FORMULA, adaptive `target_formulas`, review ciega conserva
`formula_id` cuando revela). Sin saltos de `FormulaValidator`.

## B6.11 Determinismo

D01–D06 + run1=run2 (119/119 sin CC02; CC02 rojo en ambas por P0).
Timestamps (`graded_at`, `created_at`) excluidos por contrato.

## B6.12 Aislamiento

7/7 hashes idénticos antes/después (ver B6.md). GENDB en copias tmp;
cabecera tocada por la suite (P2-2 conocido), contenido idéntico y
restaurado. Sin conocimiento canónico nuevo.

## B6.13 LLM boundary

Application nunca llama proveedor raw: solo `reasoning.answer` y
`examiner.generate` (contratos de dominio). Fallo proveedor →
GENERATION_ERROR (T07/EB06). Sin prompts/CoT persistidos (vistas
auditadas: sin `prompt`, sin CoT, sin metadata de proveedor salvo
`{provider,model}` declarado en versions).

## B6.14 Error contract

10 clases provocadas (EB01–EB08 + T05/T07/S08): VALIDATION, NOT_FOUND
(×3 rutas), ABSTAIN estructurado, GENERATION (×2), STATE (×2),
USER, POLICY (R07). `except Exception` en application: 5 sitios,
todos a código conocido o re-lanzan. Nada se convierte en SUCCESS.

## B6.15 Concurrencia (modelo certificado)

PASS: submit mismo attempt [False,True] + mastery; submit distinto
2×CORRECT; recommend =; get_question =; ask aislado =; submit+grade
secuencial. Modelo: share-nothing por hilo (wiring propio) para
lecturas; escrituras F5/F7 secuenciales. P0: grade‖grade misma
sesión (B6.6). Hilo compartiendo conexión → `ProgrammingError`
fail-loud (P2-3 nuevo, documentado: una conexión por hilo).

## B6.16 Equivalencia directa vs application

submit, grade, get_review, generate: igualdad lógica, score,
provenance y persistencia (sonda `equiv6`, 4/4 True). Application
solo añade contexto/scope/normalización/sesión.

## Clasificación de hallazgos

- P0: 1 — grade concurrente corrompe resultado (F7). NO-GO.
- P1: 0. P2: 3 (P2-1 THEORY-fallback, P2-2 cabecera GENDB, P2-3
  conexión-por-hilo). P3: 0.
