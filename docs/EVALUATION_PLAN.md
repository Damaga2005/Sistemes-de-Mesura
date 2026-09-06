# EVALUATION_PLAN — Cómo sabremos que funciona

Criterio único: *¿responde correctamente usando la fuente adecuada, con trazabilidad y sin inventar?* Responder no es funcionar.

## 1. Dataset (semilla real, no sintética)
Extractor Fase 1 sobre los 10 `entrenament`: ~500 V/F con `{q, a, j, d}` → `data/evaluation/vf_bank.jsonl` (`EvaluationQuestion`). Estratificar por tema y por tipo (DEFINITION/COMPARISON/PROCEDURE). Añadir a mano 30 preguntas: 10 sin respuesta en el material (deben abstener), 10 ambiguas/parciales, 10 multi-tema (p. ej. *¿por qué el soroll limita la resolució?* T1+T4).

## 2. Tests de comportamiento (los del brief, operativizados)
- **Alucinación**: existe / no existe / parcial / ambigua / confusos / multi-tema → `fundamentada | advertencia | abstención`.
- **Confusión**: pares mínimos `incertesa vs error` (T2§1.3/T3§1), `sensibilitat vs resolució` (T1§5–6), `tipus A vs B` (T2§4–5), `coherent vs no coherent` (T8§4–5), `transimpedància T6 vs T10`, `termoparell vs PTAT` (T9§2 vs §6), `chopper vs autozero` (T10§2).
- **Fórmulas**: recuperar `U=k·u_c`, identificar variables+unidades, sustituir, orden de magnitud.
- **Unidades**: magnitud→unidad, unidad→magnitud, conversión, compatibilidad dimensional (SI T1§2).

## 3. Métricas
Retrieval: recall@5/20 por pregunta (fuente esperada recuperada), precisión de cita (cita ↔ fragmento real). Generación: faithfulness (afirmaciones soportadas/total), exactitud V/F, abstención correcta (↑) e incorrecta (↓), corrección matemática y de unidades. Proceso: cobertura de ingesta, % chunks trazables (=100 % exigido), latencia y coste por consulta.

## 4. Ground truth y reglas
Ground truth = material + justificaciones `j` de los entrenament. Prohibido entrenar/indexar con el banco (fuga): el banco vive en `evaluation/`, con split dev/test por tema. Toda regresión de Fase ≥2 corre `pytest tests/ + eval` antes de declarar nada.
