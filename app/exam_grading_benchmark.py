"""Benchmark Exam Grading Bloque 3 (determinista, sin LLM para la nota).

24 casos (G01-G24): correccion F5 real por tipo, scoring entero HALF_UP,
agregacion, idempotencia triple, mastery unica, anti-leak, aislamiento.
Sesiones+resultados en student DB temporal; pool generado determinista
en questions DB temporal (KB/indice reales solo en lectura; GENDB
real jamas se toca: sin copia siquiera, el pool es autocontenido).

Uso: python3 app/exam_grading_benchmark.py [--write] [--out P]
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.exam.grading import (  # noqa: E402
    ExamGradingService,
    avail_thou,
    pct_hundredths,
    thou,
)
from app.exam.service import ExamSessionService  # noqa: E402
from app.examiner.service import ExaminerEngine  # noqa: E402
from app.retrieval.service import RetrievalService  # noqa: E402
from app.student import mastery as MAS  # noqa: E402
from app.student.models import MasteryEvent  # noqa: E402
from app.student.service import StudentService  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
INDEX = str(ROOT / "data" / "index")
EVALDB = str(ROOT / "data" / "evaluation" / "eval.sqlite")
CHUNKS = str(ROOT / "data" / "processed" / "chunks.jsonl")
MANIFEST = str(ROOT / "data" / "source_manifest.json")
GENDB = str(ROOT / "data" / "generated" / "questions.sqlite")
CASES = ROOT / "data" / "evaluation" / "exam_grading_benchmark.jsonl"
RESULTS = ROOT / "data" / "evaluation" / "exam_grading_results.json"

_retriever = None


def load_cases() -> list[dict]:
    out = []
    for line in CASES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _sha(p: str) -> str:
    import hashlib
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _engine(tmp: Path):
    global _retriever
    if _retriever is None:
        _retriever = RetrievalService(KB, INDEX)
    return ExaminerEngine(_retriever, KB, str(tmp / "pool.sqlite"))


def _pool_body(tmp: Path, qid: str) -> dict:
    con = sqlite3.connect("file:%s?mode=ro" % (tmp / "pool.sqlite"), uri=True)
    try:
        return json.loads(con.execute("SELECT body_json FROM questions "
                                      "WHERE question_id=?", (qid,)).fetchone()[0])
    finally:
        con.close()


def _resolve_answer(tmp: Path, qid: str, spec) -> str:
    if isinstance(spec, str):
        return spec
    mode = spec.get("mode", "literal")
    if mode == "literal":
        return spec.get("value", "")
    if mode == "blank":
        return ""
    body = _pool_body(tmp, qid)
    if mode == "correct":
        return body.get("correct_answer", "")
    if mode == "wrong_tf":
        ca = body.get("correct_answer", "")
        return "F" if ca == "V" else "V"
    if mode == "mcq_correct":
        for i, o in enumerate(body.get("options", [])):
            if o.get("correct"):
                return chr(65 + i) + ")"
        raise AssertionError("sin opcion correcta: %s" % qid)
    raise ValueError("modo respuesta desconocido: %r" % mode)


def _services(tmp: Path):
    sdb = str(tmp / "student.sqlite")
    qdb = str(tmp / "pool.sqlite")
    exam = ExamSessionService(sdb, qdb, KB)
    stu = StudentService(KB, qdb, sdb)
    return exam, stu, ExamGradingService(exam, stu)


def _gen_pool(tmp: Path, pool: list[dict]) -> None:
    eng = _engine(tmp)
    for g in pool:
        kw = {"topic": g["topic"], "question_type": g["type"],
              "seed": g["seed"]}
        if g.get("formula_id"):
            kw["formula_id"] = g["formula_id"]
        q, log = eng.generate(**kw)
        assert q is not None, "pool no generable: %r (%r)" % (kw, log)
        assert q.validation.status == "VALID", q.question_id


def run_case(case: dict, tmp: Path) -> tuple[bool, dict]:
    method = case["method"]
    fails: list[str] = []
    detail: dict = {"case_id": case["case_id"]}
    if method == "grade":
        return _run_grade(case, tmp, fails, detail)
    if method == "units":
        return _run_units(case, fails, detail)
    if method == "invalid":
        return _run_invalid(case, tmp, fails, detail)
    if method == "isolate":
        return _run_isolate(case, tmp, fails, detail)
    raise ValueError("metodo desconocido: %r" % method)


def _check(cond: bool, msg: str, fails: list[str]) -> None:
    if not cond:
        fails.append(msg)


def _run_grade(case, tmp, fails, detail):
    _gen_pool(tmp, case.get("pool", []))
    exam, stu, grading = _services(tmp)
    sid = case.get("student", "alu-1")
    call = case.get("call", {})
    expect = case.get("expect", {})
    out = exam.store_blueprint(case["blueprint"])
    exam.prepare_exam(out["exam_id"])
    sess = exam.create_session(out["exam_id"], sid)["session_id"]
    exam.prepare_session(sess, sid)
    exam.start_session(sess, sid, now=call.get("start", ""))
    if case.get("pre_submit_leak_checks"):
        for fn, args in (("get_result", (sess, sid)),
                         ("get_question_result", (sess, 0, sid))):
            try:
                getattr(grading, fn)(*args)
                fails.append("%s en IN_PROGRESS debió fallar" % fn)
            except Exception as e:  # noqa: BLE001
                _check("RESULT_NOT_AVAILABLE" in str(e),
                       "%s: %r sin marcador" % (fn, str(e)[:120]), fails)
    for sv in case.get("saves", []):
        qid = _question_at(exam, sess, sid, sv["position"])
        ans = _resolve_answer(tmp, qid, sv["answer"])
        exam.save_answer(sess, sv["position"], ans, sid,
                         now=sv.get("now", ""))
    if "submit_error" in expect:
        try:
            exam.submit_session(sess, sid, now=call.get("submit", ""))
            fails.append("submit debió fallar")
        except Exception as e:  # noqa: BLE001
            _check(expect["submit_error"] in str(e),
                   "submit: %r sin %r" % (str(e)[:150],
                                          expect["submit_error"]), fails)
            detail["submitted"] = {"rejected": str(e)[:150]}
    else:
        sub = exam.submit_session(sess, sid, now=call.get("submit", ""))
        detail["submitted"] = {"status": sub["status"],
                               "submitted_at": sub["submitted_at"]}
        if "submitted_at" in expect:
            _check(sub["submitted_at"] == expect["submitted_at"],
                   "submitted_at %r != %r"
                   % (sub["submitted_at"], expect["submitted_at"]), fails)
    res = grading.grade(sess, sid, now=call.get("grade", ""))
    for _ in range(expect.get("extra_grades", 0)):
        res2 = grading.grade(sess, sid, now=call.get("grade2", call.get(
            "grade", "")))
        _check(res2 == res, "re-grade difiere", fails)
    detail["result"] = res
    _expect_result(res, expect.get("result", {}), fails)
    for qexp in expect.get("questions", []):
        hit = [q for q in res["questions"]
               if q["position"] == qexp["position"]]
        _check(bool(hit), "falta pregunta %r" % qexp["position"], fails)
        if hit:
            for k, v in qexp.items():
                if k == "position":
                    continue
                _check(hit[0].get(k) == v,
                       "q%d.%s=%r != %r" % (qexp["position"], k,
                                            hit[0].get(k), v), fails)
    for unit, mexp in expect.get("mastery", {}).items():
        got = stu.get_mastery(sid, unit)
        _check(got is not None, "sin mastery %s" % unit, fails)
        if got:
            for k, v in mexp.items():
                _check(got.get(k) == v,
                       "mastery %s.%s=%r != %r" % (unit, k, got.get(k), v),
                       fails)
    for err in expect.get("mastery_errors_contain", []):
        prof = stu.get_error_profile(sid)
        _check(prof.get(err, 0) > 0,
               "error %r ausente en perfil %r" % (err, prof), fails)
    if "stable_counts" in expect:
        got = _table_counts(exam)
        for k, v in expect["stable_counts"].items():
            _check(got.get(k) == v, "conteo %s=%r != %r"
                   % (k, got.get(k), v), fails)
        detail["counts"] = got
    if expect.get("leak_scan"):
        bad = _scan_leaks(res)
        _check(not bad, "fugas en resultado: %r" % bad, fails)
    if case.get("mirror"):
        _check_mirror(exam, grading, tmp, case, res, fails, detail)
    if case.get("isolation_check"):
        other = case["isolation_check"]["other"]
        try:
            grading.get_result(sess, other)
            fails.append("otro estudiante leyó resultado")
        except Exception as e:  # noqa: BLE001
            _check("otro estudiante" in str(e),
                   "aislamiento: %r" % str(e)[:120], fails)
        for unit in case["isolation_check"].get("units_absent", []):
            _check(stu.get_mastery(other, unit) is None,
                   "contaminación %s en %s" % (unit, other), fails)
        detail["isolation_ok"] = True
    if expect.get("provenance"):
        _check_provenance(exam, stu, sess, sid, res, fails, detail)
    if "session_status" in expect:
        _check(exam.session_status(sess)["status"]
               == expect["session_status"],
               "estado sesion != %r" % expect["session_status"], fails)
    return (not fails, {**detail, "fails": fails})


def _question_at(exam, sess, sid, position):
    for inst in exam.read_session(sess, sid)["instances"]:
        if inst["position"] == position:
            return inst["question_id"]
    raise AssertionError("sin instancia %r" % position)


def _check_mirror(exam, grading, tmp, case, res, fails, detail):
    """Segunda sesion, mismo examen, guardado en orden inverso."""
    m = case["mirror"]
    sid2 = m["student"]
    out = exam.store_blueprint(case["blueprint"])
    sess2 = exam.create_session(out["exam_id"], sid2)["session_id"]
    exam.prepare_session(sess2, sid2)
    exam.start_session(sess2, sid2, now="2026-09-05T10:00:00+00:00")
    for sv in reversed(case.get("saves", [])):
        qid = _question_at(exam, sess2, sid2, sv["position"])
        exam.save_answer(sess2, sv["position"],
                         _resolve_answer(tmp, qid, sv["answer"]), sid2,
                         now=sv.get("now", ""))
    exam.submit_session(sess2, sid2, now="2026-09-05T10:04:00+00:00")
    res2 = grading.grade(sess2, sid2, now="2026-09-05T10:05:00+00:00")

    def proj(r):
        return {"totals": (r["total_points"], r["earned_points"],
                           r["percentage"]),
                "counts": (r["question_count"], r["answered_count"],
                           r["blank_count"], r["correct_count"],
                           r["partial_count"], r["incorrect_count"]),
                "qs": sorted((q["status"], q["points_earned"]) for q in
                             r["questions"])}

    _check(proj(res2) == proj(res),
           "espejo difiere: %r vs %r" % (proj(res2), proj(res)), fails)
    detail["mirror_equal"] = proj(res2) == proj(res)


def _expect_result(res, expect, fails):
    for k, v in expect.items():
        if k == "counts":
            for ck, cv in v.items():
                _check(res.get(ck) == cv, "result.%s=%r != %r"
                       % (ck, res.get(ck), cv), fails)
        else:
            _check(res.get(k) == v, "result.%s=%r != %r"
                   % (k, res.get(k), v), fails)


def _table_counts(exam) -> dict:
    con = sqlite3.connect(exam.exams.path)
    try:
        return {t: con.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                for t in ("attempts", "corrections", "mastery_events")}
    finally:
        con.close()


def _scan_leaks(res: dict) -> list[str]:
    bad: list[str] = []
    deny = ("correct_answer", "expected_answer", "solution", "rubric",
            "criteria", "detected_errors", "claims", "options",
            "evidence_refs", "source_refs", "answer_key", "formula_application",
            "calculation", "hints", "prompt", "variables", "conditions")

    def walk(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in deny and "policy_versions" not in path:
                    bad.append("%s.%s" % (path, k))
                walk(v, "%s.%s" % (path, k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, "%s[%d]" % (path, i))

    walk(res)
    return bad


def _check_provenance(exam, stu, sess, sid, res, fails, detail):
    links = []
    con = sqlite3.connect(exam.exams.path)
    try:
        for q in res["questions"]:
            att = con.execute("SELECT question_id, exam_id, answer FROM "
                              "attempts WHERE attempt_id=?",
                              (q["attempt_id"],)).fetchone()
            _check(att is not None, "attempt ausente %s" % q["attempt_id"],
                   fails)
            if att:
                _check(att[0] == q["question_id"] and att[1] == res["exam_id"],
                       "attempt %s no enlaza" % q["attempt_id"], fails)
            cor = con.execute("SELECT body_json FROM corrections WHERE "
                              "attempt_id=? ORDER BY version DESC LIMIT 1",
                              (q["attempt_id"],)).fetchone()
            _check(cor is not None, "correction ausente %s" % q["attempt_id"],
                   fails)
            if cor:
                body = json.loads(cor[0])
                _check(body.get("correction_id") == q["correction_id"]
                       and body.get("exam_id") == res["exam_id"]
                       and body.get("session_id") == sess,
                       "correction %s sin provenance" % q["correction_id"],
                       fails)
            ev = con.execute("SELECT COUNT(*) FROM mastery_events WHERE "
                             "attempt_id=?", (q["attempt_id"],)).fetchone()[0]
            _check(ev >= 1, "sin mastery event %s" % q["attempt_id"], fails)
            links.append(q["attempt_id"])
    finally:
        con.close()
    detail["provenance_attempts"] = sorted(links)


def _run_units(case, fails, detail):
    outs = []
    for fn, args, want in [("thou", (0.05, 0.1), 1),
                           ("thou", (0.15, 0.1), 2),
                           ("thou", (8.5, 1.0), 850),
                           ("thou", (6.0, 1.0), 600),
                           ("thou", (7.19, 1.0), 719),
                           ("thou", (0.0, 2.5), 0),
                           ("avail_thou", (1.0,), 1000),
                           ("avail_thou", (2.5,), 2500),
                           ("pct_hundredths", (1, 20000), 1),
                           ("pct_hundredths", (3, 20000), 2),
                           ("pct_hundredths", (1450, 2000), 7250),
                           ("pct_hundredths", (1450, 3000), 4833),
                           ("pct_hundredths", (0, 1000), 0),
                           ("pct_hundredths", (5, 0), 0)]:
        got = {"thou": thou, "avail_thou": avail_thou,
               "pct_hundredths": pct_hundredths}[fn](*args)
        outs.append([fn, list(args), got])
        _check(got == want, "%s%r=%r != %r" % (fn, args, got, want), fails)
    detail["result"] = outs
    return (not fails, {**detail, "fails": fails})


def _run_invalid(case, tmp, fails, detail):
    from app.exam.service import ExamSessionService as _ES
    svc = _ES(str(tmp / "s.sqlite"), str(tmp / "q.sqlite"), KB)
    try:
        svc.store_blueprint(case["blueprint"])
        fails.append("store aceptó blueprint inválido")
    except Exception as e:  # noqa: BLE001
        _check(case["expect_error"] in str(e),
               "error %r no contiene %r" % (str(e)[:150],
                                            case["expect_error"]), fails)
        detail["result"] = {"rejected": str(e)[:150]}
    return (not fails, {**detail, "fails": fails})


def _run_isolate(case, tmp, fails, detail):
    targets = [KB, EVALDB, CHUNKS, MANIFEST]
    before = {t: _sha(t) for t in targets}
    before_gen = _gen_content()
    _gen_pool(tmp, case.get("pool", []))
    exam, stu, grading = _services(tmp)
    sid = case.get("student", "alu-1")
    out = exam.store_blueprint(case["blueprint"])
    exam.prepare_exam(out["exam_id"])
    sess = exam.create_session(out["exam_id"], sid)["session_id"]
    exam.prepare_session(sess, sid)
    exam.start_session(sess, sid, now="2026-09-05T10:00:00+00:00")
    for sv in case.get("saves", []):
        qid = _question_at(exam, sess, sid, sv["position"])
        exam.save_answer(sess, sv["position"],
                         _resolve_answer(tmp, qid, sv["answer"]), sid,
                         now=sv.get("now", ""))
    exam.submit_session(sess, sid, now="2026-09-05T10:04:00+00:00")
    grading.grade(sess, sid, now="2026-09-05T10:05:00+00:00")
    after = {t: _sha(t) for t in targets}
    bad = [Path(t).name for t in targets if before[t] != after[t]]
    gen_now = _gen_content()
    detail["result"] = {"matches": not bad, "gen_stable": gen_now
                        == before_gen, "checked": [Path(t).name
                                                   for t in targets]}
    _check(not bad, "hash cambio: %r" % bad, fails)
    _check(gen_now == before_gen, "GENDB cambio: %r" % (
        {k: (before_gen.get(k), gen_now.get(k)) for k in before_gen
         if before_gen.get(k) != gen_now.get(k)}), fails)
    return (not fails, {**detail, "fails": fails})


def _gen_content() -> dict:
    con = sqlite3.connect("file:%s?mode=ro" % GENDB, uri=True)
    try:
        return {"questions": con.execute(
            "SELECT COUNT(*) FROM questions").fetchone()[0],
            "exams": con.execute(
                "SELECT COUNT(*) FROM exams").fetchone()[0],
            "synthetic": con.execute(
                "SELECT COUNT(*) FROM questions WHERE question_id LIKE"
                " 'qm-%' OR question_id LIKE 'qb-%' OR question_id LIKE"
                " 'attex-%'").fetchone()[0],
            "origins": sorted(con.execute(
                "SELECT DISTINCT origin FROM questions").fetchall())}
    finally:
        con.close()


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    cases = load_cases()
    print("casos: %d" % len(cases))
    all_ok, details = True, []
    for case in cases:
        with tempfile.TemporaryDirectory(prefix="exam-grade-") as td:
            ok, detail = run_case(case, Path(td))
        details.append(detail)
        print(("PASS " if ok else "FAIL ") + case["case_id"] + " "
              + case.get("title", ""))
        for f in detail.get("fails", []):
            print("     - " + f)
        all_ok = all_ok and ok
    out = Path(args.out) if args.out else RESULTS
    if args.write or args.out:
        out.write_text(json.dumps(
            {"spec": "exam-spec-v1", "cases": details},
            ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        print("resultados en %s" % out)
    print("OK" if all_ok else "FALLOS")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
