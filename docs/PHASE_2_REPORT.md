# PHASE_2_REPORT — Retrieval / RAG Engine

## 1. Resumen

Motor de recuperación académica sobre `knowledge.sqlite` (1903 chunks, 2896
fórmulas): lexical FTS5 + semántico TF-IDF local + fórmulas por símbolos,
fusión RRF, ranking explicado, rerank anti-duplicado PDF, contexto padre,
abstención calibrada y `EvidencePack` para Fase 3. CLI `app.retrieve`
(texto/JSON/debug). Sin LLM, sin red, determinista.

## 2. Arquitectura

Ver `RETRIEVAL_ARCHITECTURE.md`. Flujo: normalización → clasificación (13
tipos) → candidatos (60/60/20) → RRF → ranking (9 componentes) → rerank →
expansión → abstención → pack. `Retriever` Protocol + `EmbeddingProvider`
Protocol: ramas sustituibles sin cambiar el consumidor.

## 3. Métricas (test, n=16; dev n=42 entre paréntesis)

Recall@1 0.786 (0.868) · Recall@5 1.0 (1.0) · Recall_text@5 1.0 (0.974) ·
MRR 0.768 (0.802) · Precision@5 0.757 (0.695) · Formula Recall 0.857 (0.868) ·
Topic Accuracy 0.857 (0.868) · **Sufficiency@5 1.0 (1.0)** · Abstention P/R
1.0/1.0 (1.0/1.0) · FPR 0.0 (0.0).

## 4. Fallos

Test final: 0 (taxonomía en FAILURE_ANALYSIS). Near-miss vigilado:
paráfrasis verbo→nombre (`compensar…offset`, T10 en #5). Dev aportó 7
lecciones con fixes generales (metadata SVG, substrings, fuzzy, plegado
de símbolos, directivos, masa IDF, alts). Sin manipulación del benchmark:
gold con grounding verificado por script, split test intacto hasta el final.

## 5. Decisiones

- Embeddings: TF-IDF local real (sin stack neural offline); interfaz lista.
- Índice: FTS5 + postings JSON, `content_hash` idempotente, ~7,9 MB.
- Ranking: pesos justificados en dev; thresholds en `config.py`.
- Dedup: degradación PDF x0.5 (no fusión silenciosa), dups exactos
  registrados con `dup_of` y penalizados −0.35.
- Abstención: 6 causas explícitas; `unknown_term` con masa<0,6;
  consultas FORMULA/VARIABLE/DEFINITION eximen OOV funcionales.
- Evaluación aislada: servicio ciego a `eval.sqlite` (test).

## 6. Tests

`pytest tests/`: **132 passed** (22 de Fases 0-1 + 110 de Fase 2, matriz §68
superada en todas las filas). Benchmark reproducible:
`python3 -m app.retrieval.benchmark --split {dev,test}`.

## 7. Limitaciones

Semántico no-neuronal (paráfrasis profundas limitadas); benchmark n=58;
ambigüedades genuinas (T1 vs T2 en `u_c`) resueltas por ranking, no por
comprensión; catalán primarily (puente es→ca ~100 entradas + reglas).

## 8. Recomendación

**GO para Fase 3.** Pregunta de cierre: SÍ — el pack entrega evidencia
correcta (sufficiency 1.0), trazada (chunk→hash) y suficiente (padre +
fórmulas + visuales), y sabe decir `No hi ha evidència suficient` (6/6).
Riesgo residual: near-miss de paráfrasis verbal y densidad de `sensibilitat`;
mitigación: Fase 3 debe citar tópico y el router puede pedir top-10.
