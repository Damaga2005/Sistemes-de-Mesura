# PHASE_1_REPORT — Ingesta y Knowledge Base canónica

Pipeline: `fase1-1.0`. Fuentes verificadas por SHA-256: 91/91.

| Métrica | Valor |
|---|---|
| docs_theory | 61 |
| sections | 332 |
| chunks | 1903 |
| chunks_dup | 115 |
| formulas | 2896 |
| formulas_latex | 2858 |
| formulas_unicode | 38 |
| tables | 90 |
| visuals | 587 |
| visuals_dup | 25 |
| concepts | 377 |
| eval_questions | 500 |

## Reconciliación PDF↔HTML
| Tema | Vocab HTML | Vocab PDF | Compartido | Jaccard | Cobertura | Estado |
|---|---|---|---|---|---|---|
| 1 | 2201 | 3412 | 1441 | 0.345 | 0.655 | OK |
| 2 | 1565 | 2106 | 1306 | 0.552 | 0.835 | OK |
| 3 | 1612 | 2236 | 1214 | 0.461 | 0.753 | OK |
| 4 | 1332 | 1874 | 968 | 0.433 | 0.727 | OK |
| 5 | 2004 | 2675 | 1430 | 0.440 | 0.714 | OK |
| 6 | 1594 | 2267 | 1191 | 0.446 | 0.747 | OK |
| 7 | 2027 | 2604 | 1665 | 0.561 | 0.821 | OK |
| 8 | 1718 | 2323 | 1329 | 0.490 | 0.774 | OK |
| 9 | 1960 | 2553 | 1512 | 0.504 | 0.771 | OK |
| 10 | 1595 | 1862 | 1188 | 0.524 | 0.745 | OK |

## Calidad
- Fidelidad LaTeX (multiconjunto por doc): OK en 61/61 teoría.
- Visuales: bytes en mapas JS (variantes `IMGDATA`/`FIGS`/`window.__IMG__`), `alt` catalán como caption, 1 fila por asset único con ocurrencias.
- Validación SQLite: OK.
- Near-dups registrados (no fusionados): 0.
- Preguntas V/F: 500 (formatos {'BANC': 100, 'ITEMS': 250, 'DATA': 150}), en base separada.
- Warnings: 250.
- Resoluciones tail-match DOCS→manifest (T6–T10, prefijo numérico omitido en origen): 250.
- Warnings no-eval: 0.


## Aplazado explícito
- Relaciones académicas (`Relationship`): sin extracción verificable determinista; jerarquía en `sections`/`parent_context`. Fase 3 con verificación.
- Variables de fórmulas: solo con evidencia local (`on X és…`); resto `[]` para Fase 3.
- Retrieval/RAG, tutores y examen: fuera de alcance (reglas 7–8).
