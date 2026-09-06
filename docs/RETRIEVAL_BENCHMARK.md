# RETRIEVAL_BENCHMARK — Dataset, métricas y resultados

## Dataset (`data/evaluation/retrieval_benchmark.jsonl`, 58 items)

Generado por `app/make_benchmark.py`, que **aborta si un gold no tiene grounding**
por búsqueda directa en `chunks.jsonl`/`formulas.jsonl` (independiente del retriever).
`app/retrieval/benchmark.py` lo ejecuta y escribe
`data/evaluation/retrieval_results_{dev,test}.json`.

| Cat | n | Contenido |
|---|---|---|
| concept/formula/variable/unit/procedure | 8/8/5/4/5 | Términos, `U=k·u_c`, NTC, Hall, `u_c/k/Z`, Ω/Hz, Welch, 3 fils, unió freda |
| comparison/ambiguity/visual/topic | 6/6/4/6 | A-vs-B, sensibilitat…, LVDT/figuras, Tema N |
| abstention | 6 | Tema 20, Champions, paella, president, fotosíntesi, Quixot (ausencia verificada) |
| es + typos | 7 integrados | `incerteza`, `Wheatston`, termopar, polarización… |

Split estratificado por categoría: **dev 42 / test 16**. Pesos/thresholds
calibrados **solo en dev**; test intacto hasta el informe final (§69-70).

## Métricas (definiciones operativas)

- `recall_topic/text@K`: gold de tópico/texto en top-K. `formula_recall@5` análogo.
- `topic_accuracy@1`, `mrr` (primer resultado suficiente), `precision@5`,
  `hit_rate@5`, `sufficiency@5` = **métrica crítica**: tópico AND (texto OR
  fórmula OR fuente) en top-5 → ¿puede Fase 3 responder sin inventar?
- `abstention_precision/recall`, `false_positive_rate` (abstenciones indebidas).

## Resultados (congelados)

| Métrica | dev (42) | test (16) |
|---|---|---|
| recall_topic@1 / @5 | 0.868 / 1.0 | 0.857 / 1.0 |
| recall_text@5 | 0.974 | 1.0 |
| formula_recall@5 | 0.868 | 0.857 |
| topic_accuracy@1 | 0.868 | 0.857 |
| **sufficiency@5** | **1.0** | **1.0** |
| mrr / precision@5 | 0.802 / 0.695 | 0.768 / 0.757 |
| abstention P / R | 1.0 / 1.0 | 1.0 / 1.0 |
| false_positive_rate | 0.0 | 0.0 |

## Calibración (dev, documentada, no repetida en test)

`ABSTAIN_MASS=0.35`, `ABSTAIN_MIN_SCORE=0.12`, márgenes 0.03/0.06, pesos del
ranking y `PDF_CORROBORATION_CAP=0.85`. Cambios durante dev respondieron a
fallos medidos (ver FAILURE_ANALYSIS); tras congelar, test se ejecutó 2 veces
(diagnóstico B06/I06 → 1 fix general de tokens directivos + 1 de routing con
señal; re-verificado dev+test al 100 %).

## Limitaciones

n=58 pequeño; categorías finas (units=4) con intervalos anchos. Split único
sin validación cruzada (documentado; Fase 3+ puede ampliar el banco con las
500 V/F como preguntas de respuesta, no como retrieval gold).
