# F11-B6 — Final UX Integration / Product Certification

## Integración

B6 no añade funcionalidad de producto. Revalida los contratos ya implementados
en F10 y F11-B0…B5 mediante:

- benchmark reproducible de 125 casos con la distribución completa del prompt;
- checks de app shell, endpoints Study/Tutor/Practice/Adaptive/Exam/History;
- auditoría estática de la UI B5 para secretos, DB directa y metadata interna;
- comprobación de ownership en las fachadas de Exam y Review;
- cross-flow de examen REAL_EXAM y verificación de blindaje;
- conservación de hashes de knowledge, chunks, manifest, eval y GENDB.

## Hallazgos

Se corrigió un P1 propio de B6 en `web/static/js/practice.js`: un `catch`
desparejado impedía compilar el JavaScript y bloqueaba Practice en navegador.
La regresión de sintaxis Node quedó añadida a los tests. La única observación
restante de especificación es la aritmética 120/125 del benchmark, registrada
como P2 documental y resuelta conservando 125 casos.

## Resultado

Benchmark B6: `125/125 ×2`, determinista. Tests B6 y suite web verdes. La
regresión completa queda en `812 passed` y únicamente los dos fallos Gemini
HTTP 401 ya clasificados como `LIVE_ENV_EXTERNAL`.
