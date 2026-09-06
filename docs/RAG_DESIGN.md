# RAG_DESIGN — Retrieval verificado para una asignatura técnica

## Pipeline
```
query → classifier (DEFINITION|EXPLANATION|COMPARISON|FORMULA|CALCULATION|PROCEDURE|CONCEPTUAL|UNIT|CLASSIFICATION|RELATION|APPLICATION|EXERCISE|EXAM|AMBIGUOUS|OUT_OF_SCOPE)
  → retrieval híbrido (BM25 catalán + vectorial + lookup exacto) con filtro topic/source_type
  → rerank (top 20 → top 5) → context assembly (chunk + padre + fórmulas vecinas)
  → LLM (provider abstracto) → verification (cada afirmación ↔ cita) → respuesta + fuentes / abstención
```

## Por qué híbrido (evidencia, no dogma)
- Léxico (BM25, stemming catalán): términos normativos exactos (`incertesa expandida`, `Welch-Satterthwaite`, `guarda de Kelvin`) y símbolos (`u_c`, `k`, `CMRR`). Un embedding solo confunde `sensibilitat` con `resolució` (co-ocurren en T1 §5–6).
- Vectorial: paráfrasis del estudiante (`el dubte de la mesura` → `incertesa`) y preguntas RELATION entre temas.
- Lookup exacto: índice LaTeX normalizado para FORMULA (`U=k·u_c`) y glosario para UNIT (`Ω→resistència`); tabla periódica de tipos para CLASSIFICATION.
- Filtros: `topic` (desambiguar `transimpedància` T6 vs T10), `source_type` (HTML primario, PDF corroboración infraponderada — Decisión D4).
- Rerank 20→5: justificado por el tamaño (~61 docs, chunks de sección): barato y corta el ruido de la doble fuente.
- Assembly padre-hijo: el chunk responde, el padre (`h1/h2` + frase-definición) evita anáforas huérfanas.

## Consultas matemáticas (módulo determinista, no LLM)
Chequeo dimensional/unidades, propagación de incertidumbre (derivadas parciales del modelo T2 §6), sustitución numérica y orden de magnitud. El LLM propone el procedimiento; la aritmética la verifica código. Sin `sympy`-dependencia prematura: Fase 2 empieza con validador de unidades + calculadora de `u_c/U/k` con fórmulas canónicas.

## Verification y abstención (núcleo, no accesorio)
Toda respuesta candidata se contrasta: `soportada | parcial (+advertencia) | sin respaldo → abstención` con la frase canónica. Fuentes citadas como `Tema 2 → §7 → 2_07…#h2-4 (+ Apunts p. X)`. Prohibido internet silencioso: `COURSE_SOURCE` vs `EXTERNAL_SOURCE` siempre etiquetados.

## Decisión vector DB (Fase 2, justificada por volumen real)
~61 docs / miles de chunks / embeddings catalanes: **SQLite (canónico) + índice vectorial local embebido con filtros de metadatos y búsqueda híbrida** (p. ej. sqlite-vec o similar evaluado en Fase 2 contra: instalación cero, persistencia fichero, filtros, portabilidad, coste 0). Nada cloud hasta que las métricas lo exijan. `EmbeddingProvider` abstracto (empezar por un modelo multilingüe con buen catalán; re-embebido solo si cambia el modelo, cache por chunk id).
