"""Bridge presentació B2: HTTP stdlib -> Application Layer (F10).

Capa fina: serveix `web/` estàtic + JSON cap a workflows certificats.
NO duplica domini: delega tot, projecta DTOs segurs, enriqueix errors
amb les taules humanes del propi backend (ERROR_HUMAN/BAND_HUMAN/
FIX_HINT). KB sempre en mode lectura. Sense dependències noves.

DTOs servits (estables B2):
  tutor.ask        {answer,status,abstain,claims[],formulas[],
                    provenance[],versions{}} |USER_ERROR...
  practice.start   {question{stem view},log} (+ cookie sm_session)
  practice.submit  {result{status,score,errors[+label,hint,band],
                    mastery[]},attempt}
  practice.question/get_result/complete: passthrough de workflow
  study.topics     [{topic,documents,sections,formulas,concepts,
                    mastery{score,attempts}|null}]
  study.next       {recommendation|null} (F6 real o buit honest)
  study.documents/sections/content: lectures KB read-only
  study.mastery    {topic: {score,attempts}|null}
"""
from __future__ import annotations

import html
import json
import os
import secrets
import shutil
import sqlite3
import sys
import urllib.parse
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WEB = Path(__file__).resolve().parent
ROOT = WEB.parent
sys.path.insert(0, str(ROOT))

from app.adaptive.loop import AdaptiveLoop  # noqa: E402
from app.application.adaptive import AdaptivePracticeWorkflow  # noqa: E402
from app.application.errors import AppError  # noqa: E402
from app.application.errors import map_error as _map_app_error  # noqa: E402
from app.application.exam import ExamWorkflow  # noqa: E402
from app.application.practice import PracticeWorkflow  # noqa: E402
from app.application.review import ReviewWorkflow  # noqa: E402
from app.application.service import ApplicationService  # noqa: E402
from app.application.session import ApplicationSession  # noqa: E402
from app.application.tutor import TutorWorkflow  # noqa: E402
from app.calendar import CalendarSource  # noqa: E402
from app.exam.grading import ExamGradingService  # noqa: E402
from app.exam.review import (BAND_HUMAN, ERROR_HUMAN,  # noqa: E402
                             ExamReviewService, _FALLBACK_HINT, FIX_HINT)
from app.exam.service import ExamSessionService  # noqa: E402
from app.examiner.service import ExaminerEngine  # noqa: E402
from app.examiner.store import QuestionStore  # noqa: E402
from app.llm.extractive import ExtractiveProvider  # noqa: E402
from app.reasoning.engine import ReasoningEngine  # noqa: E402
from app.retrieval.service import RetrievalService  # noqa: E402
from app.student.service import StudentService  # noqa: E402

from app import paths as sm_paths  # noqa: E402

KB = str(sm_paths.package_dir() / "data" / "processed" / "knowledge.sqlite")
# Un directori `index/` buit (el crea `sistemes init`) NO es un index: cal
# el centinela real que escriu app.build_index (lexical/fts.sqlite).
INDEX = str(sm_paths.index_dir()) \
    if (sm_paths.index_dir() / "lexical" / "fts.sqlite").is_file() \
    else str(sm_paths.package_dir() / "data" / "index")
GENDB = str(sm_paths.package_dir() / "data" / "generated" / "questions.sqlite")

STATUS = {"USER_ERROR": 400, "VALIDATION_ERROR": 400, "NOT_FOUND": 404,
          "STATE_ERROR": 409, "KNOWLEDGE_ERROR": 422,
          "RETRIEVAL_ERROR": 503, "GENERATION_ERROR": 502,
          "CORRECTION_ERROR": 422, "PERSISTENCE_ERROR": 500,
          "POLICY_ERROR": 422, "INTERNAL_ERROR": 500}

# Etiquetes de presentació (B3.6/B3.11): noms per a valors backend.
# No decideixen res; el significat el defineix F5/F6.
ACTION_META = {
    "PRACTICE": ("Practicar", "Pràctica guiada del punt feble."),
    "REVIEW": ("Repassar", "Repàs de contingut vist."),
    "REINFORCE": ("Reforçar", "Aquest punt necessita més pràctica."),
    "CHALLENGE": ("Repte", "Nivell avançat: posa't a prova."),
    "MAINTAIN": ("Mantenir", "Consolida el que ja domines.")}
STATUS_LABEL = {"UNKNOWN": "Sense dades", "EMERGING": "Inicial",
                "DEVELOPING": "En progrés", "PROFICIENT": "Competent",
                "MASTERED": "Assolit", "AT_RISK": "En risc"}
# Prefixos de reason_codes aptes per mostrar (la resta és mecànica
# interna: spacing/categoria/ancestres). Valors sempre literals.
REASON_PREFIX = {"mastery:": "Mastery", "evidencia:": "Evidència",
                 "confianza_baja:": "Confiança",
                 "raiz:": "Error principal",
                 "fallo_reciente:": "Fallo recent",
                 "dificultad:": "Dificultat"}


# ---------- LaTeX segur (subconjunt amb llista blanca) ----------
_GREEK = {"alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ",
          "epsilon": "ε", "varepsilon": "ε", "zeta": "ζ", "eta": "η",
          "theta": "θ", "iota": "ι", "kappa": "κ", "lambda": "λ",
          "mu": "μ", "nu": "ν", "xi": "ξ", "pi": "π", "rho": "ρ",
          "sigma": "σ", "varsigma": "ς", "tau": "τ", "phi": "φ",
          "chi": "χ", "psi": "ψ", "omega": "ω", "Gamma": "Γ",
          "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ",
          "Pi": "Π", "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω"}
_SYM = {"cdot": "·", "times": "×", "div": "÷", "pm": "±", "mp": "∓",
         "leq": "≤", "geq": "≥", "neq": "≠", "approx": "≈", "infty": "∞",
         "partial": "∂", "sum": "∑", "int": "∫", "rightarrow": "→",
         "leftarrow": "←", "ldots": "…", "cdots": "⋯"}
_SPACE = {"\\,": " ", "\\;": " ", "\\:": " ", "\\!": "", "\\ ": " ",
          "\\quad": "  ", "\\qquad": "   "}
_ESCAPED = {"\\%": "%", "\\&": "&", "\\$": "$", "\\{": "{", "\\}": "}"}


def render_latex(src: str) -> str:
    """LaTeX -> HTML segur. Fora de la llista blanca: text escapat
    literal (mai es perd contingut, mai s'emet markup arbitrari).
    Nomes emet: sub/sup/span/br + text escapat."""
    s = src.strip()
    if s.startswith("\\(") and s.endswith("\\)"):
        s = s[2:-2]
    if len(s) >= 2 and s.startswith("$") and s.endswith("$"):
        s = s[1:-1]
    out, _ = _nodes(s, 0, None)
    return out


def _nodes(s, i, stop):
    parts = []
    n = len(s)
    while i < n:
        ch = s[i]
        if stop and ch == stop:
            return "".join(parts), i + 1
        if ch == "\\":
            html_frag, i = _command(s, i)
            parts.append(html_frag)
        elif ch == "{":
            inner, i = _nodes(s, i + 1, "}")
            parts.append(inner)
        elif ch == "^":
            arg, i = _arg(s, i + 1)
            parts.append("<sup>%s</sup>" % arg)
        elif ch == "_":
            arg, i = _arg(s, i + 1)
            parts.append("<sub>%s</sub>" % arg)
        elif ch == "\n":
            parts.append("<br>")
            i += 1
        else:
            parts.append(html.escape(ch, quote=False))
            i += 1
    return "".join(parts), i


def _arg(s, i):
    n = len(s)
    while i < n and s[i] == " ":
        i += 1
    if i < n and s[i] == "{":
        return _nodes(s, i + 1, "}")
    if i < n and s[i] == "\\":
        return _command(s, i)
    if i < n:
        return html.escape(s[i], quote=False), i + 1
    return "", i


def _command(s, i):
    n = len(s)
    for esc, val in _ESCAPED.items():
        if s.startswith(esc, i):
            return html.escape(val, quote=False), i + len(esc)
    for sp, val in _SPACE.items():
        if s.startswith(sp, i):
            return html.escape(val, quote=False), i + len(sp)
    if s.startswith("\\\\", i):
        return "<br>", i + 2
    j = i + 1
    while j < n and s[j].isalpha():
        j += 1
    name = s[i + 1:j]
    if not name:
        return html.escape("\\", quote=False), i + 1
    if name == "frac":
        num, k = _arg(s, j)
        den, k = _arg(s, k)
        return ('<span class="fr"><span class="num">%s</span>'
                '<span class="den">%s</span></span>' % (num, den)), k
    if name == "sqrt":
        inner, k = _arg(s, j)
        return '<span class="rt">√<span>%s</span></span>' % inner, k
    if name == "text":
        inner, k = _arg(s, j)
        return inner, k
    if name in ("left", "right"):
        return "", j
    if name in _GREEK:
        return _GREEK[name], j
    if name in _SYM:
        return _SYM[name], j
    return html.escape("\\" + name, quote=False), j


# ---------- bridge ----------
class Bridge:
    def __init__(self, kb=KB, index=INDEX, gen_src=GENDB,
                 workdir: str = "", sessions: dict | None = None,
                 lock=None, calendar_path=None, student: str = "") -> None:
        import tempfile
        import threading
        self.student = student or os.environ.get("SM_STUDENT", "me")
        self.kb, self.index = kb, index
        self.work = Path(workdir) if workdir else Path(
            tempfile.mkdtemp(prefix="sm-web-"))
        self.work.mkdir(parents=True, exist_ok=True)
        qdb = str(self.work / "q.sqlite")
        if not Path(qdb).exists():
            shutil.copyfile(gen_src, qdb)
        sdb = str(self.work / "s.sqlite")
        retr = RetrievalService(kb, index)
        reng = ReasoningEngine(retr, kb, provider=ExtractiveProvider())
        eng = ExaminerEngine(retr, kb, qdb)
        QuestionStore(qdb)
        stu = StudentService(kb, qdb, sdb)
        loop = AdaptiveLoop(stu)
        exs = ExamSessionService(sdb, qdb, kb)
        exg = ExamGradingService(exs, stu)
        exr = ExamReviewService(exs, exg, stu, kb)
        self.app = ApplicationService(
            retriever=retr, reasoning=reng, examiner=eng,
            correction=stu.correction, students=stu, adaptive=loop,
            exam_sessions=exs, exam_grading=exg, exam_review=exr,
            kb_path=kb)
        self.flows = {"tutor": TutorWorkflow(self.app),
                      "practice": PracticeWorkflow(self.app),
                      "adaptive": AdaptivePracticeWorkflow(self.app),
                      "exam": ExamWorkflow(self.app),
                      "review": ReviewWorkflow(self.app)}
        self.sessions: dict = sessions if sessions is not None else {}
        self._lock = lock or threading.Lock()
        self.exams_meta: dict = {}
        self.calendar = CalendarSource(calendar_path)

    # ----- KB read-only -----
    def _kb(self):
        return sqlite3.connect("file:%s?mode=ro" % self.kb, uri=True)

    def kb_topics(self):
        con = self._kb()
        try:
            out = []
            for (t,) in con.execute(
                    "SELECT DISTINCT topic FROM documents ORDER BY 1"):
                docs = con.execute(
                    "SELECT COUNT(*) FROM documents WHERE topic=?",
                    (t,)).fetchone()[0]
                secs = con.execute(
                    "SELECT COUNT(*) FROM sections s JOIN documents d "
                    "ON d.id=s.doc_id WHERE d.topic=?", (t,)).fetchone()[0]
                forms = con.execute(
                    "SELECT COUNT(*) FROM formulas WHERE topic=?",
                    (t,)).fetchone()[0]
                conc = con.execute(
                    "SELECT COUNT(*) FROM concepts WHERE topic=?",
                    (t,)).fetchone()[0]
                try:
                    m = self.app.students.get_topic_mastery(
                        self.student, int(t))
                    mastery = {"score": m.get("score"),
                               "attempts": m.get("attempt_count")}
                except Exception:  # noqa: BLE001 - sense historial
                    mastery = None
                out.append({"topic": t, "documents": docs,
                            "sections": secs, "formulas": forms,
                            "concepts": conc, "mastery": mastery})
            return out
        finally:
            con.close()

    def kb_documents(self, topic, doc_id=None):
        con = self._kb()
        try:
            query = "SELECT id, title, kind FROM documents WHERE topic=?"
            params = [topic]
            if doc_id:
                query += " AND id=?"
                params.append(doc_id)
            query += " ORDER BY doc_order"
            return [{"id": r[0], "title": r[1], "kind": r[2]}
                    for r in con.execute(query, params).fetchall()]
        finally:
            con.close()

    def documents_catalog(self, topic=None):
        """Catàleg de documents de curs, sempre en lectura i amb traça."""
        con = self._kb()
        try:
            where = ""
            params = []
            if topic is not None:
                where = "WHERE d.topic=?"
                params.append(topic)
            rows = con.execute(
                "SELECT d.id, d.title, d.kind, d.topic, "
                "COUNT(s.id) FROM documents d "
                "LEFT JOIN sections s ON s.doc_id=d.id "
                + where + " GROUP BY d.id, d.title, d.kind, d.topic "
                "ORDER BY d.topic, d.doc_order", params).fetchall()
            return [{"id": row[0], "title": row[1], "kind": row[2],
                     "topic": row[3], "sections": row[4],
                     "url": "topic.html?topic=%s&doc_id=%s" %
                     (row[3], row[0])} for row in rows]
        finally:
            con.close()

    def kb_sections(self, doc_id):
        con = self._kb()
        try:
            secs = con.execute("SELECT id, h2 FROM sections WHERE "
                               "doc_id=? ORDER BY idx",
                               (doc_id,)).fetchall()
            if not secs and isinstance(doc_id, int):
                secs = con.execute(
                    "SELECT s.id, s.h2 FROM sections s JOIN documents d "
                    "ON d.id=s.doc_id WHERE d.topic=? ORDER BY d.doc_order,"
                    " s.idx", (doc_id,)).fetchall()
            return [{"id": r[0], "h2": r[1]} for r in secs]
        finally:
            con.close()

    def kb_content(self, section_id):
        con = self._kb()
        try:
            h2 = con.execute("SELECT h2 FROM sections WHERE id=?",
                             (section_id,)).fetchone()
            if not h2:
                return None
            blocks = []
            for (ct, tx) in con.execute(
                    "SELECT content_type, text FROM chunks WHERE "
                    "section_id=? ORDER BY rowid", (section_id,)).fetchall():
                blocks.append({"kind": "text" if ct != "table" else
                               "table", "text": tx})
            for (cap, md) in con.execute(
                    "SELECT caption, markdown FROM tables_t WHERE "
                    "section_id=? ORDER BY rowid", (section_id,)).fetchall():
                blocks.append({"kind": "table", "caption": cap,
                               "text": md})
            for r in con.execute(
                    "SELECT equation_id, expression FROM formulas f "
                    "JOIN chunks c ON c.section_id=? AND "
                    "instr(c.formula_ids, f.equation_id) > 0 "
                    "GROUP BY f.equation_id ORDER BY f.equation_id",
                    (section_id,)).fetchall():
                blocks.append({"kind": "formula", "equation_id": r[0],
                               "expression": r[1],
                               "html": render_latex(r[1] or "")})
            return {"h2": h2[0], "blocks": blocks}
        finally:
            con.close()

    # ----- learn (F6/F5, només projecció) -----
    def project_rec(self, item, lang="ca"):
        li = 0 if lang == "ca" else 1
        d = item.to_dict() if hasattr(item, "to_dict") else dict(item)
        mu = None
        try:
            mu = self.app.students.get_mastery(
                self.student, d.get("knowledge_unit_id", ""))
        except Exception:  # noqa: BLE001 - sense historial
            mu = None
        reasons = []
        for code in d.get("reason_codes", d.get("reasons", [])) or []:
            for pre, lab in REASON_PREFIX.items():
                if code.startswith(pre):
                    val = code[len(pre):]
                    vlab = ""
                    if pre == "raiz:":
                        vlab = ERROR_HUMAN.get(val, (val, val))[li]
                    reasons.append({"label": lab, "value": val,
                                    "value_label": vlab})
                    break
        errs = []
        if mu and mu.get("error_counts"):
            for t, n in sorted(mu["error_counts"].items()):
                errs.append({"type": t, "count": n,
                             "label": ERROR_HUMAN.get(t, (t, t))[li]})
        act = d.get("action", "")
        meta = ACTION_META.get(act, (act, ""))
        mastery = None
        if mu:
            mastery = {"score": mu.get("score"),
                       "status": mu.get("status"),
                       "status_label": STATUS_LABEL.get(
                           mu.get("status", ""), mu.get("status", "")),
                       "confidence": mu.get("confidence"),
                       "attempts": mu.get("attempt_count")}
        return {"unit": d.get("knowledge_unit_id", ""),
                "kind": d.get("unit_kind", ""),
                "action": act, "action_label": meta[0],
                "action_hint": meta[1],
                "difficulty": d.get("difficulty", ""),
                # priority viaja para round-trip fiel a generate();
                # la UI no lo muestra ni lo interpreta (B3.5).
                "priority": d.get("priority_score", 0.0),
                "targets": {"topic": d.get("target_topic"),
                            "section": d.get("target_section"),
                            "concepts": list(
                                d.get("target_concepts", []) or []),
                            "formulas": list(
                                d.get("target_formulas", []) or [])},
                "reasons": list(d.get("reason_codes",
                                      d.get("reasons", [])) or []),
                "reasons_display": reasons,
                "mastery": mastery, "errors": errs}

    def learn_priorities(self, limit=5, lang="ca"):
        items = self.app.adaptive.recommend(
            self.student, limit=limit, seed=7)
        return [self.project_rec(i, lang) for i in items]

    def learn_locate(self, unit):
        """Unitat -> URL real (topic/content) o null honest."""
        con = self._kb()
        try:
            if unit.startswith("topic:"):
                try:
                    t = int(unit.split(":")[1].lstrip("T"))
                except ValueError:
                    return None
                return {"kind": "topic", "topic": t,
                        "url": "topic.html?topic=%d" % t}
            if unit.startswith("section:"):
                parts = unit.split(":", 2)
                h2 = parts[2] if len(parts) > 2 else ""
                row = None
                if h2:
                    row = con.execute(
                        "SELECT s.id FROM sections s JOIN documents d "
                        "ON d.id=s.doc_id WHERE d.topic=? AND "
                        "(s.h2=? OR s.h2 LIKE ?) ORDER BY s.id LIMIT 1",
                        (int(parts[1].lstrip("T")), h2,
                         "%" + h2[:30] + "%")).fetchone()
                if row:
                    return {"kind": "section", "section_id": row[0],
                            "url": "content.html?section_id=%s" % row[0]}
                return {"kind": "section", "section_id": None,
                        "url": None}
            if unit.startswith("concept:"):
                term = unit.split(":", 1)[1]
                row = con.execute("SELECT topic FROM concepts WHERE "
                                  "term_ca=? LIMIT 1", (term,)).fetchone()
                if row:
                    return {"kind": "concept", "topic": row[0],
                            "url": "topic.html?topic=%d" % row[0]}
                return {"kind": "concept", "topic": None, "url": None}
            if unit.startswith("formula:"):
                fid = unit.split(":", 1)[1]
                row = con.execute("SELECT topic, section_h2 FROM "
                                  "formulas WHERE equation_id=? LIMIT 1",
                                  (fid,)).fetchone()
                if row:
                    return {"kind": "formula", "topic": row[0],
                            "equation_id": fid,
                            "url": "topic.html?topic=%d" % row[0]}
                return {"kind": "formula", "topic": None, "url": None}
            return None
        except (ValueError, IndexError):
            return None
        finally:
            con.close()

    def learn_progress(self):
        units = self.app.students.get_weak_units(self.student,
                                                 limit=1000)
        attempts = sum(u.get("attempt_count", 0) for u in units)
        correct_n = 0
        last = ""
        for u in units:
            try:
                h = self.app.students.get_unit_history(
                    self.student, u["knowledge_unit_id"])
            except Exception:  # noqa: BLE001
                continue
            st = h.get("state") or {}
            correct_n += st.get("correct_count", 0)
            if st.get("last_attempt", "") > last:
                last = st.get("last_attempt", "")
        recent = self.app.students.get_recent_attempts(
            self.student, limit=5)
        return {"attempts": attempts, "correct": correct_n,
                "units": len(units), "last_activity": last,
                "recent": recent}

    # ----- errors humans (taules del propi backend) -----
    @staticmethod
    def enrich_errors(errors, lang="ca"):
        li = 0 if lang == "ca" else 1
        out = []
        for e in errors or []:
            t = e.get("type", "")
            label = ERROR_HUMAN.get(t, (t, t))[li] if t else ""
            hint = FIX_HINT.get(t, _FALLBACK_HINT)[li]
            band = BAND_HUMAN.get(e.get("severity", ""),
                                  (e.get("severity", ""),) * 2)[li]
            out.append({**e, "label": label, "hint": hint, "band": band})
        return out

    # ----- sessions demo (efímeres, servidor; dict compartit amb lock) -----
    def _get(self, tok):
        with self._lock:
            return self.sessions[tok]["practice"]

    def _put(self, tok, sess):
        with self._lock:
            self.sessions[tok]["practice"] = sess

    def _token(self, ck):
        c = cookies.SimpleCookie()
        try:
            c.load(ck or "")
        except Exception:  # noqa: BLE001 - cookie malformada
            pass
        tok = c.get("sm_session")
        tok = tok.value if tok else ""
        with self._lock:
            if tok not in self.sessions:
                tok = secrets.token_hex(12)
                self.sessions[tok] = {"student": self.student,
                                      "practice": None}
        return tok

    def _ctx(self, workflow, lang="ca"):
        return self.app.create_context(self.student, workflow, lang)

    # ----- exam (F10 -> F7, xsid explícit, el navegador no guarda) -----
    # Configuració només amb opcions suportades pel contracte real.
    @staticmethod
    def _exam_spec(body):
        from app.exam.models import EXAM_KINDS
        from app.examiner.models import DIFFICULTIES, QUESTION_TYPES
        kind = body.get("exam_kind", "MOCK_EXAM")
        if kind not in EXAM_KINDS:
            raise AppError("VALIDATION_ERROR", "exam_kind no suportat")
        topics = body.get("topics", [2])
        if not isinstance(topics, list) or not topics or any(
                not isinstance(t, int) or t < 1 or t > 10
                for t in topics):
            raise AppError("VALIDATION_ERROR", "topics invàlids")
        count = body.get("question_count", 2)
        if not isinstance(count, int) or count < 1 or count > 50:
            raise AppError("VALIDATION_ERROR", "question_count invàlid")
        types = {}
        if body.get("question_type"):
            if body["question_type"] not in QUESTION_TYPES:
                raise AppError("VALIDATION_ERROR", "tipus no suportat")
            types = {body["question_type"]: count}
        difficulty = {}
        if body.get("difficulty"):
            if body["difficulty"] not in DIFFICULTIES:
                raise AppError("VALIDATION_ERROR",
                               "dificultat no suportada")
            difficulty = {body["difficulty"]: 1.0}
        dur = body.get("duration_seconds")
        if dur is not None and (not isinstance(dur, int) or dur < 1):
            raise AppError("VALIDATION_ERROR", "durada invàlida")
        seed = body.get("seed", 0)
        if not isinstance(seed, int) or seed < 0:
            raise AppError("VALIDATION_ERROR", "seed invàlid")
        title = body.get("title", "")
        if not isinstance(title, str):
            raise AppError("VALIDATION_ERROR", "títol invàlid")
        return {"title": title or "Examen T%s" % ("/".join(
            str(t) for t in topics)), "version": "1", "seed": seed,
            "duration_seconds": dur, "question_count": count,
            "topics": topics, "types": types, "difficulty": difficulty,
            "exam_kind": kind}
    # Ownership: la comprova el propi domini (get_answers/_check_student
    # → NOT_FOUND). El bridge no reimplementa res; només propaga.
    # Metadades de creació (títol/kind) efímeres de servidor demo.
    def exam_state(self, xsid, lang="ca"):
        exf = self.flows["exam"]
        result = exf.state(
            self._ctx("EXAM", lang),
            self.app.create_session(self.student, "EXAM",
                                    nonce=secrets.token_hex(6)), xsid)
        data = result["data"]
        sess = data["session"]
        exam = data["exam"]
        return {
            "session_id": xsid,
            "exam_id": sess["exam_id"],
            "title": exam["title"],
            "exam_kind": sess["exam_kind"],
            "status": sess["status"],
            "started_at": sess.get("started_at", "") or "",
            "expires_at": sess.get("expires_at", "") or "",
            "submitted_at": sess.get("submitted_at", "") or "",
            "duration_seconds": sess.get("duration_seconds"),
            "question_count": exam["question_count"],
            "topics": exam["topics"],
            "provenance": {"versions": exam["versions"],
                            "quality": exam["quality"]},
            "snapshot": {
                "immutable": True,
                "version": exam["version"],
                "instances": data["instances"],
            },
            "answers": {str(pos): {"answer": answer["answer"],
                                    "version": answer["version"]}
                        for pos, answer in data["answers"].items()},
        }

    @staticmethod
    def _project_review(data):
        """Apply the presentation whitelist for a REAL_EXAM review.

        F7 owns the policy and computes the feedback.  The bridge only
        prevents fields that the effective blind policy marks unavailable
        from crossing the HTTP boundary.
        """
        out = dict(data)
        is_real = data.get("exam_kind") == "REAL_EXAM"
        questions = []
        for question in data.get("questions", []) or []:
            item = dict(question)
            feedback = dict(item.get("feedback") or {})
            if is_real:
                item.pop("prompt", None)
                item.pop("options", None)
                feedback["correct_answer"] = None
                feedback["solution"] = None
                feedback["formula"] = None
                provenance = dict(feedback.get("provenance") or {})
                provenance.pop("provider", None)
                provenance.pop("model", None)
                feedback["provenance"] = provenance
            formula = feedback.get("formula")
            if isinstance(formula, dict) and formula.get("latex"):
                formula = dict(formula)
                formula["html"] = render_latex(formula["latex"])
                feedback["formula"] = formula
            item["feedback"] = feedback
            questions.append(item)
        out["questions"] = questions
        return out

    @staticmethod
    def _project_result(result):
        """Public result DTO; question/correction internals stay server-side."""
        keys = ("session_id", "exam_id", "title", "exam_kind",
                "origin_status", "status", "started_at", "submitted_at",
                "total_points", "earned_points", "optional_points",
                "optional_earned", "percentage", "question_count",
                "answered_count", "blank_count", "correct_count",
                "partial_count", "incorrect_count", "review_count",
                "graded_at")
        out = {k: result.get(k) for k in keys}
        out["provenance"] = {
            "exam_version": result.get("exam_version", ""),
            "scoring_policy_id": result.get("scoring_policy_id", ""),
            "scoring_policy_version": result.get(
                "scoring_policy_version", "")}
        out["questions"] = [{k: q.get(k) for k in
                             ("position", "points_available", "points_earned",
                              "status", "blank", "graded_at")}
                            for q in result.get("questions", [])]
        return out

    # ----- router pur (testeable sense xarxa) -----
    def route(self, method, path, query=None, body=None, cookie="",
              headers=None):
        query = query or {}
        body = body or {}
        lang = body.get("language", query.get("language", "ca"))
        if lang not in ("ca", "es"):
            lang = "ca"
        tok = self._token(cookie)
        with self._lock:
            csrf = self.sessions[tok].setdefault("csrf",
                                                 secrets.token_hex(24))
        secure = "; Secure" if os.environ.get("SM_TLS") == "1" else ""
        set_cookie = "\n".join([
            "sm_session=%s; Path=/; SameSite=Strict; HttpOnly%s" % (
                tok, secure),
            "sm_csrf=%s; Path=/; SameSite=Strict%s" % (csrf, secure)])

        if method == "GET" and path == "/api/health":
            checks = {"kb": Path(self.kb).is_file(),
                      "index": Path(self.index).exists(),
                      "student_db": True}
            ok = all(checks.values())
            from app.cli import _version
            return (200 if ok else 503), {
                "status": "ok" if ok else "degraded",
                "version": _version(), "checks": checks}, set_cookie
        if method == "GET" and path == "/api/session":
            return 200, {"csrf": csrf, "student": self.student}, set_cookie

        # CSRF double-submit: només s'aplica quan hi ha capçaleres reals
        # (Handler sempre en passa; les crides directes de test que no
        # exerceixen CSRF passen headers=None i queden exemptes).
        if headers is not None and method == "POST" \
                and path.startswith("/api/"):
            if (headers or {}).get("X-CSRF-Token") != csrf:
                return 403, {"ok": False, "code": "CSRF",
                             "message": "CSRF"}, set_cookie
        try:
            if method == "GET" and path == "/api/study/topics":
                return 200, {"topics": self.kb_topics()}, set_cookie
            if method == "GET" and path == "/api/documents":
                raw_topic = query.get("topic")
                topic = None
                if raw_topic not in (None, ""):
                    try:
                        topic = int(raw_topic)
                    except (TypeError, ValueError):
                        raise AppError("VALIDATION_ERROR", "tema invàlid")
                    if topic < 1:
                        raise AppError("VALIDATION_ERROR", "tema invàlid")
                return 200, {"documents": self.documents_catalog(topic),
                             "source": "COURSE_SOURCE"}, set_cookie
            if method == "GET" and path == "/api/calendar":
                return 200, self.calendar.read(), set_cookie
            if method == "GET" and path == "/api/study/documents":
                return 200, {"documents": self.kb_documents(
                    int(query.get("topic", 0)), query.get("doc_id"))}, set_cookie
            if method == "GET" and path == "/api/study/sections":
                return 200, {"sections": self.kb_sections(
                    query.get("doc_id", ""))}, set_cookie
            if method == "GET" and path == "/api/study/content":
                c = self.kb_content(query.get("section_id", ""))
                if c is None:
                    raise AppError("NOT_FOUND", "secció inexistent")
                return 200, c, set_cookie
            if method == "GET" and path == "/api/study/next":
                recs = self.flows["adaptive"].recommend(
                    self._ctx("ADAPTIVE_PRACTICE", lang),
                    self.app.create_session(
                        self.student, "ADAPTIVE_PRACTICE", nonce="web"),
                    limit=1, seed=7)["data"]["recommendations"]
                return 200, {"recommendation": recs[0] if recs
                             else None}, set_cookie
            if method == "GET" and path == "/api/study/mastery":
                out = {}
                for t in range(1, 11):
                    try:
                        m = self.app.students.get_topic_mastery(
                            self.student, t)
                        out[str(t)] = {"score": m.get("score"),
                                       "attempts": m.get(
                                           "attempt_count")}
                    except Exception:  # noqa: BLE001 - sense historial
                        out[str(t)] = None
                return 200, {"mastery": out}, set_cookie
            if method == "GET" and path == "/api/learn/priorities":
                try:
                    lim = max(1, min(10, int(
                        query.get("limit", 5))))
                except ValueError:
                    lim = 5
                return 200, {"priorities": self.learn_priorities(
                    lim, lang)}, set_cookie
            if method == "GET" and path == "/api/learn/progress":
                return 200, self.learn_progress(), set_cookie
            if method == "GET" and path == "/api/learn/unit":
                unit = query.get("unit", "")
                if not unit:
                    raise AppError("VALIDATION_ERROR", "unit buida")
                h = self.app.students.get_unit_history(
                    self.student, unit)
                if h.get("state") is None:
                    return 200, {"unit": unit, "state": None,
                                 "events": [], "locate": None}, \
                        set_cookie
                st = dict(h["state"])
                st["status_label"] = STATUS_LABEL.get(
                    st.get("status", ""), st.get("status", ""))
                errs = [{"type": t, "count": n, "label": ERROR_HUMAN.get(
                    t, (t, t))[0 if lang == "ca" else 1]}
                    for t, n in sorted(
                        (st.get("error_counts") or {}).items())]
                return 200, {"unit": unit, "state": st,
                             "events": h.get("events", []),
                             "errors": errs,
                             "locate": self.learn_locate(unit)}, \
                    set_cookie
            if method == "GET" and path == "/api/learn/locate":
                return 200, {"locate": self.learn_locate(
                    query.get("unit", ""))}, set_cookie
            if method == "POST" and path == "/api/learn/start":
                item = body.get("item")
                if not isinstance(item, dict) or not item.get(
                        "knowledge_unit_id"):
                    raise AppError("VALIDATION_ERROR", "item invàlid")
                r = self.flows["adaptive"].generate(
                    self._ctx("ADAPTIVE_PRACTICE", lang),
                    self.app.create_session(
                        self.student, "ADAPTIVE_PRACTICE",
                        nonce=secrets.token_hex(6)),
                    item, seed=int(body.get("seed", 7)))
                sess = self.app.create_session(
                    self.student, "PRACTICE",
                    nonce=secrets.token_hex(6))
                sess.touch({"kind": "question",
                            "id": r["data"]["question"]["question_id"]})
                self._put(tok, sess.to_dict())
                return 200, {"question": r["data"]["question"]}, \
                    set_cookie
            if method == "POST" and path == "/api/tutor/ask":
                q = body.get("query", "")
                r = self.flows["tutor"].ask(
                    self._ctx("TUTOR", lang), q,
                    top_k=int(body.get("top_k", 5)))
                return 200, r["data"], set_cookie
            if method == "POST" and path == "/api/practice/start":
                sess = self.app.create_session(
                    self.student, "PRACTICE",
                    nonce=secrets.token_hex(6))
                kw = {"topic": int(body.get("topic", 1))}
                for k in ("question_type", "section", "formula_id",
                          "difficulty"):
                    if body.get(k):
                        kw[k] = body[k]
                kw["seed"] = int(body.get("seed", 0))
                r = self.flows["practice"].start(
                    self._ctx("PRACTICE", lang), sess, **kw)
                self._put(tok, r["data"]["session"])
                return 200, {"question": r["data"]["question"]}, set_cookie
            if method == "POST" and path == "/api/practice/submit":
                ps = self._get(tok)
                if not ps:
                    raise AppError("STATE_ERROR", "sin pregunta activa")
                sess = ApplicationSession.from_dict(ps)
                r = self.flows["practice"].submit_answer(
                    self._ctx("PRACTICE", lang), sess,
                    str(body.get("answer", "")),
                    attempt_id=str(body.get("attempt_id", "")))
                self._put(tok, r["data"]["session"])
                res = dict(r["data"]["result"])
                res["errors"] = self.enrich_errors(res.get("errors"),
                                                   lang)
                return 200, {"result": res,
                             "attempt_id": r["data"]["result"].get(
                                 "attempt_id", "")}, set_cookie
            if method == "GET" and path == "/api/practice/question":
                ps = self._get(tok)
                if not ps:
                    raise AppError("STATE_ERROR", "sin pregunta activa")
                r = self.flows["practice"].get_question(
                    self._ctx("PRACTICE", lang),
                    ApplicationSession.from_dict(ps))
                return 200, r["data"], set_cookie
            if method == "POST" and path == "/api/practice/result":
                ps = self._get(tok)
                if not ps:
                    raise AppError("STATE_ERROR", "sin pregunta activa")
                units = body.get("units", [])
                r = self.flows["practice"].get_result(
                    self._ctx("PRACTICE", lang),
                    ApplicationSession.from_dict(ps), units)
                return 200, r["data"], set_cookie
            if method == "POST" and path == "/api/practice/complete":
                ps = self._get(tok)
                if not ps:
                    raise AppError("STATE_ERROR", "sin pregunta activa")
                r = self.flows["practice"].complete(
                    self._ctx("PRACTICE", lang),
                    ApplicationSession.from_dict(ps))
                self._put(tok, r["data"]["session"])
                return 200, {"session": r["data"]["session"]}, set_cookie
            if method == "POST" and path == "/api/exam/create":
                exf = self.flows["exam"]
                c = self._ctx("EXAM", lang)
                sess = self.app.create_session(
                    self.student, "EXAM", nonce=secrets.token_hex(6))
                spec = self._exam_spec(body)
                r = exf.configure(c, sess, spec)
                xsid = r["data"]["exam_session"]["session_id"]
                state = self.exam_state(xsid, lang)
                return 200, {"exam_session": {"session_id": xsid},
                             "exam": {"exam_id": state["exam_id"],
                                      "title": state["title"],
                                      "kind": state["exam_kind"]},
                              "state": state}, set_cookie
            if method == "POST" and path == "/api/exam/start":
                exf = self.flows["exam"]
                c = self._ctx("EXAM", lang)
                sess = self.app.create_session(
                    self.student, "EXAM", nonce=secrets.token_hex(6))
                r = exf.start(c, sess, str(body.get("exam_session_id")),
                              now=str(body.get("now", "")))
                return 200, {"started": r["data"]["started"],
                              "state": self.exam_state(
                                  str(body.get("exam_session_id")), lang)}, \
                    set_cookie
            if method == "GET" and path == "/api/exam/state":
                return 200, self.exam_state(
                    str(query.get("exam_session_id", "")), lang), set_cookie
            if method == "GET" and path == "/api/exam/question":
                exf = self.flows["exam"]
                c = self._ctx("EXAM", lang)
                sess = self.app.create_session(
                    self.student, "EXAM", nonce=secrets.token_hex(6))
                r = exf.get_question(
                    c, sess, str(query.get("exam_session_id", "")),
                    int(query.get("position", 0)),
                    now=str(query.get("now", "")))
                return 200, {"question": r["data"]["question"]}, \
                    set_cookie
            if method == "POST" and path == "/api/exam/save":
                exf = self.flows["exam"]
                c = self._ctx("EXAM", lang)
                sess = self.app.create_session(
                    self.student, "EXAM", nonce=secrets.token_hex(6))
                pos = body.get("position")
                if not isinstance(pos, int) or pos < 0:
                    raise AppError("VALIDATION_ERROR",
                                   "position inválida")
                r = exf.save_answer(
                    c, sess, str(body.get("exam_session_id", "")),
                    pos, str(body.get("answer", "")),
                    now=str(body.get("now", "")))
                return 200, {"saved": r["data"]["saved"]}, set_cookie
            if method == "POST" and path == "/api/exam/submit":
                exf = self.flows["exam"]
                c = self._ctx("EXAM", lang)
                sess = self.app.create_session(
                    self.student, "EXAM", nonce=secrets.token_hex(6))
                r = exf.submit(c, sess,
                               str(body.get("exam_session_id", "")),
                               now=str(body.get("now", "")))
                return 200, {"submitted": r["data"]["submitted"],
                              "state": self.exam_state(
                                  str(body.get("exam_session_id")), lang) \
                             }, set_cookie
            if method == "POST" and path == "/api/exam/grade":
                exf = self.flows["exam"]
                c = self._ctx("EXAM", lang)
                sess = self.app.create_session(
                    self.student, "EXAM", nonce=secrets.token_hex(6))
                r = exf.grade(c, sess,
                              str(body.get("exam_session_id", "")),
                              now=str(body.get("now", "")))
                return 200, {"result": r["data"]["result"]}, set_cookie
            if method == "GET" and path == "/api/exam/result":
                rf = self.flows["review"]
                c = self._ctx("REVIEW", lang)
                sess = self.app.create_session(
                    self.student, "REVIEW", nonce=secrets.token_hex(6))
                r = rf.get_result(
                    c, sess, str(query.get("exam_session_id", "")))
                return 200, self._project_result(r["data"]), set_cookie
            if method == "GET" and path == "/api/exam/review":
                rf = self.flows["review"]
                c = self._ctx("REVIEW", lang)
                sess = self.app.create_session(
                    self.student, "REVIEW", nonce=secrets.token_hex(6))
                r = rf.get_review(
                    c, sess, str(query.get("exam_session_id", "")))
                return 200, self._project_review(r["data"]), set_cookie
            if method == "GET" and path == "/api/exam/review_question":
                rf = self.flows["review"]
                c = self._ctx("REVIEW", lang)
                sess = self.app.create_session(
                    self.student, "REVIEW", nonce=secrets.token_hex(6))
                r = rf.get_question_review(
                    c, sess, str(query.get("exam_session_id", "")),
                    int(query.get("position", 0)))
                # The question-review workflow returns the question DTO
                # itself, so recover its projected feedback without changing
                # the response shape.
                if r["data"].get("feedback") is not None:
                    projected = self._project_review({
                        "exam_kind": self.exam_state(
                            str(query.get("exam_session_id", "")), lang)[
                                "exam_kind"],
                        "questions": [r["data"]]})
                    r["data"]["feedback"] = projected["questions"][0][
                        "feedback"]
                return 200, r["data"], set_cookie
            if method == "GET" and path == "/api/exam/mastery":
                rf = self.flows["review"]
                c = self._ctx("REVIEW", lang)
                sess = self.app.create_session(
                    self.student, "REVIEW", nonce=secrets.token_hex(6))
                r = rf.get_mastery_view(
                    c, sess, str(query.get("exam_session_id", "")))
                return 200, r["data"], set_cookie
            if method == "GET" and path == "/api/exam/mine":
                r = self.flows["exam"].list_mine(
                    self._ctx("EXAM", lang),
                    self.app.create_session(self.student, "EXAM",
                                            nonce=secrets.token_hex(6)))
                return 200, r["data"], set_cookie
            if method == "GET" and path == "/api/exam/history":
                r = self.flows["exam"].history(
                    self._ctx("EXAM", lang),
                    self.app.create_session(self.student, "EXAM",
                                            nonce=secrets.token_hex(6)))
                return 200, r["data"], set_cookie
            raise AppError("NOT_FOUND", "ruta inexistent")
        except AppError as e:
            return STATUS.get(e.code, 500), {"ok": False, "code": e.code,
                                             "message": e.message}, set_cookie
        except (KeyError, ValueError, TypeError, AttributeError):
            return 400, {"ok": False, "code": "VALIDATION_ERROR",
                         "message": "petició invàlida"}, set_cookie
        except Exception as e:  # noqa: BLE001 - frontera final: sense fuites
            from app.exam.models import ExamError
            if isinstance(e, ExamError):
                try:
                    raise _map_app_error(e)
                except AppError as m:
                    return STATUS.get(m.code, 500), {
                        "ok": False, "code": m.code,
                        "message": m.message}, set_cookie
                except Exception:  # noqa: BLE001
                    pass
            return 500, {"ok": False, "code": "INTERNAL_ERROR",
                         "message": "error intern"}, set_cookie


_MIME = {".html": "text/html; charset=utf-8",
         ".css": "text/css; charset=utf-8",
         ".js": "text/javascript; charset=utf-8",
         ".json": "application/json",
         ".svg": "image/svg+xml", ".png": "image/png"}


class Handler(BaseHTTPRequestHandler):
    # Un Bridge (wiring propi) per fil: les connexions SQLite no es
    # comparteixen entre fils (P2-3/B6). Les sessions demo comparteixen
    # dict amb lock. Configurat a main().
    config = None  # type: dict
    _local = None

    @classmethod
    def thread_bridge(cls):
        import threading
        if cls._local is None:
            cls._local = threading.local()
        b = getattr(cls._local, "bridge", None)
        if b is None:
            b = Bridge(sessions=cls.config["sessions"],
                       lock=cls.config["lock"], **cls.config["kw"])
            cls._local.bridge = b
        return b

    def log_message(self, *a):  # silenciós
        pass

    def _send(self, status, payload, cookie="", ctype="application/json"):
        raw = payload if isinstance(payload, bytes) else json.dumps(
            payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        if cookie:
            for line in cookie.split("\n"):
                self.send_header("Set-Cookie", line)
        self.end_headers()
        self.wfile.write(raw)

    def _static(self, path):
        target = (WEB / path.lstrip("/")).resolve()
        if WEB not in target.parents and target != WEB:
            return self._send(404, {"ok": False}, "")
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file() or target.suffix not in _MIME:
            return self._send(404, {"ok": False}, "")
        return self._send(200, target.read_bytes(), "",
                          _MIME[target.suffix])

    def _api(self):
        url = urllib.parse.urlparse(self.path)
        query = {k: v[0] for k, v in
                 urllib.parse.parse_qs(url.query).items()}
        body = {}
        if self.command == "POST":
            limit = int(os.environ.get("SM_MAX_BODY_BYTES", "1048576"))
            try:
                n = int(self.headers.get("Content-Length", 0))
            except ValueError:
                n = 0
            if n > limit:
                return self._send(413, {"ok": False,
                                        "code": "PAYLOAD_TOO_LARGE",
                                        "message": "cos massa gran"}, "")
            raw = self.rfile.read(n) if n > 0 else b""
            if raw:
                try:
                    body = json.loads(raw.decode("utf-8"))
                except ValueError:
                    return self._send(400, {"ok": False,
                                            "code": "VALIDATION_ERROR",
                                            "message": "JSON invàlid"}, "")
            if not isinstance(body, dict):
                return self._send(400, {"ok": False,
                                        "code": "VALIDATION_ERROR",
                                        "message": "JSON invàlid"}, "")
        import time
        from app import logsetup
        t0 = time.perf_counter()
        try:
            status, payload, cookie = self.thread_bridge().route(
                self.command, url.path, query, body,
                self.headers.get("Cookie", ""), headers=dict(self.headers))
        except Exception:
            logsetup.exception("route fallo: %s %s" % (self.command, url.path))
            status, payload, cookie = 500, {"ok": False,
                                            "code": "INTERNAL_ERROR",
                                            "message": "error intern"}, ""
        logsetup.request(self.command, url.path, status,
                         (time.perf_counter() - t0) * 1000)
        self._send(status, payload, cookie)

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self._api()
        return self._static(urllib.parse.urlparse(self.path).path or "/")

    def do_POST(self):
        if self.path.startswith("/api/"):
            return self._api()
        return self._send(404, {"ok": False}, "")


def main(argv=None) -> int:
    import argparse
    import tempfile
    from app.env import load_env
    load_env(os.environ.get("SM_ENV_FILE"))            # ./.env si no s'indica
    load_env(sm_paths.config_dir() / ".env")            # cerca de reserva
    from app import logsetup
    logsetup.configure()
    ap = argparse.ArgumentParser(description="Servidor presentació B2")
    ap.add_argument("--host", default=os.environ.get("SM_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int,
                    default=int(os.environ.get("SM_PORT", "8901")))
    ap.add_argument("--data-dir", default=os.environ.get("SM_DATA_DIR", ""))
    ap.add_argument("--calendar",
                    default=os.environ.get("COURSE_CALENDAR_PATH", ""),
                    help="font JSON versionada de calendari (opcional)")
    args = ap.parse_args(argv)
    data = args.data_dir or tempfile.mkdtemp(prefix="sm-web-")
    import threading
    Handler.config = {"kw": {}, "sessions": {}, "lock": threading.Lock()}
    Handler.config["kw"] = {"workdir": data,
                             "calendar_path": args.calendar or None}
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    srv.timeout = int(os.environ.get("SM_REQUEST_TIMEOUT", "30"))
    print("Sistemes de Mesura a http://%s:%d (dades: %s)"
          % (args.host, args.port, data))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
