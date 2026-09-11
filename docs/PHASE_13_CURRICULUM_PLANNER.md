# FASE 13 — Curriculum Planner + Long-Term Learning Path

## 1. Problema / audit

El sistema respondía "¿qué pregunta hago ahora?" (AdaptiveLoop)
pero no "¿qué estudio hoy / esta semana / más adelante?".
Audit read-only: sin scheduler/plan/calendar existente; jerarquía
KB real = documents(topic 1–10) → sections(h2) → concepts(term_ca)
→ formulas(equation_id, 2896); señales reutilizables = Priority
congelada, retention F12, spacing F10, ErrorMemory F9, history F8,
coverage F10, modes F11, `GET /api/learn/priorities`.

## 2. Arquitectura previa / nueva

Previa: KB → Student Model → Spacing → Priority → AdaptiveLoop →
Question. Nueva: idéntica + `CurriculumPlanner` entre Priority y
AdaptiveLoop (WHAT/WHEN arriba, WHICH QUESTION abajo). EXAM
excluido de la generación automática.

## 3. Unidad curricular

`knowledge_unit_id` existente (topic/section/concept/formula).
Sin ontología nueva. Plan Item ≠ question (sin `question_id`).

## 4. Inputs

Coverage, Mastery, Retention, Spacing, ErrorMemory, Priority
(scores congelados para ordenar dentro del bucket),
jerarquía Topic/Section. Difficulty excluida a propósito: se
decide por pregunta en AdaptiveLoop, no por unidad.

## 5. Horizons

TODAY (urgente) / NEXT_7_DAYS (cola) / LATER (estable). Sin
calendario real, sin horas, sin sincronización externa.

## 6. Ranking

Sin fórmula nueva: clases por reglas sobre señales existentes
(FORGOTTEN 0, DUE 1, recurrente+weak 2, recurrente 3, weak 4,
UNSEEN 5, AT_RISK 6, vence-pronto 7, learning 8, mastered 9);
dentro de clase manda Priority congelada + uid. Modo
recomendado: FORGOTTEN/recurrente → RECOVERY, UNSEEN → STUDY,
resto → PRACTICE.

## 7. Reason codes / provenance

Vocabulario existente (`coverage_unseen/weak/mastered`,
`retention_forgotten/due/at_risk`, `error_recurrent:key:xN`,
`mastery_weak`, `spacing_due`). Provenance: policy
curriculum-policy@v1, now, student_id, horizon, plan_id
(`plan-`+sha12 de contenido ordenado).

## 8. Determinismo / multi-student / recompute

Mismo estado+now → mismo plan (test). Sin duplicados
(one-item-per-unit). Aislamiento por student_id (test).
Plan derivado, sin persistencia: tras un submit relevante el
plan_id cambia (test).

## 9. Integración AdaptiveLoop / Exam

Item → Priority(candidates) → selector.to_spec → Examiner
(test). EXAM: sin blueprint/grading/review tocados; ningún item
EXAM; `adaptive_decision_llm_calls=0`.

## 10. DB / API

Sin migración. Nuevo `GET /api/learn/plan?horizon=&limit=`
(400 ante horizon inválido). Sin JS adaptativo (presentación
futura).

## 11. Tests

`tests/adaptive/test_planner.py`: 15 passed (nuevo, débil,
recurrente, forgotten/due, mastered→later, determinismo,
no-dup, aislamiento, horizontes/límites, recompute, integración,
no-LLM, exam-excluido, fórmula intacta, endpoint ×2).

## 12. Limitaciones / futuro

Pool unseen acotado (60, fórmulas + topics); sections/concepts
unseen solo vía filas tocadas; umbrales de clase sin calibrar;
sin workload estimado (`unknown` por defecto: no se inventan
tiempos); sin UI de plan; "Exam session Friday" explícitamente
fuera de alcance.
