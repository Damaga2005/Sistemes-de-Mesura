# F11-B6 — Fix de auditoría

## Hallazgo

La auditoría final encontró un P1 en `web/static/js/practice.js`: el bloque
`}).catch(...)` posterior a `playQuestion()` no tenía una promesa asociada y
provocaba `SyntaxError: Unexpected token ')'` al cargar la página.

## Corrección

Se eliminó solamente ese bloque inválido. El `catch` legítimo de
`/api/practice/start` permanece en `start()`. No se modificó el contrato de
Practice, corrección, mastery ni Application Layer.

## Verificación

- Todos los JS: `node --check` PASS.
- Test de regresión de sintaxis añadido a `tests/web/test_b6_certification.py`.
- B6 tests: PASS.
- Benchmark B6: `125/125 ×2`.
- No se tocaron artefactos canónicos.
