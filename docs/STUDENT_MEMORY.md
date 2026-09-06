# STUDENT_MEMORY — Solo rendimiento observado, con prueba

Dos clases y solo dos: PERFORMANCE derivada de eventos. FACTUAL académica
prohibida (la memoria nunca aprende materia §61/§172). Cada memoria:
confianza + nº evidencias + última evidencia + `attempt_ids`/`correction_ids`
(¿por qué creemos esto? → IDs). Sin evidencia suficiente:
INSUFFICIENT_EVIDENCE (no se almacena §64). Inyección manual sin eventos:
rechazada (§142, test). Sin etiquetas psicológicas (§60/§128): solo
"confunde X/Y", "omite unidades", "domina Z", "riesgo en W".

Transacción atómica attempt→correction→mastery→memory (rollback ante fallo
§114); `attempt_id` idempotente (replay, §68/§115); regrade versionado
v1→v2 con motivo (sin borrar §70); review queue PENDING→RESOLVED/REJECTED
con override auditado (§71-73). Dashboard Fase 6: `get_weak_units(kind)`
ya expone conceptos/fórmulas débiles (solo lectura §162).
