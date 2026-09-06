# RETRIEVAL_SCHEMA — Cómo el Retrieval consume la KB (Fase 1)

Fuente de verdad: `data/processed/knowledge.sqlite` (pipeline `fase1-1.0`).
El índice (`data/index/`) deriva de ella y nunca la modifica.

## Tablas consumidas

| Tabla | Filas | Uso en retrieval |
|---|---|---|
| `sources` | 91 | `source_hash` para trazabilidad; verificación de filtros |
| `documents` | 71 (61 teoria + 10 pdf) | `title`/`h1` para FTS (peso x3); `doc_id → source_id` |
| `sections` | 332 | `h2` para FTS (peso x3); filtro `section`; contexto padre |
| `chunks` | 1903 | corpus recuperable: `text`, `topic`, `content_type`, `formula_ids`, `image_refs`, `parent_context`, `dup_of` |
| `formulas` | 2896 | índice de símbolos LaTeX; `math_universe` para routing |
| `tables_t` | 90 | estructura preservada (no se aplana: `markdown` + `records_json`) |
| `visuals` | 587 assets | `asset_id` + `caption` (alt catalán) + `occurrences` en el pack |
| `concepts` | 377 | lookup de conceptos mencionados en la query (top 10) |
| `reconciliation` | 10 | justifica `PDF_CORROBORATION_CAP` y la degradación PDF |

## Índices derivados (`data/index/`, `index-2.0`)

| Artefacto | Tamaño | Contenido + hash |
|---|---|---|
| `lexical/fts.sqlite` | ~5,0 MB | FTS5 `unicode61`, columnas `text(1.0)/h1(3.0)/h2(3.0)` |
| `semantic/vocab.json` | ~0,6 MB | vocabulario (11.357 términos), idf, normas |
| `semantic/postings.json` | ~2,2 MB | postings TF-IDF redondeados a 6 decimales |
| `manifest.json` | — | `content_hash` conjunto, modelo, versión, timestamp (fuera del hash) |

Idempotencia: reconstruir produce el mismo `content_hash` (test `test_idempotency_rebuild_stable`).

## Relaciones que el ranking respeta

- `chunk.formula_ids → formulas.equation_id`: evidencia de fórmula con contexto.
- `chunk.image_refs → visuals.asset_id`: referencia trazable (nunca binario en el pack).
- `chunk.section_id → sections`: vecinos y `parent_context`.
- `documents.source_id → sources.id = manifest.sm-TT-*`: cadena chunk→section→document→source→hash.
- PDF↔HTML: sin enlace explícito por fragmento; la equivalencia se penaliza por
  near-duplicado (Jaccard ≥ 0,8 → `pdf-corroboration` x0,5) en lugar de sumar 2X.

## Aislamiento

`data/evaluation/eval.sqlite` (500 V/F) **no** es legible por `RetrievalService`
(verificado por test: la cadena `eval.sqlite` no aparece en el servicio).
