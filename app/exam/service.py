"""ExamSessionService (Fase 7 Bloque 2): nucleo persistente de sesion de examen.

Flujo: store_blueprint -> prepare_exam (seleccion+snapshot, exam READY)
-> create_session (CREATED) -> prepare_session (session READY, snapshot
re-verificado) -> start_session (IN_PROGRESS, reloj aqui) ->
get_question/save_answer (solo IN_PROGRESS, vistas STEM) ->
submit_session (SUBMITTED, idempotente) | expiry/cancel.

Sin grading (GRADED reservado), sin adaptive, sin LLM, sin correccion
en este bloque (save != correction != mastery, §34). Reloj inyectable
para determinismo. Una conexion por operacion = atomicidad (§36).
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from app.correction.models import GRADER_VERSION, RUBRIC_VERSION
from app.examiner.exam import assemble_exam
from app.examiner.models import EXAMINER_VERSION
from app.student.policy import MASTERY_POLICY

from .models import (
    EXAM_SPEC_VERSION,
    ExamAnswer,
    ExamBlueprint,
    ExamError,
    ExamQuestionInstance,
    ExamSession,
    SnapshotInvalid,
    stem_view,
    transition,
)
from .store import ExamStore

RETRIEVAL_VERSION = "retrieval-2.0"
REASONING_VERSION = "reasoning-3.0"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _sha12(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def _body_sha(body_json: str) -> str:
    return hashlib.sha256(body_json.encode("utf-8")).hexdigest()


class ExamSessionService:
    def __init__(self, student_db: str | Path, questions_db: str | Path,
                 kb_path: str | Path, clock=None) -> None:
        self.exams = ExamStore(student_db)
        self.questions_db = str(questions_db)
        self.kb_path = str(kb_path)
        self._clock = clock or _now

    def _t(self, now: str) -> str:
        return now or self._clock()

    # ---------- lectura cruda ----------
    def _qstore(self):
        return SimpleNamespace(path=self.questions_db)

    def _question_row(self, question_id: str) -> dict:
        con = sqlite3.connect("file:%s?mode=ro" % self.questions_db, uri=True)
        try:
            row = con.execute("SELECT fingerprint, body_json FROM questions "
                              "WHERE question_id=?", (question_id,)).fetchone()
        finally:
            con.close()
        if not row:
            raise ExamError("pregunta inexistente: %r" % question_id)
        body = json.loads(row[1])
        return {"fingerprint": row[0], "body_json": row[1], "body": body}

    def _kb_formula_exists(self, fid: str) -> bool:
        con = sqlite3.connect("file:%s?mode=ro" % self.kb_path, uri=True)
        try:
            return bool(con.execute("SELECT 1 FROM formulas WHERE "
                                    "equation_id=?", (fid,)).fetchone())
        finally:
            con.close()

    def _kb_pipeline(self) -> str:
        con = sqlite3.connect("file:%s?mode=ro" % self.kb_path, uri=True)
        try:
            row = con.execute("SELECT value FROM meta WHERE key="
                              "'pipeline_version'").fetchone()
        finally:
            con.close()
        return row[0] if row else ""

    def _manifest_sha(self) -> str:
        mp = Path(self.kb_path).parent.parent / "source_manifest.json"
        if not mp.is_file():
            raise ExamError("source_manifest.json ausente: %s" % mp)
        import hashlib as _hl
        return _hl.sha256(mp.read_bytes()).hexdigest()

    # ---------- blueprint ----------
    def store_blueprint(self, spec: dict) -> dict:
        bp = ExamBlueprint.from_dict(spec)
        errs = bp.validate()
        if errs:
            raise ExamError("blueprint invalido: %s" % "; ".join(errs))
        exam_id = bp.exam_id()
        con = self.exams.connect()
        try:
            con.execute(
                "INSERT OR IGNORE INTO exam_specs(exam_id,title,version,kind,"
                "blueprint_json,seed,duration_seconds,question_count,"
                "topics_json,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (exam_id, bp.title, bp.version, bp.exam_kind, bp.canonical(),
                 bp.seed, bp.duration_seconds, bp.question_count,
                 json.dumps(list(bp.topics)), "DRAFT", self._clock()))
            con.commit()
            created = con.total_changes > 0
        finally:
            con.close()
        return {"exam_id": exam_id, "created": created, "status": "DRAFT"}

    def _load_spec(self, con, exam_id: str) -> dict:
        row = con.execute("SELECT title, version, kind, blueprint_json, seed,"
                          " duration_seconds, question_count, topics_json, status,"
                          " quality_json, versions_json, kb_pipeline, manifest_sha,"
                          " created_at FROM exam_specs WHERE exam_id=?",
                          (exam_id,)).fetchone()
        if not row:
            raise ExamError("examen inexistente: %r" % exam_id)
        keys = ("title", "version", "kind", "blueprint_json", "seed",
                "duration_seconds", "question_count", "topics_json", "status",
                "quality_json", "versions_json", "kb_pipeline",
                "manifest_sha", "created_at")
        return dict(zip(keys, row))

    # ---------- preparacion ----------
    def prepare_exam(self, exam_id: str) -> dict:
        con = self.exams.connect()
        try:
            spec = self._load_spec(con, exam_id)
            if spec["status"] == "READY":
                return self._exam_summary(con, exam_id)
            bp = ExamBlueprint.from_dict(json.loads(spec["blueprint_json"]))
            for fid in bp.required_formula_ids:
                if not self._kb_formula_exists(fid):
                    raise ExamError("EXAM NOT READY: formula inexistente %r"
                                    % fid)
            asm = assemble_exam(
                self._qstore(), topics=list(bp.topics),
                question_count=bp.question_count,
                types=dict(bp.types) or None,
                difficulty=dict(bp.difficulty) or None, seed=bp.seed,
                kb_version=self._kb_pipeline(),
                sections=dict(bp.sections) or None,
                formula_ids=list(bp.required_formula_ids) or None,
                concept_terms=[c["term"] for c in bp.concept_requirements]
                or None,
                order=bp.ordering_policy)
            gate = self._quality_gate(bp, asm)
            if gate:
                raise ExamError("EXAM NOT READY: %s" % "; ".join(gate))
            pts = self._points_for(bp, asm["question_ids"])
            con.execute("DELETE FROM exam_questions WHERE exam_id=?",
                        (exam_id,))
            for pos, qid in enumerate(asm["question_ids"]):
                q = self._question_row(qid)
                body = q["body"]
                con.execute(
                    "INSERT INTO exam_questions(exam_id,position,question_id,"
                    "question_version,fingerprint,body_sha,points,required,"
                    "slot_json) VALUES(?,?,?,?,?,?,?,?,?)",
                    (exam_id, pos, qid, body.get("version", ""),
                     q["fingerprint"], _body_sha(q["body_json"]),
                     pts[qid][0], 1 if pts[qid][1] else 0,
                     json.dumps({"type": body.get("type", ""),
                                 "difficulty": body.get("difficulty", "")},
                                sort_keys=True)))
            versions = {"exam_spec": EXAM_SPEC_VERSION,
                        "examiner": EXAMINER_VERSION,
                        "knowledge": self._kb_pipeline(),
                        "manifest_sha": self._manifest_sha(),
                        "retrieval": RETRIEVAL_VERSION,
                        "reasoning": REASONING_VERSION,
                        "grader": GRADER_VERSION, "rubric": RUBRIC_VERSION,
                        "mastery": MASTERY_POLICY.key()}
            quality = {"shortfall": asm["coverage"].get("shortfall", 0),
                        "topics": asm["coverage"].get("topics", []),
                        "formulas_covered": asm["coverage"].get(
                            "formulas_covered", []),
                        "concepts_covered": asm["coverage"].get(
                            "concepts_covered", []),
                        "checks": "quality_gate_ok"}
            con.execute("UPDATE exam_specs SET status='READY',"
                        " quality_json=?, versions_json=?, kb_pipeline=?,"
                        " manifest_sha=? WHERE exam_id=?",
                        (json.dumps(quality, sort_keys=True),
                         json.dumps(versions, sort_keys=True),
                         versions["knowledge"], versions["manifest_sha"],
                         exam_id))
            con.commit()
            return self._exam_summary(con, exam_id)
        finally:
            con.close()

    def _points_for(self, bp: ExamBlueprint, qids: list[str]) -> dict:
        sc = bp.scoring
        default = float(sc.get("default_points", 1.0))
        req_default = bool(sc.get("required_default", True))
        by_type = sc.get("points_by_type", {}) or {}
        out = {}
        con = sqlite3.connect("file:%s?mode=ro" % self.questions_db, uri=True)
        try:
            for qid in qids:
                row = con.execute("SELECT type FROM questions WHERE "
                                  "question_id=?", (qid,)).fetchone()
                qtype = row[0] if row else ""
                out[qid] = (float(by_type.get(qtype, default)), req_default)
        finally:
            con.close()
        return out

    def _quality_gate(self, bp: ExamBlueprint, asm: dict) -> list[str]:
        errs = []
        qids = asm["question_ids"]
        if asm["coverage"].get("shortfall", 0):
            errs.append("shortfall %d" % asm["coverage"]["shortfall"])
        if len(set(qids)) != len(qids):
            errs.append("duplicados en seleccion")
        con = sqlite3.connect("file:%s?mode=ro" % self.questions_db, uri=True)
        try:
            bodies = {}
            for qid in qids:
                row = con.execute("SELECT body_json FROM questions WHERE "
                                  "question_id=?", (qid,)).fetchone()
                if not row:
                    errs.append("qid fantasma: %r" % qid)
                    continue
                bodies[qid] = json.loads(row[0])
        finally:
            con.close()
        if errs:
            return errs
        if set(b.get("topic") for b in bodies.values()) != set(bp.topics):
            errs.append("cobertura topics %r != %r"
                        % (sorted({b.get("topic") for b in bodies.values()}),
                           sorted(bp.topics)))
        if bp.types and any(b.get("type") not in bp.types for b in
                            bodies.values()):
            errs.append("tipos fuera de cuota")
        if bp.difficulty and any(b.get("difficulty") not in bp.difficulty
                                 for b in bodies.values()):
            errs.append("dificultad fuera de distribucion")
        have_f, have_c = set(), set()
        for b in bodies.values():
            have_f.update(b.get("formula_ids", []) or [])
            have_c.update(b.get("concept_terms", []) or [])
            if not b.get("source_refs") or not b.get("evidence_refs"):
                errs.append("provenance incompleta: %r"
                            % b.get("question_id"))
        missing_f = [f for f in bp.required_formula_ids if f not in have_f]
        if missing_f:
            errs.append("formulas sin cubrir: %r" % missing_f)
        missing_c = [c["term"] for c in bp.concept_requirements
                     if c["term"] not in have_c]
        if missing_c:
            errs.append("conceptos sin cubrir: %r" % missing_c)
        fps = [b.get("fingerprint", "") for b in bodies.values()]
        if len(set(fps)) != len(fps):
            errs.append("fingerprints duplicados")
        return errs

    def _exam_summary(self, con, exam_id: str) -> dict:
        spec = self._load_spec(con, exam_id)
        rows = con.execute("SELECT position, question_id, points, required"
                           " FROM exam_questions WHERE exam_id=? ORDER BY "
                           "position", (exam_id,)).fetchall()
        return {"exam_id": exam_id, "status": spec["status"],
                "instances": [{"position": r[0], "question_id": r[1],
                               "points": r[2], "required": bool(r[3])}
                              for r in rows],
                "quality": json.loads(spec["quality_json"]),
                "versions": json.loads(spec["versions_json"])}

    # ---------- sesiones ----------
    def create_session(self, exam_id: str, student_id: str) -> dict:
        con = self.exams.connect()
        try:
            spec = self._load_spec(con, exam_id)
            if spec["status"] != "READY":
                raise ExamError("examen no READY: %r (%s)"
                                % (exam_id, spec["status"]))
            bp = json.loads(spec["blueprint_json"])
            seq = con.execute("SELECT COUNT(*) FROM exam_sessions WHERE "
                              "exam_id=? AND student_id=?",
                              (exam_id, student_id)).fetchone()[0] + 1
            sid = "exs-" + _sha12("%s|%s|%d|%d"
                                  % (exam_id, student_id, bp["seed"], seq))
            con.execute(
                "INSERT INTO exam_sessions(session_id,exam_id,student_id,"
                "exam_kind,status,seed,exam_version,policy_versions_json,"
                "duration_seconds,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (sid, exam_id, student_id, spec["kind"], "CREATED",
                 bp["seed"], bp["version"], spec["versions_json"],
                 bp.get("duration_seconds"), self._clock()))
            con.commit()
        finally:
            con.close()
        return {"session_id": sid, "status": "CREATED", "exam_id": exam_id,
                "student_id": student_id}

    def _load_session(self, con, session_id: str) -> dict:
        row = con.execute("SELECT session_id, exam_id, student_id, exam_kind,"
                          " status, seed, exam_version, policy_versions_json,"
                          " duration_seconds, started_at, submitted_at,"
                          " cancelled_at, expires_at, created_at"
                          " FROM exam_sessions WHERE session_id=?",
                          (session_id,)).fetchone()
        if not row:
            raise ExamError("sesion inexistente: %r" % session_id)
        keys = ("session_id", "exam_id", "student_id", "exam_kind", "status",
                "seed", "exam_version", "policy_versions", "duration_seconds",
                "started_at", "submitted_at", "cancelled_at", "expires_at",
                "created_at")
        d = dict(zip(keys, row))
        d["policy_versions"] = json.loads(d["policy_versions"])
        return d

    @staticmethod
    def _check_student(sess: dict, student_id: str) -> None:
        if sess["student_id"] != student_id:
            raise ExamError("sesion de otro estudiante")

    def _snapshot_ok(self, con, session_id: str) -> bool:
        rows = con.execute("SELECT question_id, fingerprint, body_sha FROM "
                           "session_questions WHERE session_id=? ORDER BY "
                           "position", (session_id,)).fetchall()
        if not rows:
            return False
        for qid, fp, sha in rows:
            try:
                q = self._question_row(qid)
            except ExamError:
                return False
            if q["fingerprint"] != fp or _body_sha(q["body_json"]) != sha:
                return False
        return True

    def prepare_session(self, session_id: str, student_id: str) -> dict:
        con = self.exams.connect()
        try:
            sess = self._load_session(con, session_id)
            self._check_student(sess, student_id)
            if sess["status"] == "READY":
                n = con.execute("SELECT COUNT(*) FROM session_questions "
                                "WHERE session_id=?", (session_id,)).fetchone()[0]
                return {"session_id": session_id, "status": "READY",
                        "instances": n}
            transition(sess["status"], "READY")
            spec = self._load_spec(con, sess["exam_id"])
            if spec["status"] != "READY":
                raise ExamError("examen no READY")
            con.execute("DELETE FROM session_questions WHERE session_id=?",
                        (session_id,))
            grows = con.execute(
                "SELECT position, question_id, question_version, fingerprint,"
                " body_sha, points, required, slot_json FROM exam_questions "
                "WHERE exam_id=? ORDER BY position",
                (sess["exam_id"],)).fetchall()
            for pos, qid, qv, fp, sha, pts, req, slot in grows:
                con.execute(
                    "INSERT INTO session_questions(session_id,position,"
                    "question_id,question_version,fingerprint,body_sha,points,"
                    "required,slot_json) VALUES(?,?,?,?,?,?,?,?,?)",
                    (session_id, pos, qid, qv, fp, sha, pts, req, slot))
            if not self._snapshot_ok(con, session_id):
                raise SnapshotInvalid("SNAPSHOT_INVALID al preparar")
            con.execute("UPDATE exam_sessions SET status='READY' WHERE "
                        "session_id=?", (session_id,))
            con.commit()
            return {"session_id": session_id, "status": "READY",
                    "instances": len(grows)}
        finally:
            con.close()

    def start_session(self, session_id: str, student_id: str,
                      now: str = "") -> dict:
        t = self._t(now)
        con = self.exams.connect()
        try:
            sess = self._load_session(con, session_id)
            self._check_student(sess, student_id)
            transition(sess["status"], "IN_PROGRESS")
            if not self._snapshot_ok(con, session_id):
                raise SnapshotInvalid("SNAPSHOT_INVALID al iniciar")
            exp = ""
            if sess["duration_seconds"] is not None:
                exp = (_parse(t) + timedelta(
                    seconds=sess["duration_seconds"])).isoformat(
                        timespec="seconds")
            con.execute("UPDATE exam_sessions SET status='IN_PROGRESS',"
                        " started_at=?, expires_at=? WHERE session_id=?",
                        (t, exp, session_id))
            con.commit()
            return {"session_id": session_id, "status": "IN_PROGRESS",
                    "started_at": t, "expires_at": exp}
        finally:
            con.close()

    def check_expiry(self, session_id: str, now: str = "") -> bool:
        """Puro (solo lectura): True si debe expirar."""
        t = self._t(now)
        con = self.exams.connect()
        try:
            sess = self._load_session(con, session_id)
        finally:
            con.close()
        return bool(sess["status"] == "IN_PROGRESS" and sess["expires_at"]
                    and _parse(t) >= _parse(sess["expires_at"]))

    def _enforce_expiry(self, con, sess: dict, now: str) -> dict:
        if sess["status"] == "IN_PROGRESS" and sess["expires_at"] \
                and _parse(now) >= _parse(sess["expires_at"]):
            con.execute("UPDATE exam_sessions SET status='EXPIRED' WHERE "
                        "session_id=?", (sess["session_id"],))
            sess = dict(sess, status="EXPIRED")
        return sess

    # ---------- preguntas y respuestas ----------
    def _instance(self, con, session_id: str, position: int) -> dict:
        row = con.execute("SELECT question_id, question_version, fingerprint,"
                          " body_sha, points, required FROM session_questions "
                          "WHERE session_id=? AND position=?",
                          (session_id, position)).fetchone()
        if not row:
            raise ExamError("position inexistente o ajena: %r" % position)
        return {"question_id": row[0], "question_version": row[1],
                "fingerprint": row[2], "body_sha": row[3], "points": row[4],
                "required": bool(row[5])}

    def get_question(self, session_id: str, position: int, student_id: str,
                     now: str = "") -> dict:
        t = self._t(now)
        con = self.exams.connect()
        try:
            sess = self._load_session(con, session_id)
            self._check_student(sess, student_id)
            sess = self._enforce_expiry(con, sess, t)
            con.commit()
            if sess["status"] != "IN_PROGRESS":
                raise ExamError("pregunta solo disponible en IN_PROGRESS "
                                "(estado %s)" % sess["status"])
            inst = self._instance(con, session_id, position)
            q = self._question_row(inst["question_id"])
            if q["fingerprint"] != inst["fingerprint"] or \
                    _body_sha(q["body_json"]) != inst["body_sha"]:
                raise SnapshotInvalid("SNAPSHOT_INVALID al leer")
            return stem_view(q["body"], position=position,
                             question_version=inst["question_version"],
                             points=inst["points"], required=inst["required"],
                             session_id=session_id)
        finally:
            con.close()

    def save_answer(self, session_id: str, position: int, answer: str,
                    student_id: str, now: str = "") -> dict:
        if not isinstance(answer, str):
            raise ExamError("answer debe ser str")
        t = self._t(now)
        con = self.exams.connect()
        try:
            sess = self._load_session(con, session_id)
            self._check_student(sess, student_id)
            sess = self._enforce_expiry(con, sess, t)
            con.commit()
            if sess["status"] != "IN_PROGRESS":
                raise ExamError("no se admite respuesta en estado %s"
                                % sess["status"])
            inst = self._instance(con, session_id, position)
            row = con.execute("SELECT version FROM session_answers WHERE "
                              "session_id=? AND position=?",
                              (session_id, position)).fetchone()
            ver = (row[0] + 1) if row else 1
            con.execute("INSERT OR REPLACE INTO session_answers(session_id,"
                        "position,question_id,answer,saved_at,version)"
                        " VALUES(?,?,?,?,?,?)",
                        (session_id, position, inst["question_id"], answer,
                         t, ver))
            con.execute("INSERT INTO answer_log(session_id,position,"
                        "question_id,answer,saved_at,version)"
                        " VALUES(?,?,?,?,?,?)",
                        (session_id, position, inst["question_id"], answer,
                         t, ver))
            con.commit()
            return {"session_id": session_id, "position": position,
                    "question_id": inst["question_id"], "answer": answer,
                    "saved_at": t, "version": ver}
        finally:
            con.close()

    def get_answers(self, session_id: str, student_id: str) -> list[dict]:
        con = self.exams.connect()
        try:
            sess = self._load_session(con, session_id)
            self._check_student(sess, student_id)
            return [{"position": r[0], "question_id": r[1], "answer": r[2],
                     "saved_at": r[3], "version": r[4]}
                    for r in con.execute(
                        "SELECT position, question_id, answer, saved_at,"
                        " version FROM session_answers WHERE session_id=? "
                        "ORDER BY position", (session_id,)).fetchall()]
        finally:
            con.close()

    # ---------- submit / cancel ----------
    def submit_session(self, session_id: str, student_id: str,
                       now: str = "") -> dict:
        t = self._t(now)
        con = self.exams.connect()
        try:
            sess = self._load_session(con, session_id)
            self._check_student(sess, student_id)
            if sess["status"] == "SUBMITTED":
                return self._summary(con, sess)
            sess = self._enforce_expiry(con, sess, t)
            con.commit()
            transition(sess["status"], "SUBMITTED")
            con.execute("UPDATE exam_sessions SET status='SUBMITTED',"
                        " submitted_at=? WHERE session_id=?",
                        (t, session_id))
            con.commit()
            sess = dict(sess, status="SUBMITTED", submitted_at=t)
            return self._summary(con, sess)
        finally:
            con.close()

    def _summary(self, con, sess: dict) -> dict:
        answers = [{"position": r[0], "question_id": r[1], "answer": r[2],
                    "saved_at": r[3], "version": r[4]}
                   for r in con.execute(
                       "SELECT position, question_id, answer, saved_at,"
                       " version FROM session_answers WHERE session_id=? "
                       "ORDER BY position", (sess["session_id"],)).fetchall()]
        return {"session_id": sess["session_id"], "status": sess["status"],
                "submitted_at": sess["submitted_at"], "answers": answers,
                "answers_frozen": len(answers)}

    def cancel_session(self, session_id: str, student_id: str,
                       now: str = "") -> dict:
        t = self._t(now)
        con = self.exams.connect()
        try:
            sess = self._load_session(con, session_id)
            self._check_student(sess, student_id)
            transition(sess["status"], "CANCELLED")
            con.execute("UPDATE exam_sessions SET status='CANCELLED',"
                        " cancelled_at=? WHERE session_id=?",
                        (t, session_id))
            con.commit()
            return {"session_id": session_id, "status": "CANCELLED",
                    "cancelled_at": t}
        finally:
            con.close()

    # ---------- utilidades ----------
    def read_session(self, session_id: str, student_id: str) -> dict:
        """Sesion + instancias + respuestas (para grading y resultado)."""
        con = self.exams.connect()
        try:
            sess = self._load_session(con, session_id)
            self._check_student(sess, student_id)
            instances = [
                {"position": r[0], "question_id": r[1],
                 "question_version": r[2], "fingerprint": r[3],
                 "body_sha": r[4], "points": r[5],
                 "required": bool(r[6]), "slot": json.loads(r[7])}
                for r in con.execute(
                    "SELECT position, question_id, question_version,"
                    " fingerprint, body_sha, points, required, slot_json"
                    " FROM session_questions WHERE session_id=? ORDER BY"
                    " position", (session_id,)).fetchall()]
            answers = {r[0]: {"question_id": r[1], "answer": r[2],
                              "saved_at": r[3], "version": r[4]}
                       for r in con.execute(
                           "SELECT position, question_id, answer, saved_at,"
                           " version FROM session_answers WHERE session_id=?",
                           (session_id,)).fetchall()}
            return {"session": sess, "instances": instances,
                    "answers": answers}
        finally:
            con.close()

    def session_status(self, session_id: str) -> dict:
        con = self.exams.connect()
        try:
            s = self._load_session(con, session_id)
        finally:
            con.close()
        return {"session_id": s["session_id"], "status": s["status"],
                "started_at": s["started_at"],
                "submitted_at": s["submitted_at"],
                "expires_at": s["expires_at"]}

    def list_sessions(self, student_id: str) -> list[dict]:
        con = self.exams.connect()
        try:
            return [{"session_id": r[0], "exam_id": r[1], "status": r[2]}
                    for r in con.execute(
                        "SELECT session_id, exam_id, status FROM exam_sessions"
                        " WHERE student_id=? ORDER BY created_at, session_id",
                        (student_id,)).fetchall()]
        finally:
            con.close()
