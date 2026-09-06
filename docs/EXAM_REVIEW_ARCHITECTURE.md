# EXAM_REVIEW_ARCHITECTURE — Vistas y contratos (B4 diseño → B5 implementado)

> Trazabilidad B5: `get_result` +`title/exam_version/started_at/
> submitted_at`; `REVIEW/MASTERY` en `app/exam/review.py`;
> `review-policy-v1` en `app/exam/review_policy.py`; prompt+opciones
> texto en cada item de review (propio examen post-`GRADED`); F5 solo
> aditivo (`provider/model/session_id`). Resto del diseño intacto.

## 1. Vistas

- `STEM_VIEW`: existe (`exam/models.py:260`, 12 campos). Solo
  `IN_PROGRESS` vía `get_question`. Prompt SÍ (es la pregunta); todo lo
  demás de §44, NO.
- `RESULT_VIEW`: existe (`grading.get_result`: ids, puntos, estados,
  conteos, timestamps, versiones). Solo post-submit con fila; nunca
  secretos (por construcción, G22).
- `REVIEW_VIEW` (futura): por pregunta
  `{position, question_id, type, difficulty, points, earned, status,
  student_answer, correct_answer?, solution?, errors[{type, human,
  root, consequences}], formula{formula_id, latex?, topic, section,
  source_title}, source{topic, section, doc}, feedback{points[]}}`
  donde `?` = flags `review-policy-v1`. Jamás: rúbrica cruda,
  `calc_entry.expected`, `detail` con ids-respuesta, prompts, packs,
  hashes, `attempt/correction` ajenos.
- `MASTERY_VIEW` (futura, SÍ necesaria): `{topic, banda
  (sólido|practicar|revisar), motivo_humano, examenes_relacionados[]}`.
  Sin scores crudos, sin `confidence`, sin listas de ids, sin
  `error_counts`.

## 2. Gates de estado

Matriz §8 del preaudit (7 estados × 4 vistas). Regla de oro: ningún
contenido post-submit es visible antes de su estado; `CANCELLED` no
produce nada; `INCOMPLETE` muestra resultado con banner pero DENY review.

## 3. Versiones

`review-policy-v1` (futura) + `knowledge fase1-1.0` + `grader/rubric-5.0`
+ `exam-spec-v1` + `correction_version` por pregunta (ya en
`rubric_snapshot`). Review histórico: parámetros congelados en la
primera renderización (sin store: el llamante fija policy; el contrato
exige citarla).

## 4. Presentación de errores (§15–§17)

Taxonomía F5 intacta (16). Presentación: error raíz como titular
(`_FIX_HINTS` + `why`), derivados colapsados como consecuencias vía
`PROPAGATION` (nunca lista plana engañosa). Severidad: banda humana
(leve/media/fuerte); código crudo y `CRITICAL` solo internos.
`severity` NO decide nada en review (informativa).

## 5. Fórmulas y fuentes (§18–§21)

Resolución solo-lectura por `formula_id` (mismo id F1–F6, sin
`review_formula_id`). Mostrar: latex canónico, variables, unidades,
tema/sección/título. Ocultar: hashes, `expression` python, paths
crudos. Fuentes: título+sección; hash interno. Citas solo KB o
corrección validada; sin LLM no hay texto nuevo (abstención explícita
`INSUFFICIENT_EVIDENCE`/`UNSUPPORTED`/`CONTRADICTED`/`GRADING_INCOMPLETE`).

## 6. Numéricas y tipos (§30–§35)

Numérica: `{given (de variables), fórmula (canónica si aplica),
sustitución (propia), cálculo (propio vs esperado SOLO si
reveal_correct_answer), unidad (esperada vs propia), resultado}`.
Nunca recalcular distinto de F5: reutilizar `calculation_results`.
`solution` por tipo: fórmula+cálculo (FORMULA/NUMERICAL/MULTI_STEP),
opción correcta (MCQ/TF), evidencia canónica (SHORT/OPEN/THEORY/
CONCEPTUAL). MCQ/TF: `correct selection = NEVER` en `IN_PROGRESS`;
post-`GRADED` según flag.

## 7. LLM boundary (§22)

Determinista-primero: feedback-5.0+HINTS+evidencia cubren el caso base.
Explicador LLM opcional y apagado por defecto: jamás score/nota/
corrección/resultado/mastery; con evidencia obligatoria, fallback a
plantilla, `source` marcado, temperatura 0.0, sin persistir raw.
CoT interno: P0, jamás expuesto (no existe en stores: verificado).

## 8. Multilingüe (§29)

`feedback_lang ∈ {ca, es}` con diccionarios fijos versionados (plantillas
`_FIX_HINTS`-like por idioma, sin motor MT ni LLM). Invariantes byte:
fórmulas, unidades, variables, números, referencias. Test: mismo caso en
ca/es difiere solo en literales.

## 9. Inmutabilidades (§27, §49–§52)

Review: cero writes (KB, questions, sessions, corrections, mastery,
eval). Recalcular ≠ mutar (nueva versión explícita, fuera de B4).
`mastery_write_rate_from_review = 0` testeable por conteo.

## 10. Compatibilidad (§59–§62, §38)

Funciona sobre F5/F6/B2/B3 sin tocarlos; `Review → Practice` y
re-examen automático explícitamente fuera; los 4 orígenes comparten
contrato con provenance propia; REAL_EXAM sin importer ni mezcla con
GENERATED.
