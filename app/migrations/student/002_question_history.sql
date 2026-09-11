-- 002 question_history: memoria por estudiante de preguntas vistas.
-- Forward-only, aditiva: no toca tablas existentes. Sin backfill: el
-- historial anterior vive en attempts/corrections y no se reinterpreta;
-- el registro empieza con esta fase. question_history queda cubierta
-- por el esquema del store (CREATE TABLE IF NOT EXISTS idempotente).
CREATE TABLE IF NOT EXISTS question_history(
  student_id TEXT NOT NULL REFERENCES students(student_id),
  question_id TEXT NOT NULL,
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  last_status TEXT NOT NULL DEFAULT '',
  last_score REAL NOT NULL DEFAULT 0.0,
  last_attempt_id TEXT NOT NULL DEFAULT '',
  PRIMARY KEY(student_id, question_id));
CREATE INDEX IF NOT EXISTS idx_qh_student_seen ON question_history(student_id, last_seen);
