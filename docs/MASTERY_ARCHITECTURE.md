# MASTERY_ARCHITECTURE — Dominio como evidencia acumulada (no nota)

Unidades: `formula:*` · `concept:*` · `section:T..:*` · `topic:T..`, derivadas
de cada corrección (fórmulas/conceptos de la pregunta + sección + tema).
Política `mastery-policy-v1` (versionada): señal 1.0/0.5/0.0; score = media
ponderada con sesgo suave a recencia (w=1+0.1i, historial intacto);
confianza = min(1,n/8)·(1−var/4) — 1 acierto NO da 100 %.

Estados deterministas: UNKNOWN (0) · EMERGING · DEVELOPING · PROFICIENT ·
MASTERED (≥0.9 + ≥4 intentos + ≥3 correctos) · AT_RISK (últimos 3 mal).
NEEDS_REVIEW/UNGRADABLE/NO_ANSWER registran intento sin mover score (§122).

Eventos inmutables (`old/new/reason/evidence/version`); `replay(events) ==
estado` (test). Agregación subida por intentos (formula→…→topic) con
co-ocurrencia observacional, sin inventar dependencias (§101). Recencia
documentada, sin decay destructivo (§66). Sin randomness (§49).
