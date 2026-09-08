# PHASE_11_B2_BASELINE — Punto de partida (B2.1)

## APIs auditadas (contratos reales, sin DTOs inventados)

- `TutorWorkflow.ask(ctx, query, top_k=10)` → `{ok,data{answer,
  status,abstain,abstention_type,language,claims[{text,type,status,
  evidence_ids}],formulas[{equation_id}],provenance[{source_path,
  source_hash,topic}],versions{reasoning,prompt,retrieval,provider}}}`
  | USER_ERROR (vacía) / VALIDATION (top_k) / GENERATION (provider) /
  RETRIEVAL. Sin sesión. `versions.prompt` es etiqueta de versión,
  no contenido.
- `PracticeWorkflow`: `start(ctx,session,topic,**{question_type,
  section,formula_id,difficulty,seed})` → `{session,question(stem
  view),log}`; `submit_answer(ctx,session,answer,attempt_id)` →
  `{session,result{attempt_id,replayed,status,score,errors[{type,
  severity,root}],mastery[{unit,score,status}]}}`;
  `get_question/get_result/complete` según B4. Tipos: 9 de
  `QUESTION_TYPES`; dificultad EASY/MEDIUM/HARD/EXPERT o "" (auto).
- `StudentService`: `get_topic_mastery`, `get_recent_attempts`,
  `get_weak_units`, `get_error_profile`, `get_unit_history` (solo
  lectura, ideales para Study).
- KB (read-only): topics 1–10, 71 documents (teoria/pdf-apunts),
  332 sections, 377 concepts, 2896 formulas (`expression` canónica),
  1903 chunks, 90 taules markdown, 587 visuals (sense bytes, només
  caption). Cap endpoint de llistat: el bridge llegeix directe.
- Taxonomia correcció: claus `ERROR_HUMAN` (16) + `BAND_HUMAN` +
  `FIX_HINT` — el bridge les projecta (cap duplicat al frontend).

## Stack B2

`web/server.py` (stdlib `http.server` multihil, 0 deps): estàtic +
JSON. Sessions demo en memòria (cookie HttpOnly, estudiant `demo`,
gap D documentat). DBs runtime en tmpdir (GENDB copiada, s.sqlite
nova). Fil per fil amb wiring propi (P2-3/B6); sessions compartides
amb lock. Fórmules: renderer LaTeX llista-blanca server-side.
