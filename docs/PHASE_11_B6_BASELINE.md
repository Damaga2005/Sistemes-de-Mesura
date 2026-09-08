# F11-B6 — Baseline de certificación final

## Estado de partida

F10 y F11-B0…B5 están documentados como certificados/GO. La aplicación
mantiene la frontera `WEB → F10 APPLICATION → F5/F6/F7 → datos` y la UI no
decide score, grading, mastery, prioridad, severidad, provenance ni estados de
examen.

## Preaudit

- App shell: páginas estáticas vanilla, Design System B1 y navegación responsive.
- Study/Tutor/Practice: endpoints del Bridge delegan en F10; Study conserva
  únicamente la deuda SQLite read-only heredada de B2.
- Adaptive/Mastery: las decisiones proceden de F6/F10.
- Exam/Results/Review/History: contratos B4/B5, ownership por estudiante,
  refresh desde backend y blindaje REAL_EXAM.
- Fórmulas: renderer whitelist existente; artefactos canónicos sin cambios.
- No se detectaron nuevas tablas, dependencias, acceso directo de la UI a DB ni
  secretos en los artefactos B5.

## Inconsistencia detectada en el documento

La distribución solicitada para el benchmark suma 125 casos, aunque el texto
indica 120 como mínimo y después exige `120/120`. Se conservan todas las
cantidades por categoría y se certifica `125/125`, que satisface el mínimo y
evita eliminar cobertura explícita.

## Deudas no bloqueantes

- Gemini live HTTP 401 = `LIVE_ENV_EXTERNAL`.
- `web/server.py` SQLite read-only para Study = deuda F11-B2.
