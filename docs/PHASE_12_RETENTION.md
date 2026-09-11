# FASE 12 — Retention / Forgetting + Recovery Intelligence

## 1. Pre-audit

- **Señales de retention existentes**: `MasteryState` (score,
  confidence, attempt/correct/incorrect_count, last_attempt,
  last_correct, error_counts, status UNKNOWN/EMERGING/DEVELOPING/
  PROFICIENT/MASTERED/AT_RISK donde AT_RISK = últimos 3 fallos y
  MASTERED = score>=0.9 con n>=4 y >=3 correctos), `student_spacing`
  (first/last/next_review, review_count, interval_days 1/3/7 ×2 cap
  30, last_status, last_score; reloj inyectable vía `get_due_units`
  y `now` del loop), `mastery_events` (signals + root_errors en
  orden), `question_history` (has_seen), `error_memory`
  (recurrentes count>=2).
- **Señales de spacing**: buckets VERY_RECENT/RECENT/NORMAL/OLD,
  veredicto ALLOW/DEFER, criticidad (debilidad > spacing).
- **Señales de mastery**: `status_for` versionado; `get_weak_units`,
  `get_coverage` (mastered/weak/learning/unseen).
- **Señales de error**: `get_recurrent_errors` ordenado por
  severidad→count→recencia→clave; reason code `error_recurrent`.
- **Señales de historial**: `get_unit_history` (estado + eventos).
- **Faltaba**: distinción unseen-nunca vs aprendido-potencialmente-
  olvidado; noción de riesgo (AT_RISK retention) y olvido
  (FORGOTTEN) con protección anti-falso-olvido; Recovery solo
  miraba errores recurrentes.
- **Reutilizado**: todo lo anterior sin modificar comportamiento.
- **No tocado**: intervalos F10, fórmula Priority, Difficulty,
  Examiner, Correction, exam/*, KB, fórmulas, QuestionStore.
- **Riesgos**: colisión nominal `AT_RISK` (mastery = 3 fallos) vs
  `AT_RISK` (retention = consolidada próxima a revisión) —
  documentada; el submit refresca `student_spacing` (el vencimiento
  previo se infiere vía proxy de reinicio, documentado abajo).

## 2. Modelo de datos

Ninguna migración, ninguna tabla nueva. Retention se deriva de
`MasteryState + student_spacing + mastery_events`. Política
versionada aditiva `retention-policy@v1` (at_risk_lead_ratio 0.5,
forgotten_min_correct 3, forgotten_min_attempts 3,
no_spacing_at_risk_days 14).

## 3. Retention model

Único cálculo canónico `app/adaptive/retention.py::
calculate_retention(svc, student_id, uid, now=None)`. Solo lectura,
determinista, sin modelo de lenguaje, sin ML, sin persistencia.

## 4. Estados

`UNSEEN` (n==0) · `LEARNING` (practicada no consolidada o débil) ·
`MASTERED` (status MASTERED vigente, al día, sin riesgo) · `DUE`
(`next_review <= now` F10) · `AT_RISK` (consolidada + transcurrido
>= 0.5×intervalo, sin evidencia negativa) · `FORGOTTEN`
(historial fuerte + (vencida | intervalo reiniciado a 1 con
historial) + última señal 0.0).

## 5. At-risk

`MASTERED/PROFICIENT` (o correct>=3 o score>=0.9) acercándose a
`next_review` (fracción del intervalo) o, sin fila de spacing,
>=14 días sin práctica. Nunca con evidencia negativa fresca.

## 6. Forgotten

Exige las tres: historial fuerte (correct>=3) + vencimiento
(`due`, o proxy de reinicio: review_count>=2, interval==1,
last_status INCORRECT — el submit refresca la fila en la misma
transacción) + evidencia negativa fresca (última signal 0.0).
Sin evidencia negativa: como máximo AT_RISK/DUE. `UNSEEN` jamás
es `FORGOTTEN`.

## 7-8. Recovery / Study / Practice

Recovery: FORGOTTEN+recurrente > FORGOTTEN > recurrente > DUE >
AT_RISK (`recovery_rank`; filtros, no Priority). Study: UNSEEN >
FORGOTTEN > AT_RISK > DUE (`study_rank`; fallback intacto).
Practice intacto (mismo orden que defecto). Reason codes aditivos
`retention_at_risk/retention_due/retention_forgotten` (observa-
bilidad; orden/scoring/routing intactos).

## 9. Exam isolation

Sin cambios: `mode=EXAM` rechazado en recommend/step; blueprint
cerrado, grading determinista. Los submits de examen siguen
alimentando mastery/history (evidencia, no routing).

## 10. Spacing / ErrorMemory / Coverage

Intervalos 1/3/7 ×2 cap 30 intactos (test de invarianza).
ErrorMemory intacto (recurrentes CD). Coverage intacto
(`coverage_unseen/weak` + `spacing_due` conservados).

## 11. Clock / multi-student / replay

`now` inyectable en `calculate_retention`, `apply_mode_filter`,
`recommend/step`, `get_due_units`. Todo retention
student-scoped (test A-mastered vs B-unseen). Replay no duplica
(submit idempotente; retention recalculada igual).

## 12. Heurística

`retention_score` 0..1 = mastery × (1 − overdue/(interval+7) si
due) × 0.5 si evidencia negativa. Heurística operativa, NO curva
científica de memoria.

## 13. Limitaciones / futuro

Proxy de reinicio en vez de historial de spacing; `AT_RISK` de
mastery ≠ `AT_RISK` de retention (nombres iguales, niveles
distintos); sin calibración empírica de umbrales; Study no
reescribe prioridades globales.
