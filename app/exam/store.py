"""Tablas Exam Mode en la student DB canonica (data/student/student.sqlite).

Migracion estrictamente aditiva: CREATE TABLE IF NOT EXISTS, sin tocar
ni mover filas existentes, sin tercera DB (§3). El legado
data/processed/students.sqlite no se referencia aqui.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

# DB canonica de estudiante (constante documental; el codigo recibe paths).
CANONICAL_STUDENT_DB = "data/student/student.sqlite"

EXAM_SCHEMA = """
CREATE TABLE IF NOT EXISTS exam_specs(
  exam_id TEXT PRIMARY KEY, title TEXT NOT NULL, version TEXT NOT NULL,
  kind TEXT NOT NULL, blueprint_json TEXT NOT NULL, seed INTEGER NOT NULL,
  duration_seconds INTEGER, question_count INTEGER NOT NULL,
  topics_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'DRAFT',
  quality_json TEXT NOT NULL DEFAULT '{}', versions_json TEXT NOT NULL DEFAULT '{}',
  kb_pipeline TEXT NOT NULL DEFAULT '', manifest_sha TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS exam_questions(
  exam_id TEXT NOT NULL, position INTEGER NOT NULL,
  question_id TEXT NOT NULL, question_version TEXT NOT NULL,
  fingerprint TEXT NOT NULL, body_sha TEXT NOT NULL,
  points REAL NOT NULL, required INTEGER NOT NULL,
  slot_json TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY(exam_id, position));
CREATE TABLE IF NOT EXISTS exam_sessions(
  session_id TEXT PRIMARY KEY, exam_id TEXT NOT NULL, student_id TEXT NOT NULL,
  exam_kind TEXT NOT NULL, status TEXT NOT NULL, seed INTEGER NOT NULL,
  exam_version TEXT NOT NULL, policy_versions_json TEXT NOT NULL,
  duration_seconds INTEGER, started_at TEXT NOT NULL DEFAULT '',
  submitted_at TEXT NOT NULL DEFAULT '', cancelled_at TEXT NOT NULL DEFAULT '',
  expires_at TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_exam_sessions_student ON exam_sessions(student_id);
CREATE TABLE IF NOT EXISTS session_questions(
  session_id TEXT NOT NULL, position INTEGER NOT NULL,
  question_id TEXT NOT NULL, question_version TEXT NOT NULL,
  fingerprint TEXT NOT NULL, body_sha TEXT NOT NULL,
  points REAL NOT NULL, required INTEGER NOT NULL,
  slot_json TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY(session_id, position));
CREATE TABLE IF NOT EXISTS session_answers(
  session_id TEXT NOT NULL, position INTEGER NOT NULL,
  question_id TEXT NOT NULL, answer TEXT NOT NULL,
  saved_at TEXT NOT NULL, version INTEGER NOT NULL,
  PRIMARY KEY(session_id, position));
CREATE TABLE IF NOT EXISTS answer_log(
  seq INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
  position INTEGER NOT NULL, question_id TEXT NOT NULL,
  answer TEXT NOT NULL, saved_at TEXT NOT NULL, version INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_answer_log_session ON answer_log(session_id, position);
CREATE TABLE IF NOT EXISTS exam_question_results(
  session_id TEXT NOT NULL, position INTEGER NOT NULL, exam_id TEXT NOT NULL,
  question_id TEXT NOT NULL, question_version TEXT NOT NULL,
  fingerprint TEXT NOT NULL, points_avail_thou INTEGER NOT NULL,
  points_earned_thou INTEGER NOT NULL, correction_id TEXT NOT NULL,
  attempt_id TEXT NOT NULL, correction_status TEXT NOT NULL,
  blank INTEGER NOT NULL, graded_at TEXT NOT NULL,
  versions_json TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY(session_id, position));
CREATE TABLE IF NOT EXISTS exam_results(
  session_id TEXT PRIMARY KEY, exam_id TEXT NOT NULL, student_id TEXT NOT NULL,
  exam_kind TEXT NOT NULL, origin_status TEXT NOT NULL,
  status TEXT NOT NULL, total_req_thou INTEGER NOT NULL,
  earned_req_thou INTEGER NOT NULL, total_opt_thou INTEGER NOT NULL,
  earned_opt_thou INTEGER NOT NULL, percentage_hund INTEGER NOT NULL,
  question_count INTEGER NOT NULL, answered_count INTEGER NOT NULL,
  blank_count INTEGER NOT NULL, correct_count INTEGER NOT NULL,
  partial_count INTEGER NOT NULL, incorrect_count INTEGER NOT NULL,
  review_count INTEGER NOT NULL, graded_at TEXT NOT NULL,
  scoring_json TEXT NOT NULL DEFAULT '{}', versions_json TEXT NOT NULL DEFAULT '{}');
"""


class ExamStore:
    """Solo tablas exam_* sobre la student DB. Jamas toca mastery/attempts."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path)
        try:
            con.executescript(EXAM_SCHEMA)
            from app.migrate import migrate as _migrate
            _migrate(con, "exam_sessions")
            con.commit()
        finally:
            con.close()

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=30.0)
        con.execute("PRAGMA foreign_keys=ON")
        return con
