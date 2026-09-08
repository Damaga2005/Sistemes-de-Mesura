# F11 Product Experience Certification

## Veredicto

`F11-B6 STATUS: CERTIFIED`.

Tras corregir el P1 de sintaxis de Practice, la capa de experiencia de producto queda certificada sobre los contratos
F0–F10 y F11-B0…B5. Results, Review, History, Exam, Adaptive, Mastery,
Study, Tutor y Practice conservan sus límites de aplicación/dominio. No se
introdujo persistencia paralela, scoring frontend, mastery frontend, IA nueva,
Calendar ni Documents.

## Evidencia

- `data/evaluation/phase_11_b6_final_certification_benchmark.jsonl`:
  125 casos, distribución completa.
- Runs 1 y 2: `125/125`, deterministas.
- Suite completa: `812 passed`, 2 `LIVE_ENV_EXTERNAL` por Gemini HTTP 401.
- Fórmulas: `2896/2896`.
- Isolation: hashes canónicos conservados; GENDB restaurada a su hash baseline.
- No commit ni push.

## Corrección B6

`practice.js` compila correctamente con `node --check`; se eliminó únicamente
el `catch` desparejado de `playQuestion` y se conservó el manejo de errores de
`start`.

## P2

La especificación del benchmark dice 120 casos, pero su distribución suma 125.
Se mantuvieron las categorías solicitadas y se reporta el total reproducible de
125.

## Known non-blocking

- Gemini HTTP 401 = `LIVE_ENV_EXTERNAL`.
- Study SQLite read-only boundary = deuda F11-B2.
