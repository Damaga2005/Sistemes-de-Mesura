# F11-B5 — Review / Results / History UX

## Implementación

- `ExamWorkflow.history()` reconstruye actividad desde sesiones y resultados
  F7, sin store adicional y con ownership delegado al dominio.
- `/api/exam/history` expone fechas, estado, provenance y un resumen de
  resultado únicamente cuando el backend lo autoriza.
- `/api/exam/result` aplica una whitelist pública: no salen `student_id`,
  correction IDs, attempt IDs, scoring raw ni preguntas internas.
- Se añadieron entradas directas y reentrables para `history.html`,
  `results.html` y `review.html`, con estados de carga, vacío, no disponible,
  no encontrado y error.
- La navegación enlaza History → Results → Review → Mastery/Practice; el
  contenido se reconstruye desde HTTP después de refresh.

## Verificación

- Tests específicos B5 en `tests/web/test_exam_ux_contract.py`.
- Tests web y application verdes tras el cambio.
- No se introdujo acceso nuevo a SQLite en `web/`.

## Estado y gates

`GO` para B5: benchmark `100/100 ×2`, determinista; 10 tests específicos
verdes; regresión `807 passed` con únicamente los 2 `Gemini HTTP 401`
clasificados como `LIVE_ENV_EXTERNAL`. Fórmula `2896/2896` e aislamiento de
los cinco artefactos canónicos conservados. Las deudas conocidas no se
cuentan como fallos B5.
