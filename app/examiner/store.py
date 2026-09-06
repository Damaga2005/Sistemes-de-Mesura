"""Question Store separado (§42): data/generated/questions.sqlite.

Jamas knowledge.sqlite / chunks.jsonl / evaluation DB. Fingerprint estable §35.
Tablas: questions (JSON canonico + columnas de cobertura), exams.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS questions(
  question_id TEXT PRIMARY KEY,
  fingerprint TEXT NOT NULL,
  topic INTEGER NOT NULL,
  section TEXT NOT NULL,
  type TEXT NOT NULL,
  difficulty TEXT NOT NULL,
  status TEXT NOT NULL,
  prompt TEXT NOT NULL,
  body_json TEXT NOT NULL,
  seed INTEGER NOT NULL,
  generator_version TEXT NOT NULL,
  prompt_version TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_q_topic ON questions(topic);
CREATE INDEX IF NOT EXISTS idx_q_status ON questions(status);
CREATE INDEX IF NOT EXISTS idx_q_fp ON questions(fingerprint);
CREATE TABLE IF NOT EXISTS exams(
  exam_id TEXT PRIMARY KEY,
  seed INTEGER NOT NULL,
  blueprint_json TEXT NOT NULL,
  question_ids TEXT NOT NULL,
  versions_json TEXT NOT NULL
);
"""


class QuestionStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path)
        try:
            con.executescript(SCHEMA)
            con.commit()
            self._migrate(con)
            con.commit()
        finally:
            con.close()

    @staticmethod
    def _migrate(con) -> None:
        """Migraciones idempotentes Fase 6 (solo metadatos de procedencia)."""
        qcols = {r[1] for r in con.execute("PRAGMA table_info(questions)").fetchall()}
        if "origin" not in qcols:
            con.execute("ALTER TABLE questions ADD COLUMN origin TEXT NOT NULL DEFAULT 'GENERATED'")
        ecols = {r[1] for r in con.execute("PRAGMA table_info(exams)").fetchall()}
        if "kind" not in ecols:
            con.execute("ALTER TABLE exams ADD COLUMN kind TEXT NOT NULL DEFAULT 'GENERATED'")
        if "source" not in ecols:
            con.execute("ALTER TABLE exams ADD COLUMN source TEXT NOT NULL DEFAULT ''")

    def put(self, q) -> bool:
        """Inserta si el fingerprint no existe. Devuelve True si es nueva."""
        con = sqlite3.connect(self.path)
        try:
            if con.execute("SELECT 1 FROM questions WHERE fingerprint=?",
                           (q.fingerprint,)).fetchone():
                return False
            con.execute(
                "INSERT INTO questions(question_id,fingerprint,topic,section,type,"
                "difficulty,status,prompt,body_json,seed,generator_version,prompt_version,"
                "origin)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (q.question_id, q.fingerprint, q.topic, q.section, q.type,
                 q.difficulty, q.validation.status, q.prompt,
                 json.dumps(q.to_dict(), ensure_ascii=False, sort_keys=True),
                 q.seed, q.generator_version, q.prompt_version,
                 getattr(q, "origin", "GENERATED")))
            con.commit()
            return True
        finally:
            con.close()

    def count(self, where: str = "", params: tuple = ()) -> int:
        con = sqlite3.connect("file:%s?mode=ro" % self.path, uri=True)
        try:
            return con.execute("SELECT COUNT(*) FROM questions" + (" WHERE " + where if where else ""),
                               params).fetchone()[0]
        finally:
            con.close()

    def put_exam(self, exam_id: str, seed: int, blueprint: dict, qids: list[str],
                 versions: dict, kind: str = "GENERATED", source: str = "") -> None:
        if kind not in ("GENERATED", "REAL_EXAM"):
            raise ValueError("exam kind no válido: %r" % kind)
        con = sqlite3.connect(self.path)
        try:
            con.execute("INSERT OR REPLACE INTO exams(exam_id,seed,blueprint_json,"
                        "question_ids,versions_json,kind,source) VALUES(?,?,?,?,?,?,?)",
                        (exam_id, seed, json.dumps(blueprint, ensure_ascii=False, sort_keys=True),
                         json.dumps(qids), json.dumps(versions, ensure_ascii=False, sort_keys=True),
                         kind, source))
            con.commit()
        finally:
            con.close()

    def get_exam(self, exam_id: str) -> dict | None:
        con = sqlite3.connect("file:%s?mode=ro" % self.path, uri=True)
        try:
            row = con.execute("SELECT seed, blueprint_json, question_ids, versions_json,"
                              "kind, source FROM exams WHERE exam_id=?", (exam_id,)).fetchone()
            if not row:
                return None
            return {"exam_id": exam_id, "seed": row[0],
                    "blueprint": json.loads(row[1]), "question_ids": json.loads(row[2]),
                    "versions": json.loads(row[3]), "kind": row[4], "source": row[5]}
        finally:
            con.close()
