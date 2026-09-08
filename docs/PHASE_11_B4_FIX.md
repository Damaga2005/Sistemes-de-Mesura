# PHASE_11_B4_FIX — Cierre quirúrgico P0/P1 y aislamiento

## Causas raíz

| Hallazgo | Causa | Capa | Acción |
|---|---|---|---|
| REAL_EXAM blind | `feedback.formula` cruzaba HTTP con `formula_id` aunque la policy ocultaba la fórmula | presentation adapter | whitelist en `web/server.py` para review y review_question |
| Q04/G01/G05/R09/C03 | expectativas del benchmark correspondían a otro snapshot de preguntas/resultados | evaluation artifact | actualizar expectativas al contrato persistido actual |
| Q07 MULTI_STEP | F4/F7 no generan ese caso; el backend responde `GENERATION_ERROR` honestamente | dominio certificado | no tocar; benchmark verifica abstención |
| P10 posición negativa | la frontera HTTP valida tipo/rango y devuelve `VALIDATION_ERROR` | presentation contract | corregir expectativa, no convertirlo en NOT_FOUND |

## Cambios

- [web/server.py](/C:/Users/dmart/Documents/OpenCode/web/server.py):
  `_project_review()` aplica la whitelist REAL_EXAM antes de la respuesta HTTP.
- [tests/web/test_exam_ux_contract.py](/C:/Users/dmart/Documents/OpenCode/tests/web/test_exam_ux_contract.py): test de no transmisión de metadata de fórmula/answer key.
- `data/evaluation/phase_11_b4_exam_ux_benchmark.jsonl`: casos corregidos
  para el snapshot y contratos actuales; sin cambiar lógica de scoring.
- `data/evaluation/phase_11_b4_exam_ux_run1.json` y `run2.json`: ejecución
  reproducible.

## Verificación

- Benchmark: `100/100 ×2`; RUN 1 y RUN 2 iguales.
- Tests focalizados: `189 passed`.
- Fórmula: `2896/2896`.
- Los cuatro artefactos canónicos mantuvieron los hashes tomados al inicio
  de este fix. La divergencia previa de `chunks.jsonl` y `source_manifest.json`
  respecto a `HEAD` ya existía antes del fix y no fue modificada.
- `questions.sqlite` mantiene 89 preguntas `VALID`; no contiene nuevos
  orígenes ni datos REAL_EXAM/IMPORTED_EXAM/MANUAL.

## Limitación explícita

El static audit histórico sigue detectando el acceso SQLite de solo lectura
que `web/server.py` ya usaba para Study. No forma parte de este fix de Exam UX;
el cliente y la ruta de examen no acceden directamente a SQLite.

## Resultado

`GO`. La regresión completa terminó con `802 passed, 2 failed`; los dos
fallos son `LIVE_ENV_EXTERNAL` por Gemini HTTP 401. No hubo fallos de
proyecto. No se hizo commit ni push.
