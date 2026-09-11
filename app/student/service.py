"""StudentService (§107-108, §67, §114-115): correction -> mastery atomicos.

Transaccion: attempt + correction + mastery events + state en un commit;
rollback ante fallo. Mismo attempt_id -> mismo resultado (idempotencia §68).
APIs: mastery por unidad/topic/formula, error profile, intentos, memoria.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone

from app.correction import errors as ERR
from app.correction.models import Correction
from app.correction.service import CorrectionService
from app.examiner.store import QuestionStore

from . import mastery as MAS
from . import memory as MEM
from . import policy
from .models import Attempt
from .store import StudentStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _qid(version: str, *parts: str) -> str:
    return version + "-" + hashlib.sha256("|".join(parts).encode()).hexdigest()[:12]


class StudentService:
    def __init__(self, kb_path: str, questions_db: str, student_db: str) -> None:
        self.kb_path = kb_path
        self.correction = CorrectionService(kb_path, questions_db)
        self.questions = QuestionStore(questions_db)
        self.store = StudentStore(student_db)

    # ---------- intento + correccion + mastery (atomico) ----------
    def submit(self, student_id: str, question_id: str, answer: str, *,
               attempt_id: str = "", exam_id: str = "",
               session_id: str = "") -> dict:
        """Devuelve {attempt, correction, mastery_updates, memories}."""
        from app.correction.service import _norm_text
        attempt_id = attempt_id or "att-" + hashlib.sha256(
            ("%s|%s|%s" % (student_id, question_id,
                            _norm_text(answer))).encode()).hexdigest()[:12]
        con = self.store.connect()
        try:
            con.execute("INSERT OR IGNORE INTO students(student_id, created_at) VALUES(?,?)",
                        (student_id, _now()))
            row = con.execute("SELECT body_json FROM corrections WHERE attempt_id=? "
                              "ORDER BY version DESC LIMIT 1", (attempt_id,)).fetchone()
            if row:
                stored = json.loads(row[0])
                return {"attempt_id": attempt_id, "replayed": True,
                        "correction": stored,
                        "mastery_updates": [], "memories": []}
            qrow = self._question_row(question_id)
            con.execute(
                "INSERT OR IGNORE INTO attempts(attempt_id,student_id,question_id,"
                "question_version,exam_id,answer,created_at) VALUES(?,?,?,?,?,?,?)",
                (attempt_id, student_id, question_id, qrow["version"], exam_id,
                 answer, _now()))
            corr = self.correction.correct(
                question_id, answer, student_id=student_id, attempt_id=attempt_id,
                exam_id=exam_id, session_id=session_id)
            self._persist_correction(con, corr, attempt_id, version=1, reason="initial")
            updates = self._update_mastery(con, student_id, question_id, attempt_id, corr)
            mems = self._refresh_memories(con, student_id)
            self._record_seen(con, student_id, question_id, attempt_id, corr)
            self._record_errors(con, student_id, question_id, attempt_id, corr)
            self._record_reviews(con, student_id, attempt_id, corr, updates)
            con.execute("INSERT INTO audit_log(action,ref_id,detail,created_at) VALUES(?,?,?,?)",
                        ("submit", attempt_id,
                         json.dumps({"correction": corr.correction_id,
                                     "units": len(updates)}, ensure_ascii=False), _now()))
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
        return {"attempt_id": attempt_id, "replayed": False,
                "correction": corr.to_dict(), "mastery_updates": updates,
                "memories": mems}

    def _question_row(self, question_id: str) -> dict:
        import sqlite3
        con = sqlite3.connect("file:%s?mode=ro" % self.questions.path, uri=True)
        try:
            row = con.execute("SELECT body_json FROM questions WHERE question_id=?",
                              (question_id,)).fetchone()
        finally:
            con.close()
        if not row:
            raise KeyError("question not found: %s" % question_id)
        return json.loads(row[0])

    def _persist_correction(self, con, corr: Correction, attempt_id: str, *,
                            version: int, reason: str, reviewer: str = "") -> None:
        con.execute(
            "INSERT INTO corrections(correction_id,attempt_id,question_id,version,"
            "reason,reviewer,body_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (corr.correction_id if version == 1 else corr.correction_id + "-v%d" % version,
             attempt_id, corr.question_id, version, reason, reviewer,
             json.dumps(corr.to_dict(), ensure_ascii=False, sort_keys=True), _now()))

    def _units_for(self, question: dict) -> list[tuple[str, str]]:
        """Unidades de mastery: formulas + conceptos + seccion + topic (trazables)."""
        units = [("formula", f) for f in question.get("formula_ids", [])]
        units += [("concept", c) for c in question.get("concept_terms", [])[:6]]
        if question.get("section"):
            units.append(("section", "T%02d:%s" % (question.get("topic", 0),
                                                   question["section"][:80])))
        units.append(("topic", "T%02d" % question.get("topic", 0)))
        seen, out = set(), []
        for u in units:
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out

    def _update_mastery(self, con, student_id: str, question_id: str,
                        attempt_id: str, corr: Correction) -> list[dict]:
        question = self._question_row(question_id)
        status = corr.status
        if status in ("CORRECT", "PARTIALLY_CORRECT", "INCORRECT"):
            signal = {"CORRECT": 1.0, "PARTIALLY_CORRECT": 0.5,
                      "INCORRECT": 0.0}[status]
            counted = "correct" if signal >= 0.5 else "incorrect"
        else:
            signal, counted = None, None
        roots = sorted({e.error_type for e in corr.detected_errors if e.root_cause})
        all_errors = sorted({e.error_type for e in corr.detected_errors})
        updates = []
        for kind, ref in self._units_for(question):
            uid = MAS.unit_id(kind, ref)
            prev = con.execute("SELECT score, confidence, attempt_count, correct_count,"
                               " incorrect_count, error_counts_json FROM mastery_states "
                               "WHERE student_id=? AND knowledge_unit_id=?",
                               (student_id, uid)).fetchone()
            prior = None
            if prev:
                from .models import MasteryState
                prior = MasteryState(mastery_id="", student_id=student_id,
                                     knowledge_unit_id=uid, unit_kind=kind,
                                     score=prev[0], confidence=prev[1],
                                     attempt_count=prev[2], correct_count=prev[3],
                                     incorrect_count=prev[4], error_counts=json.loads(prev[5]))
            evs = con.execute("SELECT evidence_json FROM mastery_events WHERE student_id=? "
                              "AND knowledge_unit_id=? ORDER BY created_at, event_id",
                              (student_id, uid)).fetchall()
            prior_signals = [json.loads(e[0]).get("signal") for e in evs]
            prior_signals = [s for s in prior_signals if s is not None]
            state, event = MAS.apply_event(
                student_id=student_id, kind=kind, ref=ref, question_id=question_id,
                attempt_id=attempt_id, correction_id=corr.correction_id,
                signal=signal, counted=counted, root_errors=roots,
                all_errors=all_errors,
                prior_signals=prior_signals, prior_state=prior)
            con.execute(
                "INSERT INTO mastery_states(mastery_id,student_id,knowledge_unit_id,"
                "unit_kind,score,confidence,attempt_count,correct_count,incorrect_count,"
                "last_attempt,last_correct,error_counts_json,status,policy_version)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(student_id,knowledge_unit_id) DO UPDATE SET "
                "score=excluded.score,confidence=excluded.confidence,"
                "attempt_count=excluded.attempt_count,correct_count=excluded.correct_count,"
                "incorrect_count=excluded.incorrect_count,last_attempt=excluded.last_attempt,"
                "last_correct=excluded.last_correct,error_counts_json=excluded.error_counts_json,"
                "status=excluded.status,policy_version=excluded.policy_version",
                (state.mastery_id, student_id, uid, kind, state.score, state.confidence,
                 state.attempt_count, state.correct_count, state.incorrect_count,
                 state.last_attempt, state.last_correct,
                 json.dumps(state.error_counts, ensure_ascii=False, sort_keys=True),
                 MAS.status_of(state, prior_signals[-3:] + ([signal] if signal is not None else [])),
                 policy.POLICY_VERSION))
            con.execute(
                "INSERT OR IGNORE INTO mastery_events(event_id,student_id,question_id,"
                "attempt_id,correction_id,knowledge_unit_id,unit_kind,old_score,new_score,"
                "old_confidence,new_confidence,reason,evidence_json,policy_version,created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (event.event_id, student_id, question_id, attempt_id, corr.correction_id,
                 uid, kind, event.old_score, event.new_score, event.old_confidence,
                 event.new_confidence, event.reason,
                 json.dumps(event.evidence, ensure_ascii=False, sort_keys=True),
                 event.policy_version, event.created_at))
            updates.append({"unit": uid, "score": state.score,
                            "confidence": state.confidence,
                            "status": MAS.status_of(
                                state, prior_signals[-3:] + ([signal] if signal is not None else []))})
        return updates

    @staticmethod
    def _record_seen(con, student_id: str, question_id: str,
                     attempt_id: str, corr: Correction) -> None:
        """Historial por estudiante (Fase 8): upsert atomico en la misma
        transaccion del submit. first_seen se conserva; replay nunca llega
        aqui (retorna antes), asi que attempt_count no se duplica."""
        now = _now()
        con.execute(
            "INSERT INTO question_history(student_id,question_id,"
            "first_seen,last_seen,attempt_count,last_status,last_score,"
            "last_attempt_id) VALUES(?,?,?,?,?,?,?,?) "
            "ON CONFLICT(student_id,question_id) DO UPDATE SET "
            "last_seen=excluded.last_seen,"
            "attempt_count=attempt_count+1,"
            "last_status=excluded.last_status,"
            "last_score=excluded.last_score,"
            "last_attempt_id=excluded.last_attempt_id",
            (student_id, question_id, now, now, 1, corr.status,
             float(corr.score), attempt_id))

    def has_seen(self, student_id: str, question_id: str) -> bool:
        con = self.store.connect()
        try:
            row = con.execute("SELECT 1 FROM question_history WHERE "
                              "student_id=? AND question_id=?",
                              (student_id, question_id)).fetchone()
        finally:
            con.close()
        return row is not None

    def get_history(self, student_id: str,
                    question_id: str) -> dict | None:
        con = self.store.connect()
        try:
            row = con.execute("SELECT first_seen, last_seen, attempt_count,"
                              " last_status, last_score, last_attempt_id"
                              " FROM question_history WHERE student_id=? AND"
                              " question_id=?",
                              (student_id, question_id)).fetchone()
        finally:
            con.close()
        if not row:
            return None
        return {"student_id": student_id, "question_id": question_id,
                "first_seen": row[0], "last_seen": row[1],
                "attempt_count": row[2], "last_status": row[3],
                "last_score": row[4], "last_attempt_id": row[5]}

    def get_recent_question_ids(self, student_id: str,
                                limit: int = 20) -> list[str]:
        if not isinstance(limit, int) or limit < 1:
            raise ValueError("limit inválido")
        con = self.store.connect()
        try:
            rows = con.execute("SELECT question_id FROM question_history"
                               " WHERE student_id=? ORDER BY last_seen DESC,"
                               " question_id ASC LIMIT ?",
                               (student_id, limit)).fetchall()
        finally:
            con.close()
        return [r[0] for r in rows]

    @staticmethod
    def _record_errors(con, student_id: str, question_id: str,
                       attempt_id: str, corr: Correction) -> None:
        """Error Memory (Fase 9): agregacion por (estudiante, error_key)
        en la misma transaccion del submit. Solo errores que
        CorrectionService detecto (nunca inferidos por score).
        Replay nunca llega aqui, asi que error_count no se duplica."""
        now = _now()
        for e in corr.detected_errors or []:
            key = e.error_type or ""
            if not key:
                continue
            con.execute(
                "INSERT INTO error_memory(student_id,error_key,"
                "first_seen,last_seen,error_count,severity,last_status,"
                "last_question_id,last_attempt_id)"
                " VALUES(?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(student_id,error_key) DO UPDATE SET "
                "last_seen=excluded.last_seen,"
                "error_count=error_count+1,"
                "severity=excluded.severity,"
                "last_status=excluded.last_status,"
                "last_question_id=excluded.last_question_id,"
                "last_attempt_id=excluded.last_attempt_id",
                (student_id, key, now, now, 1, e.severity or "",
                 corr.status, question_id, attempt_id))

    def get_error_memory(self, student_id: str) -> list[dict]:
        con = self.store.connect()
        try:
            rows = con.execute("SELECT error_key, first_seen, last_seen,"
                               " error_count, severity, last_status,"
                               " last_question_id, last_attempt_id"
                               " FROM error_memory WHERE student_id=?"
                               " ORDER BY error_key ASC",
                               (student_id,)).fetchall()
        finally:
            con.close()
        return [{"student_id": student_id, "error_key": r[0],
                 "first_seen": r[1], "last_seen": r[2],
                 "error_count": r[3], "severity": r[4],
                 "last_status": r[5], "last_question_id": r[6],
                 "last_attempt_id": r[7]} for r in rows]

    def get_recurrent_errors(self, student_id: str,
                             min_count: int = 2) -> list[dict]:
        """Errores con count>=min_count, orden determinista: severidad
        ponderada (misma escala que priority-policy) -> count ->
        recencia -> clave. Sin empates incidentales."""
        if not isinstance(min_count, int) or min_count < 1:
            raise ValueError("min_count inválido")
        sev_w = policy.PRIORITY_POLICY.parameters.get(
            "severity_weight", {})
        mem = [m for m in self.get_error_memory(student_id)
               if m["error_count"] >= min_count]
        # Orden total determinista por sorts estables compuestos:
        # severidad ponderada -> count -> recencia -> clave.
        mem.sort(key=lambda m: m["error_key"])
        mem.sort(key=lambda m: m["last_seen"], reverse=True)
        mem.sort(key=lambda m: m["error_count"], reverse=True)
        mem.sort(key=lambda m: float(sev_w.get(m["severity"], 0.0)),
                 reverse=True)
        return mem

    def get_error_history(self, student_id: str,
                          error_key: str) -> dict | None:
        con = self.store.connect()
        try:
            row = con.execute("SELECT first_seen, last_seen, error_count,"
                              " severity, last_status, last_question_id,"
                              " last_attempt_id FROM error_memory"
                              " WHERE student_id=? AND error_key=?",
                              (student_id, error_key)).fetchone()
        finally:
            con.close()
        if not row:
            return None
        return {"student_id": student_id, "error_key": error_key,
                "first_seen": row[0], "last_seen": row[1],
                "error_count": row[2], "severity": row[3],
                "last_status": row[4], "last_question_id": row[5],
                "last_attempt_id": row[6]}

    @staticmethod
    def _record_reviews(con, student_id: str, attempt_id: str,
                        corr: Correction, updates: list) -> None:
        """Memoria de revision (Fase 10): una fila por unidad tocada por
        el submit, en la misma transaccion. Intervalos de REVIEW_POLICY:
        correct duplica (tope max), partial fija, incorrect reinicia,
        otros estados conservan. Replay nunca llega aqui."""
        from datetime import timedelta
        from .policy import REVIEW_POLICY
        p = REVIEW_POLICY.parameters
        now = _now()
        outcome = {"CORRECT": "correct",
                   "PARTIALLY_CORRECT": "partial",
                   "INCORRECT": "incorrect"}.get(corr.status, "other")
        for u in updates or []:
            uid = u.get("unit", "")
            kind, _, ref = uid.partition(":")
            if not kind or not ref:
                continue
            row = con.execute("SELECT interval_days FROM student_spacing"
                              " WHERE student_id=? AND unit_kind=? AND"
                              " unit_id=?",
                              (student_id, kind, ref)).fetchone()
            prev = int(row[0]) if row else None
            if prev is None:
                interval = {"correct": p["initial_days"]["correct"],
                            "partial": p["partial_days"],
                            "incorrect": p["incorrect_days"],
                            "other": int(p["min_interval_days"])}[outcome]
            elif outcome == "correct":
                interval = min(int(prev * p["growth_factor"]),
                               int(p["max_interval_days"]))
            elif outcome == "partial":
                interval = int(p["partial_days"])
            elif outcome == "incorrect":
                interval = int(p["incorrect_days"])
            else:
                interval = prev
            interval = max(int(p["min_interval_days"]), interval)
            nxt = (datetime.fromisoformat(now) +
                   timedelta(days=interval)).isoformat(timespec="seconds")
            con.execute(
                "INSERT INTO student_spacing(student_id,unit_kind,unit_id,"
                "first_review,last_review,next_review,review_count,"
                "interval_days,last_status,last_score,last_attempt_id)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(student_id,unit_kind,unit_id) DO UPDATE SET "
                "last_review=excluded.last_review,"
                "next_review=excluded.next_review,"
                "review_count=review_count+1,"
                "interval_days=excluded.interval_days,"
                "last_status=excluded.last_status,"
                "last_score=excluded.last_score,"
                "last_attempt_id=excluded.last_attempt_id",
                (student_id, kind, ref, now, now, nxt, 1, interval,
                 corr.status, float(corr.score), attempt_id))

    def get_spacing(self, student_id: str, kind: str,
                    ref: str) -> dict | None:
        con = self.store.connect()
        try:
            row = con.execute("SELECT first_review, last_review,"
                              " next_review, review_count, interval_days,"
                              " last_status, last_score, last_attempt_id"
                              " FROM student_spacing WHERE student_id=? AND"
                              " unit_kind=? AND unit_id=?",
                              (student_id, kind, ref)).fetchone()
        finally:
            con.close()
        if not row:
            return None
        return {"student_id": student_id, "unit_kind": kind,
                "unit_id": ref, "first_review": row[0],
                "last_review": row[1], "next_review": row[2],
                "review_count": row[3], "interval_days": row[4],
                "last_status": row[5], "last_score": row[6],
                "last_attempt_id": row[7]}

    def get_due_units(self, student_id: str, limit: int = 20,
                      now: str | None = None) -> list[dict]:
        """Unidades con next_review vencido. `now` inyectable para tests
        deterministas; por defecto tiempo real. Orden: next_review,
        unit_kind, unit_id (total, sin incidentales)."""
        if not isinstance(limit, int) or limit < 1:
            raise ValueError("limit inválido")
        moment = now or _now()
        con = self.store.connect()
        try:
            rows = con.execute("SELECT unit_kind, unit_id, next_review,"
                               " review_count, interval_days, last_status"
                               " FROM student_spacing WHERE student_id=?"
                               " AND next_review <= ? ORDER BY next_review ASC,"
                               " unit_kind ASC, unit_id ASC LIMIT ?",
                               (student_id, moment, limit)).fetchall()
        finally:
            con.close()
        return [{"unit_kind": r[0], "unit_id": r[1],
                 "knowledge_unit_id": "%s:%s" % (r[0], r[1]),
                 "next_review": r[2], "review_count": r[3],
                 "interval_days": r[4], "last_status": r[5]}
                for r in rows]

    def get_coverage(self, student_id: str) -> dict:
        """Cobertura sobre el universo KB (topics+formulas+concepts+
        sections con h2). Estados derivados de MasteryState existente:
        mastered (status MASTERED), weak (AT_RISK/EMERGING con intentos),
        learning (resto con intentos), unseen (sin fila o 0 intentos).
        Solo lectura; determinista (conteos + orden fijo)."""
        conkb = sqlite3.connect("file:%s?mode=ro" % self.kb_path, uri=True)
        try:
            topics = ["topic:T%02d" % t for t in range(1, 11)]
            formulas = ["formula:" + r[0] for r in conkb.execute(
                "SELECT equation_id FROM formulas ORDER BY equation_id")]
            concepts = ["concept:" + r[0] for r in conkb.execute(
                "SELECT DISTINCT term_ca FROM concepts WHERE"
                " LENGTH(term_ca)>0 ORDER BY term_ca")]
            sections = ["section:T%02d:%s" % (r[0], r[1]) for r in
                        conkb.execute(
                            "SELECT d.topic, s.h2 FROM sections s JOIN"
                            " documents d ON d.id=s.doc_id WHERE"
                            " LENGTH(s.h2)>0 ORDER BY d.topic, s.h2")]
        finally:
            conkb.close()
        universe = {"topic": topics, "formula": formulas,
                    "concept": concepts, "section": sections}
        con = self.store.connect()
        try:
            states = {r[0]: (r[1], r[2], r[3]) for r in con.execute(
                "SELECT knowledge_unit_id, status, score, attempt_count"
                " FROM mastery_states WHERE student_id=?", (student_id,))}
        finally:
            con.close()

        def _classify(uid):
            st = states.get(uid)
            if st is None or int(st[2]) <= 0:
                return "unseen"
            if st[0] == "MASTERED":
                return "mastered"
            if st[0] in ("AT_RISK", "EMERGING"):
                return "weak"
            return "learning"

        by_kind, total_seen = {}, 0
        for kind, uids in universe.items():
            counts = {"total": len(uids), "seen": 0, "unseen": 0,
                      "mastered": 0, "weak": 0, "learning": 0}
            for uid in uids:
                c = _classify(uid)
                counts[c] += 1
                if c != "unseen":
                    counts["seen"] += 1
            total_seen += counts["seen"]
            counts["coverage_ratio"] = round(
                counts["seen"] / counts["total"], 4) if counts["total"] \
                else 0.0
            by_kind[kind] = counts
        total = sum(v["total"] for v in by_kind.values())
        return {"total_units": total, "seen_units": total_seen,
                "unseen_units": total - total_seen,
                "coverage_ratio": round(total_seen / total, 4) if total
                else 0.0,
                "by_kind": by_kind}

    def _refresh_memories(self, con, student_id: str) -> list[dict]:
        rows = con.execute("SELECT knowledge_unit_id, unit_kind, score, confidence,"
                           " attempt_count, correct_count FROM mastery_states "
                           "WHERE student_id=?", (student_id,)).fetchall()
        from .models import MasteryState
        states = []
        for r in rows:
            st = MasteryState(mastery_id="", student_id=student_id,
                              knowledge_unit_id=r[0], unit_kind=r[1], score=r[2],
                              confidence=r[3], attempt_count=r[4], correct_count=r[5])
            states.append({"knowledge_unit_id": r[0],
                           "status": MAS.status_of(st, []), "score": r[2]})
        err_rows = con.execute(
            "SELECT evidence_json FROM mastery_events WHERE student_id=?", (student_id,)).fetchall()
        totals: dict[str, int] = {}
        for (blob,) in err_rows:
            data = json.loads(blob)
            for e in (data.get("all_errors") or data.get("root_errors") or []):
                totals[e] = totals.get(e, 0) + 1
        attempts = [{"attempt_id": r[0], "correction_id": r[1]} for r in con.execute(
            "SELECT attempt_id, correction_id FROM mastery_events WHERE student_id=? "
            "ORDER BY created_at DESC LIMIT 50", (student_id,)).fetchall()]
        mems = MEM.summarize_performance(student_id, totals, attempts,
                                         [{"knowledge_unit_id": s["knowledge_unit_id"],
                                           "status": s["status"]} for s in states])
        out = []
        for m in mems:
            con.execute("INSERT OR REPLACE INTO memories(memory_id,student_id,kind,text,"
                        "confidence,evidence_count,last_evidence,attempt_ids_json,"
                        "correction_ids_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (m.memory_id, student_id, m.kind, m.text, m.confidence,
                         m.evidence_count, m.last_evidence,
                         json.dumps(m.attempt_ids), json.dumps(m.correction_ids), m.last_evidence))
            out.append(m.to_dict())
        return out

    # ---------- APIs §107 ----------
    def get_mastery(self, student_id: str, knowledge_unit: str) -> dict | None:
        con = self.store.connect()
        try:
            row = con.execute("SELECT knowledge_unit_id, unit_kind, score, confidence,"
                              " attempt_count, correct_count, incorrect_count, last_attempt,"
                              " last_correct, error_counts_json, status FROM mastery_states "
                              "WHERE student_id=? AND knowledge_unit_id=?",
                              (student_id, knowledge_unit)).fetchone()
        finally:
            con.close()
        if not row:
            return None
        import json as _j
        return {"knowledge_unit_id": row[0], "unit_kind": row[1], "score": row[2],
                "confidence": row[3], "attempt_count": row[4], "correct_count": row[5],
                "incorrect_count": row[6], "last_attempt": row[7], "last_correct": row[8],
                "error_counts": _j.loads(row[9]), "status": row[10]}

    def get_topic_mastery(self, student_id: str, topic: int) -> dict:
        return self._aggregate(student_id, "topic", "T%02d" % topic)

    def get_formula_mastery(self, student_id: str, formula_id: str) -> dict | None:
        return self.get_mastery(student_id, "formula:" + formula_id)

    def get_error_profile(self, student_id: str, unit_prefix: str = "") -> dict:
        con = self.store.connect()
        try:
            rows = con.execute("SELECT knowledge_unit_id, error_counts_json FROM mastery_states "
                               "WHERE student_id=?", (student_id,)).fetchall()
        finally:
            con.close()
        totals: dict[str, int] = {}
        import json as _j
        for uid, blob in rows:
            if unit_prefix and not uid.startswith(unit_prefix):
                continue
            for k, v in _j.loads(blob).items():
                totals[k] = totals.get(k, 0) + v
        return totals

    def get_recent_attempts(self, student_id: str, limit: int = 20) -> list[dict]:
        con = self.store.connect()
        try:
            return [{"attempt_id": r[0], "question_id": r[1], "created_at": r[2]}
                    for r in con.execute("SELECT attempt_id, question_id, created_at FROM attempts "
                                         "WHERE student_id=? ORDER BY created_at DESC LIMIT ?",
                                         (student_id, limit)).fetchall()]
        finally:
            con.close()

    def get_unit_history(self, student_id: str, knowledge_unit_id: str) -> dict:
        """Historial de una unidad: estado + eventos cronologicos. Solo lectura.

        Aditivo Fase 6 Bloque A: no cambia esquema ni comportamiento existente.
        """
        import json as _j
        con = self.store.connect()
        try:
            srow = con.execute(
                "SELECT unit_kind, score, confidence, attempt_count, correct_count,"
                " incorrect_count, last_attempt, last_correct, error_counts_json,"
                " status, policy_version FROM mastery_states "
                "WHERE student_id=? AND knowledge_unit_id=?",
                (student_id, knowledge_unit_id)).fetchone()
            erows = con.execute(
                "SELECT event_id, question_id, attempt_id, correction_id,"
                " old_score, new_score, reason, evidence_json, policy_version,"
                " created_at FROM mastery_events "
                "WHERE student_id=? AND knowledge_unit_id=? "
                "ORDER BY created_at ASC, event_id ASC",
                (student_id, knowledge_unit_id)).fetchall()
        finally:
            con.close()
        state = None
        if srow:
            state = {"unit_kind": srow[0], "score": srow[1], "confidence": srow[2],
                     "attempt_count": srow[3], "correct_count": srow[4],
                     "incorrect_count": srow[5], "last_attempt": srow[6],
                     "last_correct": srow[7],
                     "error_counts": _j.loads(srow[8] or "{}"), "status": srow[9],
                     "policy_version": srow[10]}
        events = [{"event_id": r[0], "question_id": r[1], "attempt_id": r[2],
                   "correction_id": r[3], "old_score": r[4], "new_score": r[5],
                   "reason": r[6], "evidence": _j.loads(r[7] or "{}"),
                   "policy_version": r[8], "created_at": r[9]} for r in erows]
        return {"knowledge_unit_id": knowledge_unit_id, "state": state,
                "events": events}

    def get_memory(self, student_id: str) -> list[dict]:
        con = self.store.connect()
        try:
            return [{"memory_id": r[0], "kind": r[1], "text": r[2], "confidence": r[3],
                     "evidence_count": r[4], "attempt_ids": json.loads(r[5])}
                    for r in con.execute("SELECT memory_id, kind, text, confidence,"
                                         " evidence_count, attempt_ids_json FROM memories "
                                         "WHERE student_id=?", (student_id,)).fetchall()]
        finally:
            con.close()

    def get_weak_units(self, student_id: str, kind: str = "", limit: int = 10) -> list[dict]:
        """API Fase 6 (select weak concept/formula): solo lectura. §162."""
        con = self.store.connect()
        try:
            rows = con.execute("SELECT knowledge_unit_id, unit_kind, score, confidence,"
                               " attempt_count, status FROM mastery_states WHERE student_id=?"
                               + (" AND unit_kind=?" if kind else ""),
                               (student_id,) + ((kind,) if kind else ())).fetchall()
        finally:
            con.close()
        out = [{"knowledge_unit_id": r[0], "unit_kind": r[1], "score": r[2],
                "confidence": r[3], "attempt_count": r[4], "status": r[5]} for r in rows]
        # Orden total determinista (GAP 3): debilidad, mas intentos primero,
        # y desempate final por identificador canonico. NO cambia la logica
        # de debilidad: misma entrada -> mismo orden siempre.
        out.sort(key=lambda x: (x["score"], -x["attempt_count"], x["knowledge_unit_id"]))
        return out[:limit]

    def _aggregate(self, student_id: str, kind: str, ref: str) -> dict:
        children = self._children(student_id, kind, ref)
        from . import policy as _pol
        score, n = _pol.aggregate([(c["score"], c["attempt_count"]) for c in children])
        return {"knowledge_unit_id": "%s:%s" % (kind, ref), "score": score,
                "attempt_count": n, "children": len(children)}

    def _children(self, student_id: str, kind: str, ref: str) -> list[dict]:
        con = self.store.connect()
        try:
            if kind == "topic":
                # Hijas: el propio topic + secciones/conceptos/formulas del tema.
                rows = con.execute(
                    "SELECT knowledge_unit_id, unit_kind, score, attempt_count FROM mastery_states "
                    "WHERE student_id=? AND (knowledge_unit_id=? OR knowledge_unit_id LIKE ?)",
                    (student_id, "topic:" + ref, "%:" + ref + "%")).fetchall()
            else:
                rows = con.execute(
                    "SELECT knowledge_unit_id, unit_kind, score, attempt_count FROM mastery_states "
                    "WHERE student_id=? AND knowledge_unit_id=?", (student_id, ref)).fetchall()
        finally:
            con.close()
        return [{"knowledge_unit_id": r[0], "unit_kind": r[1], "score": r[2],
                 "attempt_count": r[3]} for r in rows]

    # ---------- regrade / review (§70-73) ----------
    def regrade(self, attempt_id: str, *, reason: str, reviewer: str = "manual",
                override_score: float | None = None) -> dict:
        con = self.store.connect()
        try:
            row = con.execute("SELECT body_json, question_id FROM corrections WHERE attempt_id=? "
                              "ORDER BY version DESC LIMIT 1", (attempt_id,)).fetchone()
            if not row:
                raise KeyError("attempt sin correccion: %s" % attempt_id)
            import json as _j
            body = _j.loads(row[0])
            qid = row[1]
            if override_score is not None:
                body["score"] = override_score
                body["percentage"] = round(override_score * 10, 2)
                body["status"] = "CORRECT" if override_score >= 9.999 else (
                    "PARTIALLY_CORRECT" if override_score > 0 else "INCORRECT")
            n = con.execute("SELECT COUNT(*) FROM corrections WHERE attempt_id=?",
                            (attempt_id,)).fetchone()[0]
            con.execute("INSERT INTO corrections(correction_id,attempt_id,question_id,"
                        "version,reason,reviewer,body_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                        (body.get("correction_id", "corr-x") + "-v%d" % (n + 1), attempt_id,
                         qid, n + 1, reason, reviewer,
                         _j.dumps(body, ensure_ascii=False, sort_keys=True),
                         _now()))
            con.execute("INSERT INTO audit_log(action,ref_id,detail,created_at) VALUES(?,?,?,?)",
                        ("regrade", attempt_id,
                         _j.dumps({"reason": reason, "reviewer": reviewer}), _now()))
            con.commit()
            return {"attempt_id": attempt_id, "version": n + 1, "reason": reason}
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def add_review(self, attempt_id: str, reason: str) -> str:
        import hashlib as _hl
        rid = "rev-" + _hl.sha256((attempt_id + reason).encode()).hexdigest()[:12]
        con = self.store.connect()
        try:
            con.execute("INSERT OR IGNORE INTO reviews(review_id,attempt_id,reason,status,"
                        "created_at) VALUES(?,?,?,?,?)",
                        (rid, attempt_id, reason, "PENDING", _now()))
            con.commit()
            return rid
        finally:
            con.close()
