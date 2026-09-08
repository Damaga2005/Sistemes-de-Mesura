"""ExamGradingService (Fase 7 Bloque 3): SUBMITTED/EXPIRED -> GRADED.

Autoridad unica de grading. Por pregunta (orden de posicion): respuesta
final -> attempt determinista de sesion -> StudentService.submit (F5:
correction + mastery, idempotente por attempt) -> ExamQuestionResult.
Agregacion entera (milesimas, HALF_UP) -> ExamResult. Mastery una unica
vez (la de F5; re-grade rejuega sin duplicar).

Sin corrector paralelo, sin LLM para la nota, sin tocar scoring F5 ni
mastery. Sesion -> GRADED solo si resultado COMPLETE; si INCOMPLETE
(revision pendiente) la sesion queda SUBMITTED con resultado inmutable.
"""
from __future__ import annotations

import json
from datetime import timezone
from decimal import Decimal, ROUND_HALF_UP

from app.correction.models import GRADER_VERSION, RUBRIC_VERSION
from app.student.policy import MASTERY_POLICY

from .models import (EXAM_POLICY_ID, EXAM_SPEC_VERSION, ExamError,
                   exam_attempt_id, transition)


def _now() -> str:
    from datetime import datetime
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _attempt_id(session_id: str, position: int, question_id: str,
                answer: str) -> str:
    return exam_attempt_id(session_id, position, question_id, answer)


def thou(points_available, correction_score) -> int:
    """Milesimas de punto ganadas, HALF_UP, aritmetica Decimal exacta."""
    v = (Decimal(str(correction_score)) * Decimal(str(points_available))
         * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(v)


def avail_thou(points_available) -> int:
    return int((Decimal(str(points_available)) * Decimal(1000)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP))


def pct_hundredths(earned_thou: int, total_thou: int) -> int:
    """Centésimas de porcentaje, HALF_UP entero. Total 0 -> 0 (sin NaN)."""
    if total_thou <= 0:
        return 0
    return (2 * earned_thou * 10000 + total_thou) // (2 * total_thou)


def fmt_thou(t: int) -> str:
    sign = "-" if t < 0 else ""
    t = abs(t)
    return "%s%d.%03d" % (sign, t // 1000, t % 1000)


def fmt_pct(h: int) -> str:
    sign = "-" if h < 0 else ""
    h = abs(h)
    return "%s%d.%02d" % (sign, h // 100, h % 100)


REVIEW_STATUSES = ("NEEDS_REVIEW", "UNGRADABLE")


class ExamGradingService:
    def __init__(self, exam_service, student_service, clock=None) -> None:
        self.exam = exam_service
        self.stu = student_service
        self._clock = clock or _now

    def _t(self, now: str) -> str:
        return now or self._clock()

    # ---------- grading ----------
    def grade(self, session_id: str, student_id: str,
              now: str = "") -> dict:
        """Idempotente: con resultado existente devuelve el almacenado."""
        t = self._t(now)
        con = self.exam.exams.connect()
        try:
            row = con.execute("SELECT status FROM exam_results WHERE "
                              "session_id=?", (session_id,)).fetchone()
            if row:
                return self._read_result(con, session_id, student_id)
        finally:
            con.close()
        data = self.exam.read_session(session_id, student_id)
        sess, instances, answers = (data["session"], data["instances"],
                                    data["answers"])
        if sess["status"] not in ("SUBMITTED", "EXPIRED"):
            raise ExamError("solo se califica SUBMITTED o EXPIRED "
                            "(estado %s)" % sess["status"])
        origin = sess["status"]
        try:
            for inst in instances:
                pos = inst["position"]
                ans = answers.get(pos, {}).get("answer", "")
                aid = _attempt_id(session_id, pos, inst["question_id"], ans)
                out = self.stu.submit(student_id, inst["question_id"], ans,
                                      attempt_id=aid, exam_id=sess["exam_id"],
                                      session_id=session_id)
                corr = out["correction"]
                self._store_question_result(
                    session_id, pos, sess["exam_id"], inst, ans, aid, corr, t)
            result = self._aggregate_and_store(session_id, t, origin,
                                               student_id)
        except Exception as e:  # noqa: BLE001
            self._cleanup_partial(session_id)
            if isinstance(e, ExamError):
                raise
            raise ExamError("GRADING_INCOMPLETE: %s: %s; sesion intacta en"
                            " %s, reintentable sin duplicar"
                            % (type(e).__name__, str(e)[:150], origin))
        return result

    def _cleanup_partial(self, session_id: str) -> None:
        """Borra filas de resultado parciales (la evidencia F5 real
        persiste: es correccion valida, deduplicada al reintentar).

        P0-1: NUNCA borra estado COMMITTED de otra ejecucion. Si ya
        existe resultado commiteado (o la sesion esta GRADED), el
        estado pertenece al ganador y se conserva intacto.
        """
        con = self.exam.exams.connect()
        try:
            win = con.execute("SELECT 1 FROM exam_results WHERE "
                              "session_id=?", (session_id,)).fetchone()
            if win:
                return
            st = con.execute("SELECT status FROM exam_sessions WHERE "
                             "session_id=?", (session_id,)).fetchone()
            if st and st[0] == "GRADED":
                return
            con.execute("DELETE FROM exam_question_results WHERE "
                        "session_id=?", (session_id,))
            con.execute("DELETE FROM exam_results WHERE session_id=?",
                        (session_id,))
            con.commit()
        finally:
            con.close()

    def _store_question_result(self, session_id: str, pos: int, exam_id: str,
                                 inst: dict, answer: str, attempt_id: str,
                                 corr: dict, graded_at: str) -> None:
        # P0-1: INSERT atomico (sin check-then-insert): duplicados
        # concurrentes benignos, entradas deterministas identicas.
        con = self.exam.exams.connect()
        try:
            earned = thou(inst["points"], corr["score"])
            con.execute(
                "INSERT OR IGNORE INTO exam_question_results(session_id,"
                "position,"
                "exam_id,question_id,question_version,fingerprint,"
                "points_avail_thou,points_earned_thou,correction_id,"
                "attempt_id,correction_status,blank,graded_at,versions_json)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (session_id, pos, exam_id, inst["question_id"],
                 inst["question_version"], inst["fingerprint"],
                 avail_thou(inst["points"]), earned,
                 corr["correction_id"], attempt_id, corr["status"],
                 1 if answer == "" else 0, graded_at,
                 json.dumps({"grader": GRADER_VERSION,
                             "rubric": corr.get("rubric_version",
                                                RUBRIC_VERSION),
                             "mastery": corr.get("mastery_policy_version",
                                                 MASTERY_POLICY.key())},
                            sort_keys=True)))
            con.commit()
        finally:
            con.close()

    def _aggregate_and_store(self, session_id: str, graded_at: str,
                               origin: str, student_id: str) -> dict:
        con = self.exam.exams.connect()
        try:
            # P0-1: claim serializado. El primero en commitear gana; el
            # resto adopta su resultado (equivalente) en vez de competir
            # y limpiar. Sobrevive a procesos separados (lock SQLite).
            con.execute("BEGIN IMMEDIATE")
            win = con.execute("SELECT 1 FROM exam_results WHERE "
                              "session_id=?", (session_id,)).fetchone()
            if win:
                result = self._read_result(con, session_id, student_id)
                con.commit()
                return result
            sess = self.exam._load_session(con, session_id)
            qrows = con.execute(
                "SELECT position, question_id, points_avail_thou,"
                " points_earned_thou, correction_id, attempt_id,"
                " correction_status, blank FROM exam_question_results WHERE"
                " session_id=? ORDER BY position", (session_id,)).fetchall()
            inst_n = con.execute("SELECT COUNT(*) FROM session_questions "
                                 "WHERE session_id=?",
                                 (session_id,)).fetchone()[0]
            if len(qrows) != inst_n:
                raise ExamError("NO-GO: %d resultados para %d instancias"
                                % (len(qrows), inst_n))
            req_t = req_e = opt_t = opt_e = 0
            counts = {"answered": 0, "blank": 0, "correct": 0,
                      "partial": 0, "incorrect": 0, "review": 0}
            for pos, qid, av, er, cid, aid, st, blank in qrows:
                req = self._instance_required(con, session_id, pos)
                if req:
                    req_t += av
                    req_e += er
                else:
                    opt_t += av
                    opt_e += er
                if blank:
                    counts["blank"] += 1
                else:
                    counts["answered"] += 1
                if st == "CORRECT":
                    counts["correct"] += 1
                elif st == "PARTIALLY_CORRECT":
                    counts["partial"] += 1
                elif st in REVIEW_STATUSES:
                    counts["review"] += 1
                else:
                    counts["incorrect"] += 1
            if req_t <= 0:
                raise ExamError("ABSTAIN: sin puntos required (sin regla"
                                " de opcionales)")
            pct = pct_hundredths(req_e, req_t)
            status = "COMPLETE" if counts["review"] == 0 else "INCOMPLETE"
            spec = self.exam._load_spec(con, sess["exam_id"])
            bp = json.loads(spec["blueprint_json"])
            pvers = dict(sess["policy_versions"])
            pvers["scoring"] = "exam-spec-v1"
            con.execute(
                "INSERT OR IGNORE INTO exam_results(session_id,exam_id,"
                "student_id,exam_kind,origin_status,status,total_req_thou,"
                "earned_req_thou,total_opt_thou,earned_opt_thou,"
                "percentage_hund,question_count,answered_count,blank_count,"
                "correct_count,partial_count,incorrect_count,review_count,"
                "graded_at,scoring_json,versions_json)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (session_id, sess["exam_id"], sess["student_id"],
                 sess["exam_kind"], origin, status, req_t, req_e, opt_t,
                 opt_e, pct, len(qrows), counts["answered"], counts["blank"],
                 counts["correct"], counts["partial"], counts["incorrect"],
                 counts["review"], graded_at,
                 json.dumps(bp.get("scoring", {}), sort_keys=True),
                 json.dumps(pvers, sort_keys=True)))
            if status == "COMPLETE":
                transition(sess["status"], "GRADED")
                con.execute("UPDATE exam_sessions SET status='GRADED' WHERE "
                            "session_id=?", (session_id,))
            con.commit()
            return self._read_result(con, session_id, sess["student_id"])
        finally:
            con.close()

    @staticmethod
    def _instance_required(con, session_id: str, position: int) -> bool:
        row = con.execute("SELECT required FROM session_questions WHERE "
                          "session_id=? AND position=?",
                          (session_id, position)).fetchone()
        return bool(row and row[0])

    # ---------- lectura ----------
    def _read_result(self, con, session_id: str, student_id: str) -> dict:
        row = con.execute(
            "SELECT exam_id, student_id, exam_kind, origin_status, status,"
            " total_req_thou, earned_req_thou, total_opt_thou,"
            " earned_opt_thou, percentage_hund, question_count,"
            " answered_count, blank_count, correct_count, partial_count,"
            " incorrect_count, review_count, graded_at, scoring_json,"
            " versions_json FROM exam_results WHERE session_id=?",
            (session_id,)).fetchone()
        if not row:
            raise ExamError("RESULT_NOT_AVAILABLE")
        if row[1] != student_id:
            raise ExamError("resultado de otro estudiante")
        (exam_id, _, kind, origin, status, req_t, req_e, opt_t, opt_e, pct,
         n, ans, blank, ok, part, bad, rev, graded_at, scoring,
         versions) = row
        spec = con.execute("SELECT title, version FROM exam_specs WHERE "
                           "exam_id=?", (exam_id,)).fetchone()
        title, exam_version = (spec[0], spec[1]) if spec else ("", "")
        sess = con.execute("SELECT started_at, submitted_at FROM "
                           "exam_sessions WHERE session_id=?",
                           (session_id,)).fetchone()
        started_at, submitted_at = (sess[0], sess[1]) if sess else ("", "")
        qs = [{"position": r[0], "question_id": r[1],
               "question_version": r[2], "points_available": fmt_thou(r[3]),
               "points_earned": fmt_thou(r[4]), "status": r[7],
               "blank": bool(r[8]), "correction_id": r[5],
               "attempt_id": r[6], "graded_at": r[9]}
              for r in con.execute(
                  "SELECT position, question_id, question_version,"
                  " points_avail_thou, points_earned_thou, correction_id,"
                  " attempt_id, correction_status, blank, graded_at FROM"
                  " exam_question_results WHERE session_id=? ORDER BY"
                  " position", (session_id,)).fetchall()]
        return {"session_id": session_id, "exam_id": exam_id,
                "title": title, "exam_version": exam_version,
                "student_id": row[1], "exam_kind": kind,
                "origin_status": origin, "status": status,
                "started_at": started_at, "submitted_at": submitted_at,
                "total_points": fmt_thou(req_t),
                "earned_points": fmt_thou(req_e),
                "optional_points": fmt_thou(opt_t),
                "optional_earned": fmt_thou(opt_e),
                "percentage": fmt_pct(pct),
                "question_count": n, "answered_count": ans,
                "blank_count": blank, "correct_count": ok,
                "partial_count": part, "incorrect_count": bad,
                "review_count": rev, "graded_at": graded_at,
                "scoring_policy_id": EXAM_POLICY_ID,
                "scoring_policy_version": EXAM_SPEC_VERSION,
                "scoring": json.loads(scoring),
                "policy_versions": json.loads(versions), "questions": qs}

    def get_result(self, session_id: str, student_id: str) -> dict:
        con = self.exam.exams.connect()
        try:
            sess = self.exam._load_session(con, session_id)
            if sess["student_id"] != student_id:
                raise ExamError("resultado de otro estudiante")
            if sess["status"] not in ("SUBMITTED", "GRADED"):
                raise ExamError("RESULT_NOT_AVAILABLE (estado %s)"
                                % sess["status"])
            return self._read_result(con, session_id, student_id)
        finally:
            con.close()

    def get_question_result(self, session_id: str, position: int,
                            student_id: str) -> dict:
        res = self.get_result(session_id, student_id)
        for q in res["questions"]:
            if q["position"] == position:
                return {"session_id": session_id, **q}
        raise ExamError("position inexistente o ajena: %r" % position)
