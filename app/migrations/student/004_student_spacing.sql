-- 004 student_spacing: memoria persistente de revision por estudiante
-- y unidad (Fase 10). Forward-only, aditiva: no toca tablas existentes.
-- Sin backfill: empieza con los nuevos submits (el historial previo vive
-- en mastery_states/mastery_events y no se reinterpreta).
CREATE TABLE IF NOT EXISTS student_spacing(
  student_id TEXT NOT NULL REFERENCES students(student_id),
  unit_kind TEXT NOT NULL, unit_id TEXT NOT NULL,
  first_review TEXT NOT NULL, last_review TEXT NOT NULL,
  next_review TEXT NOT NULL,
  review_count INTEGER NOT NULL DEFAULT 0,
  interval_days INTEGER NOT NULL DEFAULT 1,
  last_status TEXT NOT NULL DEFAULT '',
  last_score REAL NOT NULL DEFAULT 0.0,
  last_attempt_id TEXT NOT NULL DEFAULT '',
  PRIMARY KEY(student_id, unit_kind, unit_id));
CREATE INDEX IF NOT EXISTS idx_ss_student_next ON student_spacing(student_id, next_review);
