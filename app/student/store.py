"""Student store: data/student/student.sqlite. Solo rendimiento.

Tablas: students, attempts (UNIQUE attempt_id), corrections (attempt+version),
mastery_states, mastery_events (inmutables, UNIQUE event_id), memories,
reviews, audit_log. FK + constraints (§143-144). Transacciones atomicas.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS students(
  student_id TEXT PRIMARY KEY, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS attempts(
  attempt_id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(student_id),
  question_id TEXT NOT NULL, question_version TEXT NOT NULL, exam_id TEXT NOT NULL DEFAULT '',
  answer TEXT NOT NULL, seed TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS corrections(
  correction_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
  question_id TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
  reason TEXT NOT NULL DEFAULT '', reviewer TEXT NOT NULL DEFAULT '',
  body_json TEXT NOT NULL, created_at TEXT NOT NULL,
  UNIQUE(attempt_id, version));
CREATE TABLE IF NOT EXISTS mastery_states(
  mastery_id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(student_id),
  knowledge_unit_id TEXT NOT NULL, unit_kind TEXT NOT NULL,
  score REAL NOT NULL, confidence REAL NOT NULL, attempt_count INTEGER NOT NULL,
  correct_count INTEGER NOT NULL, incorrect_count INTEGER NOT NULL,
  last_attempt TEXT NOT NULL DEFAULT '', last_correct TEXT NOT NULL DEFAULT '',
  error_counts_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'UNKNOWN',
  policy_version TEXT NOT NULL,
  UNIQUE(student_id, knowledge_unit_id));
CREATE TABLE IF NOT EXISTS mastery_events(
  event_id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(student_id),
  question_id TEXT NOT NULL, attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
  correction_id TEXT NOT NULL, knowledge_unit_id TEXT NOT NULL, unit_kind TEXT NOT NULL,
  old_score REAL NOT NULL, new_score REAL NOT NULL,
  old_confidence REAL NOT NULL, new_confidence REAL NOT NULL,
  reason TEXT NOT NULL, evidence_json TEXT NOT NULL, policy_version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(event_id));
CREATE TABLE IF NOT EXISTS memories(
  memory_id TEXT PRIMARY KEY, student_id TEXT NOT NULL REFERENCES students(student_id),
  kind TEXT NOT NULL, text TEXT NOT NULL, confidence REAL NOT NULL,
  evidence_count INTEGER NOT NULL, last_evidence TEXT NOT NULL,
  attempt_ids_json TEXT NOT NULL, correction_ids_json TEXT NOT NULL,
  created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reviews(
  review_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id),
  reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING',
  created_at TEXT NOT NULL, resolved_at TEXT NOT NULL DEFAULT '',
  reviewer TEXT NOT NULL DEFAULT '', resolution TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS audit_log(
  seq INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, ref_id TEXT NOT NULL,
  detail TEXT NOT NULL, created_at TEXT NOT NULL);
"""


class StudentStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path)
        try:
            con.executescript("PRAGMA foreign_keys=ON;" + SCHEMA)
            from app.migrate import migrate as _migrate
            _migrate(con, "student")
            con.commit()
        finally:
            con.close()

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=30.0)
        con.execute("PRAGMA foreign_keys=ON")
        return con
