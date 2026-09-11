# FASE 11 — Learning Modes + Exam Mode

## 1. Pre-audit

- **Existe**: `AdaptiveLoop.recommend/step` (+novelty Fase 8), Priority
  frozen, PathSelector, DifficultySelector, spacing verdicts,
  RecommendationBuilder + reason codes, exam_adapter,
  StudentService (mastery/history/error/spacing/coverage),
  ExaminerEngine determinista, exam completo (Fase 7: models,
  service, grading, review, review_policy, store + facade
  application/exam + 23 endpoints + exam.js + tests),
  `?from=adaptive` + `adaptive` flag en practice submit.
- **Falta**: noción de modo; selección study/recovery; decisión
  explícita de aislamiento exam; tests de modos.
- **Reutilizado**: todo lo anterior sin modificar.
- **No tocado**: Priority, Difficulty, Examiner, Correction,
  Spacing, exam/*, QuestionStore, KB, fórmulas.
- **Riesgos**: reason codes aditivos (orden intacto); filtros con
  fallback (nunca vacío si practice no lo está).

## 2. Arquitectura

```text
AdaptiveLoop (.recommend/.step, mode="PRACTICE" por defecto)
  └─ app/adaptive/modes.py (validate, mode_code, apply_mode_filter)
       STUDY: solo no-vistas · PRACTICE: intacto
       RECOVERY: solo error recurrente · EXAM: rechazado explícito
```

## 3-5. Study / Practice / Recovery

Study favorece `coverage_unseen`; Practice = comportamiento actual;
Recovery favorece recurrentes (`error_count>=2`, sin clasificador
nuevo). Fórmula Priority intacta.

## 6. Exam Mode

Evaluación cerrada preexistente: blueprint determinista
(`exm-`+sha), snapshot por fingerprint, máquina de estados,
grading idempotente con `attex-` deterministas, review ciega
REAL_EXAM por policy, métricas agregadas en `get_result`.
Sin adaptive durante el examen (verificado estáticamente +
conjunto estable). `mode=EXAM` rechazado en recommend/step:
el examen usa blueprint, nunca selección.

## 7. API

`GET /api/learn/priorities?mode=` (400 ante modo inválido).
Practice submit conserva flag `adaptive` (= practice).
Sin endpoints nuevos de examen.

## 8. Frontend

Pestañas de modo en recomendaciones de progres.js (Estudi/
Pràctica/Recuperació); exam.js ya cubría jugador/resultado/
revisión. Sin lógica de dominio en JS (tests lo fijan).

## 9. DATABASE / MIGRATIONS

Ninguna (sin tablas nuevas; exam usa las existentes).

## 10. Tests

`tests/adaptive/test_modes.py` (18) + `tests/exam/test_exam_isolation.py`
(11) + workflow/server (5). Ver §11.

## 11. REGRESSION

`pytest tests/` → 1019+52 en verde (ver informe final).

## 12. FORMULA GATE

2896/2896, missed=0, 100% (artefacto intacto).

## 13. LLM

`adaptive_decision_llm_calls=0` (grep + `test_no_llm_*` en verde).

## 14-16. REPLAY / MULTI-STUDENT / PROVENANCE

Sin cambios: replay por attempt, aislamiento por student_id,
provenance en DTOs. Verificado en tests de aislamiento.

## 17. LIMITACIONES

Filtros con fallback silencioso a lista completa; STUDY no
distingue unseen-nunca de unseen-olvidado; sin temporizador
frontend de examen (backend decide expiración).

## 18. VERDICT

```text
PASS
```
