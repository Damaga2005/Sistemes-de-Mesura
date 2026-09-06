# DATA_MODEL — Entidades y metadatos

## Chunk (unidad mínima recuperable)
```json
{
  "id": "sm-02-abc123#2_07$h2-1$c0",
  "course": "Sistemes de Mesura (230920)",
  "topic": 2, "doc": "2_07_incertesa_expandida.html",
  "section_h1": "7. Incertesa expandida, factor de cobertura i graus de llibertat",
  "section_h2": "4. Graus de llibertat efectius: Welch-Satterthwaite",
  "source_path": "Tema 2/2_07_incertesa_expandida.html",
  "source_type": "html",
  "source_page": null,
  "content_type": "formula | definition | explanation | procedure | classification | example | warning | comparison | table | unit",
  "text": "...",
  "formula_ids": ["eq-..."],
  "image_refs": [],
  "parent_context": {"prev": "...", "next": "...", "doc_order": 7},
  "language": "ca",
  "source_hash": "sha256:...",
  "pipeline_version": "fase1-0.1",
  "confidence": 1.0
}
```
Campos exigidos por los datos (más allá del mínimo del brief): `section_h1/h2` (la jerarquía existe),
`parent_context` (anti-`"és igual a..."` huérfano), `formula_ids`/`image_refs` (fórmulas y visual son de primer nivel),
`doc`+orden de lectura (los index lo declaran), `pipeline_version` (reproducibilidad).

## Formula
```json
{"equation_id": "eq-sm02-001", "expression": "U=k\\,u_c", "variables": [{"sym": "U", "meaning": "incertesa expandida", "unit": "unitat del mesurand"}, {"sym": "k", "meaning": "factor de cobertura"}, {"sym": "u_c", "meaning": "incertesa tipica combinada"}], "meaning": "...", "conditions": ["..."], "topic": 2, "source": "Tema 2/2_07...#h2-1", "source_hash": "sha256:..."}
```
`expression` = LaTeX del comentario HTML (canónico). `variables` se extraen del texto vecino en Fase 1; si no se encuentran → `NEEDS_REVIEW`, nunca inventar.

## Concept / Relationship / Unit / VisualAsset / Source
- `Concept{term_ca, definition, synonyms[], abbreviations[], topic, source_ids[]}` — término canónico en catalán; sin traducciones inventadas (glosarioextractivo).
- `Relationship{subj, pred, obj, source_id}` — predicados cerrados: `es-un, es-element-de, es-classifica-segons, te, savalua-per, limita, converteix, mitiga, requereix, millora, aplica-a`.
- `Unit{symbol, quantity, si_base|derived, topic, source_id}` — p. ej. `Ω↔resistència` (T1 §2, T5).
- `VisualAsset{sha256, topic, doc, section, kind: circuit|diagrama|grafica|foto|taula-imatge, image_context, source}`.
- `Source === data/source_manifest.json` (91 entradas, `id: sm-<tt>-<hash10>`, `sha256` completo).

## EvaluationQuestion (separada de conocimiento)
```json
{"qid": "eval-t02-001", "question": "...", "expected_topic": 2, "expected_source": "Tema 2/2_0X...", "expected_answer_points": ["..."], "difficulty": "recordatori|aplicacio|analisi", "qtype": "V/F", "origin": "entrenament-JS (banc)")
```
Semilla: ~500 V/F con justificación ya existentes en `entrenament` (ver PHASE_0_AUDIT §7). Nunca en el índice de conocimiento.

## Entidades diferidas (diseñadas, no implementadas)
`StudentState{concept, mastery 0..1, mistakes[], attempts, last_review, next_review}`, rúbricas (`conceptual/formula/procedure/calculation/units/precision/result`), modos (`STUDY/TRAINING/EXAM/REVIEW`). Tabla de correspondencia en EVALUATION_PLAN.
