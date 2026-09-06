# AGENTS.md — Reglas persistentes del proyecto

## Idioma
- Fuente en catalán (`lang="ca"`): **conservar literal**, no traducir el material fuente.
- Documentación del proyecto en español. Términos académicos citados en catalán original.

## Source of truth
- Originales (`Damaga2005/Sistemes-de-Mesura`, clon TEMP de solo lectura): **inmutables**. Solo lectura; derivados en `data/processed/`, nunca junto al original.
- Cada derivado cita `source_path + sección + source_hash` (trazabilidad obligatoria).
- Contenido generado por LLM **jamás** entra al knowledge base (`knowledge/` ≠ `generated/` ≠ `student/` ≠ `evaluation/`).
- Sin internet silencioso: `COURSE_SOURCE` vs `EXTERNAL_SOURCE` etiquetados.

## Arquitectura
- Simple, modular, testeable, portable: SQLite + índice vectorial local. Sin microservicios/cloud/colas.
- Abstracciones obligatorias: `LLMProvider`, `EmbeddingProvider`.
- Determinismo: parsers y hashing deterministas; el LLM no hace lo que un parser puede hacer.
- Idempotencia: re-ejecutar ingesta = mismos IDs, 0 duplicados.

## Testing obligatorio
- `pytest tests/` en verde antes de declarar cualquier fase terminada.
- Fidelidad matemática como problema crítico: `u_c(y)` ≠ `uc(y)`, `10^-3` ≠ `103` (test 8).
- Toda afirmación académica nueva en docs debe marcarse `confirmed | inferred | unknown`.

## Anti-alucinación
- Sin respaldo → abstención: `No trobo suport suficient en el material de l'assignatura.`
- Conflictos entre fuentes → registrar `CONFLICT`, nunca resolver en silencio.

## Git y seguridad
- No commitear/pushear/PR sin petición explícita. Antes de cambios grandes: `status`, `branch`, `log`, `.gitignore`.
- Secretos en `.env` (en `.gitignore`); prohibidas API keys en el repo.
- Coste: llamadas LLM mínimas, cachés por hash (parse/embedding/retrieval).

## Convenciones
- Topic derivado de la carpeta `Tema N`, nunca del nombre de archivo.
- Commits pequeños en español, vinculados a la fase (`fase0: ...`).
