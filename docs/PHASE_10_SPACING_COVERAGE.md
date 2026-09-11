# FASE 10 — Spaced Repetition + Learning Coverage

## 1. Qué se implementó

Memoria persistente de revisión (`student_spacing`) + cobertura del
temario (`StudentService.get_coverage`) + exposición en recomendaciones
(`spacing_due`, `coverage_unseen`, `coverage_weak`). Sin tocar fórmula
Priority, Difficulty, Examiner, Correction, ni pesos.

## 2. Modelo de datos

`student_spacing(student_id, unit_kind, unit_id, first_review,
last_review, next_review, review_count, interval_days, last_status,
last_score, last_attempt_id)`, PK triple, índice
`(student_id, next_review)`. Migración `004` aditiva (+ compat
`exam_sessions`, targets 3→4). Sin backfill (documentado en el SQL).

## 3. Política (`review-schedule-policy v1`)

outcome correct → duplica intervalo (tope 30); partial → 3 días;
incorrect → 1 día; otros estados conservan. Fila nueva: 7/3/1.
`due` ⟺ `next_review <= now`. Reloj inyectable (`now` param / `_now`
monkeypatch en tests); producción usa tiempo real.

## 4. Coverage

Universo KB exacto: 10 topics + 2896 fórmulas + 365 conceptos +
271 secciones = 3542 unidades. Estados derivados de MasteryState
existente (sin umbrales nuevos salvo regla documentada weak =
AT_RISK/EMERGING con intentos). `seen` exige `attempt_count>0`;
`unseen ≠ weak`.

## 5. Integración con AdaptiveLoop

`step()` intacto; `RecommendationBuilder._recommend` añade códigos
aditivos (orden/scoring/routing intactos; `strategy_for` solo lee
prefijos `raiz:`). Novelty (pregunta) y due (unidad) coexisten:
unidad due + pregunta vista → se busca alternativa; sin alternativa →
`no_novel_question_available` honesto.

## 6. Relación con QuestionHistory / ErrorMemory / Mastery

Solo lectura de sus estados; una fila de spacing por unidad tocada
por cada submit, en la misma transacción (attempt+correction+
mastery+history+errors+spacing, un commit; replay retorna antes).

## 7. Idempotencia

Replay no toca spacing (retorno temprano). Upsert atómico por PK;
concurrencia bajo la misma protección transaccional existente.

## 8. Decisiones no tomadas

Sin re-baremo de Priority; sin `target_error` en QuestionSpec
(routing actual por `raiz:` basta); sin spaced completo con
olvido/exclusiones; sin endpoints HTTP nuevos; sin backfill.

## 9. Limitaciones

Secciones/conceptos del universo usan IDs KB literales; si un
generador futuro usara otro formato, esas unidades quedarían
fuera del universo (documentado; topics/fórmulas exactos siempre).

## 10. Métricas

18 tests nuevos (`tests/student/test_spacing.py`); suite
1019 passed + 1 skipped (preexistente); benchmarks adaptive OK;
fórmula 2896/2896; aislamiento 7/7.
