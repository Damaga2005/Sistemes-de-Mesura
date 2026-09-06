# KNOWLEDGE_ARCHITECTURE — Arquitectura del sistema de conocimiento

## 1. Principio rector
El LLM es capa de razonamiento; la verdad es el material. Toda afirmación académica trazable a `manifest.id` + sección; sin respaldo → abstención (`No trobo suport suficient en el material de l'assignatura.`).

## 2. Flujo validado contra los datos
```
Material (TEMP, read-only) → Ingestion (parsers deterministas) → Normalización + metadata
  → Knowledge Store (JSONL canónico, SQLite) + Vector Index (embeddings de chunks con contexto)
  → Retrieval híbrido → Rerank → Context assembly (chunk + padre) → LLM (provider abstracto)
  → Verification (grounding por citas) → Respuesta + fuentes / abstención
```
Se adopta el diagrama del brief **con dos precisiones impuestas por la auditoría**: (a) doble fuente HTML/PDF con prioridad declarada; (b) fórmulas como objetos de primer nivel extraídos de comentarios LaTeX, no de embeddings.

## 3. Fuente primaria vs secundaria (Decisión D4)
- **Primaria: HTML de teoría (61 docs).** Estructura semántica + LaTeX canónico + captions. Cada chunk cita `source_path/h1/h2`.
- **Corroboración: PDF Apunts (10 docs, 523 págs).** Más texto (~1,5× en T2); sirve para verificación cruzada y para lo visual que falte en HTML. Se indexa con `source_type=pdf` + nº página, y el retriever lo infrapondera por defecto para evitar doble conteo.
- **No indexar como teoría:** `index` (navegación; solo metadatos de orden/dedicación), `entrenament` (banco V/F → `evaluation/`), CSS/JS/breadcrumb/instrucciones de edición Tema 1.

## 4. Entidades (mínimas, justificadas)
`Course(230920, ETSETB-UPC)` → `Topic(1..10)` → `Document(h1, kind, order)` → `Section(h2)` → `Chunk` (+`parent_context`) ·
`Concept(término catalán canónico)` · `Formula(latex, variables, units, meaning, conditions)` ·
`Unit/Quantity` · `VisualAsset(hash, image_context)` · `Relationship(sujeto, predicado, objeto, source)` ·
`EvalQuestion` (solo de entrenament, separada) · `StudentState` (separado físicamente, ver §7).

## 5. Chunking semántico (nunca por tokens fijos)
Unidad = bloque tipado dentro de su sección: `definition | concept | explanation | formula | derivation | procedure | classification | example | warning | comparison | table | unit`. Reglas: un chunk = 1 bloque + `parent_context {topic, doc_h1, section_h2, prev/next}`; tablas e imágenes no se parten; fórmulas viajan con su párrafo de definición de variables; overlap solo semántico (repetir la frase-definición, no N tokens). Hijo recupera + padre acompaña (parent-child retrieval).

## 6. Fórmulas como objetos de primer nivel
Parser Tema 2–10: comentario `<!-- $L$ -->` + SVG hermano → `Formula{expression: L, source, variables: [] (Fase 1 las extrae del texto vecino), synonyms:[render_txt]}`. Parser Tema 1: `<sub>/<sup>` → LaTeX con test de fidelidad (p. ej. `u_c(y)` nunca `uc(y)`). Búsqueda exacta de fórmula (índice LaTeX normalizado) separada de la semántica: `sensibilitat` ≠ `equació de sensibilitat` ≠ `sensibilitat vs resolució` se resuelven por router (§RAG_DESIGN).

## 7. Separación estricta de datos
`knowledge/` (fuente, inmutable, versionada por hash) ≠ `generated/` (explicaciones LLM, nunca reindexadas) ≠ `student/` (mastery, errores, intentos) ≠ `evaluation/` (bancos V/F + rúbricas). Un error frecuente (`confondre u_c amb U`) vive en `student/`, jamás corrige la `Formula` canónica.

## 8. Trazabilidad y versionado
Cada chunk/formula/relación: `{id determinista (hash ruta+sección+índice), source_path, source_type, source_page, source_hash, pipeline_version}`. Ingesta idempotente (re-ejecutar = mismos IDs, 0 duplicados). Informe `INGESTION REPORT` por ejecución (docs OK/fallo, warnings, fórmulas, visual, dups, conflictos, cobertura).

## 9. Escalabilidad contenida (anti-sobreingeniería)
Volumen real: ~61 docs teoría, ~1,2 M chars PDF + ~visible HTML, 2.858 fórmulas, ~1,3k visuales. Cabe en SQLite + un índice vectorial local embebido. Sin microservicios, sin cloud, sin colas. Abstracciones obligatorias: `LLMProvider`, `EmbeddingProvider` (Muse Spark hoy, cualquier otro mañana). Cachés: parse (por hash), embeddings (por chunk id), retrieval (solo dev).
