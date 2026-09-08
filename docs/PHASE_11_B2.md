# PHASE_11_B2 — Study / Tutor / Practice UX (RESULTADO: GO)

## Implementado (solo `web/` + `tests/web/`)

- **Bridge** (`web/server.py`): 13 endpoints JSON sobre workflows
  certificados; sesiones demo con cookie; KB `mode=ro`; renderer
  LaTeX whitelist (`\frac\sqrt^_`/griego/símbolos; resto texto
  escapado, contenido nunca perdido); errores humanos desde tablas
  backend; `AppError`→HTTP sin tracebacks.
- **Páginas**: study (temas+mastery+next F6 real+tutor),
  practice (config con solo opciones soportadas, inputs por tipo,
  submit anti-doble, corrección con labels/hints/mastery),
  topic/content (jerarquía real KB, fórmulas con `formula_id`).
- **Hallazgo integrado**: retriever compartido entre hilos falla
  (P2-3/B6 conocido) → bridges por hilo + sesiones compartidas
  (probado: submit concurrent [False,True], smoke HTTP E2E verde).

## Tests: 48 web passed

Estáticos (17 B1 + 14 UX: páginas, wiring fetch, fieldset/legend,
live regions, no-random/sort, innerHTML solo renderer, no-domini,
no-storage) + bridge E2E (17: topics/next/mastery, tutor
answer/abstain/empty, practice flujo/errores enriquecidos/doble
submit, latex ×3, seguridad ×3, hilos, aislamiento).

## Gates

```text
Regresión: 786 passed / 2 deselected (live 401 externa)
Fórmula: 2896/2896 (cd2acfed) · Aislamiento: 7/7 + GENDB restaurada
Seguridad JS: 0 eval/storage/cookie/innerHTML libre
Perf: web/ 110 KB (JS 25 KB), 0 deps
P0: 0 · P1: 0 · P2: 1 (sesión demo sin auth = gap D) · P3: 0
```

## Limitaciones

Estudiante demo único (sin auth, gap D); seed manual; tutor sin
filtro por tema (chip solo visual); multi-step en un textarea;
imágenes KB sin bytes (solo caption); fórmulas sin KaTeX.

## Veredicto

```text
F11-B2
======

STATUS: GO

P0: 0
P1: 0

Study UX: PASS
Tutor UX: PASS
Practice UX: PASS
Correction UX: PASS

Responsive: PASS
Accessibility: PASS
Security: PASS

Domain duplication: 0

Formula: 2896/2896
Isolation: PASS
F0–F10 integrity: PASS

NEXT:
F11-B3 — Adaptive / Mastery UX

STOP
```
