-- 003 error_memory: agregacion por estudiante de errores detectados.
-- Forward-only, aditiva: no toca tablas existentes. Sin backfill: la
-- memoria empieza con esta fase (los errores previos viven en
-- corrections.body_json y mastery_states.error_counts_json y no se
-- reinterpretan). Clave estable = CorrectionService.error_type.
CREATE TABLE IF NOT EXISTS error_memory(
  student_id TEXT NOT NULL REFERENCES students(student_id),
  error_key TEXT NOT NULL,
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
  error_count INTEGER NOT NULL DEFAULT 0,
  severity TEXT NOT NULL DEFAULT '',
  last_status TEXT NOT NULL DEFAULT '',
  last_question_id TEXT NOT NULL DEFAULT '',
  last_attempt_id TEXT NOT NULL DEFAULT '',
  PRIMARY KEY(student_id, error_key));
CREATE INDEX IF NOT EXISTS idx_em_student_seen ON error_memory(student_id, last_seen);
