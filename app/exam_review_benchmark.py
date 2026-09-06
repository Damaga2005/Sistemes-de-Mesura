"""Benchmark Exam Review Bloque 5 (determinista, sin LLM, sin writes).

36 casos (R01-R36): acceso por estado, seguridad/IDOR, anti-leak por
campo, correccion real por tipo, formulas canonicas, mastery read-only,
provider provenance, REAL_EXAM ciego, determinismo. Pool generado
determinista en DBs temporales (KB/indice reales solo en lectura;
GENDB real jamas se toca).

Uso: python3 app/exam_review_benchmark.py [--write] [--out P]
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.exam import review as RV  # noqa: E402
from app.exam.review_policy import effective_policy  # noqa: E402
from app.exam_grading_benchmark import (  # noqa: E402
    _engine,
    _gen_pool,
    _resolve_answer,
)
from app.exam.service import ExamSessionService  # noqa: E402
from app.exam.grading import ExamGradingService  # noqa: E402
from app.student.service import StudentService  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
INDEX = str(ROOT / "data" / "index")
EVALDB = str(ROOT / "data" / "evaluation" / "eval.sqlite")
CHUNKS = str(ROOT / "data" / "processed" / "chunks.jsonl")
MANIFEST = str(ROOT / "data" / "source_manifest.json")
GENDB = str(ROOT / "data" / "generated" / "questions.sqlite")
CASES = ROOT / "data" / "evaluation" / "exam_review_benchmark.jsonl"
RESULTS = ROOT / "data" / "evaluation" / "exam_review_results.json"


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


def _services(tmp: Path):
    sdb = str(tmp / "student.sqlite")
    qdb = str(tmp / "pool.sqlite")
    exam = ExamSessionService(sdb, qdb, KB)
    stu = StudentService(KB, qdb, sdb)
    grading = ExamGradingService(exam, stu)
    return exam, stu, grading, RV.ExamReviewService(exam, grading, stu, KB)


def _question_at(exam, sess, sid, position):
    for inst in exam.read_session(sess, sid)["instances"]:
        if inst["position"] == position:
            return inst["question_id"]
    raise AssertionError("sin instancia %r" % position)


def run_case(case: dict, tmp: Path) -> tuple[bool, dict]:
    method = case["method"]
    fails: list[str] = []
    detail: dict = {"case_id": case["case_id"]}
    if method == "review":
        return _run_review(case, tmp, fails, detail)
    if method == "units":
        return _run_units(case, tmp, fails, detail)
    if method == "isolate":
        return _run_isolate(case, tmp, fails, detail)
    raise ValueError("metodo desconocido: %r" % method)


def _check(cond: bool, msg: str, fails: list[str]) -> None:
    if not cond:
        fails.append(msg)


def _run_review(case, tmp, fails, detail):
    _gen_pool(tmp, case.get("pool", []))
    exam, stu, grading, rev = _services(tmp)
    sid = case.get("student", "alu-1")
    call = case.get("call", {})
    out = exam.store_blueprint(case["blueprint"])
    exam.prepare_exam(out["exam_id"])
    sess = exam.create_session(out["exam_id"], sid)["session_id"]
    exam.prepare_session(sess, sid)
    exam.start_session(sess, sid, now=call.get("start", ""))
    _run_probes(case.get("probes_in_progress", []), "in_progress",
                exam, stu, grading, rev, tmp, sess, sid, fails, detail)
    if case.get("cancel"):
        exam.cancel_session(sess, sid, now=case["cancel"])
    else:
        for sv in case.get("saves", []):
            qid = _question_at(exam, sess, sid, sv["position"])
            exam.save_answer(sess, sv["position"],
                             _resolve_answer(tmp, qid, sv["answer"]), sid,
                             now=sv.get("now", ""))
        if "submit_error" in case:
            try:
                exam.submit_session(sess, sid, now=call.get("submit", ""))
                fails.append("submit debió fallar")
            except Exception as e:  # noqa: BLE001
                _check(case["submit_error"] in str(e),
                       "submit: %r sin %r" % (str(e)[:150],
                                              case["submit_error"]), fails)
        elif not case.get("skip_submit"):
            exam.submit_session(sess, sid, now=call.get("submit", ""))
    _run_probes(case.get("probes_submitted", []), "submitted",
                exam, stu, grading, rev, tmp, sess, sid, fails, detail)
    if call.get("grade") is not None:
        grading.grade(sess, sid, now=call["grade"])
    _run_probes(case.get("probes_graded", []), "graded",
                exam, stu, grading, rev, tmp, sess, sid, fails, detail)
    if case.get("repeat_review"):
        try:
            a = rev.get_review(sess, sid)
            b = rev.get_review(sess, sid)
            _check(a == b, "review no determinista", fails)
            detail["repeat_equal"] = a == b
        except Exception as e:  # noqa: BLE001
            fails.append("repeat_review lanzó: %r" % e)
    return (not fails, {**detail, "fails": fails})


def _run_probes(probes, stage, exam, stu, grading, rev, tmp, sess, sid,
                fails, detail):
    for i, p in enumerate(probes):
        tag = "%s#%d(%s)" % (stage, i, p["call"])
        try:
            res = _exec_probe(p, exam, stu, grading, rev, tmp, sess, sid,
                              detail)
        except Exception as e:  # noqa: BLE001
            if "expect_error" in p:
                _check(p["expect_error"] in str(e),
                       "%s: %r sin %r" % (tag, str(e)[:150],
                                          p["expect_error"]), fails)
            else:
                fails.append("%s lanzó: %r" % (tag, e))
            continue
        if "expect_error" in p:
            fails.append("%s debió fallar (%s)" % (tag, p["expect_error"]))
            continue
        _expect_probe(res, p.get("expect", {}), tag, fails, tmp)


def _exec_probe(p, exam, stu, grading, rev, tmp, sess, sid, detail):
    call, args = p["call"], p.get("args", {})
    who = args.get("student", sid)
    if call == "get_result":
        return grading.get_result(sess, who)
    if call == "get_question_result":
        return grading.get_question_result(sess, args["position"], who)
    if call == "get_review":
        return rev.get_review(sess, who,
                              policy_version=args.get("policy_version", ""))
    if call == "get_review_question":
        return rev.get_review_question(sess, args["position"], who,
                                       policy_version=args.get(
                                           "policy_version", ""))
    if call == "get_mastery_view":
        return rev.get_mastery_view(who, sess,
                                    policy_version=args.get(
                                        "policy_version", ""))
    if call == "mastery_digest":
        out = _mastery_digest(stu, who)
        if p.get("save_as"):
            detail.setdefault("digests", {})[p["save_as"]] = out
        if p.get("same_as"):
            want = detail.get("digests", {}).get(p["same_as"])
            if want is None:
                raise AssertionError("sin digest guardado: %r" % p["same_as"])
            if out != want:
                raise AssertionError("digest cambio tras lecturas")
        return out
    if call == "policy":
        return effective_policy(args.get("kind", "MOCK_EXAM"),
                                args.get("version", ""))
    if call == "origin":
        return _origin_info(rev, exam, tmp, sess, sid, args)
    if call == "formula_check":
        return _formula_check(rev, exam, tmp, sess, sid)
    if call == "correction_shape":
        return _correction_shape(rev, exam, stu, tmp, sess, sid, args)
    raise ValueError("probe desconocida: %r" % call)


def _mastery_digest(stu, sid) -> dict:
    con = sqlite3.connect("file:%s?mode=ro" % stu.store.path, uri=True)
    try:
        n = con.execute("SELECT COUNT(*) FROM mastery_events WHERE "
                        "student_id=?", (sid,)).fetchone()[0]
        states = {}
        for uid, score, n_att, ok in con.execute(
                "SELECT knowledge_unit_id, score, attempt_count,"
                " correct_count FROM mastery_states WHERE student_id=?",
                (sid,)).fetchall():
            states[uid] = [score, n_att, ok]
    finally:
        con.close()
    return {"events": n, "states": states}


def _check_render_pair(tmp, t, fails, detail):
    """Mismo feedback en ca/es: solo literales humanos difieren."""
    from app.exam import review as _RV
    from app.exam.review_policy import effective_policy
    _gen_pool(tmp, t["pool"])
    exam, stu, grading, rev = _services(tmp)
    sid = "alu-1"
    out = exam.store_blueprint(t["blueprint"])
    exam.prepare_exam(out["exam_id"])
    sess = exam.create_session(out["exam_id"], sid)["session_id"]
    exam.prepare_session(sess, sid)
    exam.start_session(sess, sid, now="2026-09-05T10:00:00+00:00")
    qid = _question_at(exam, sess, sid, t["position"])
    exam.save_answer(sess, t["position"], t["answer"], sid,
                     now="2026-09-05T10:01:00+00:00")
    exam.submit_session(sess, sid, now="2026-09-05T10:04:00+00:00")
    grading.grade(sess, sid, now="2026-09-05T10:05:00+00:00")
    fb_ca = rev.get_review_question(sess, t["position"], sid)["feedback"]
    data = exam.read_session(sess, sid)
    res = grading.get_result(sess, sid)
    q = [x for x in res["questions"] if x["position"] == t["position"]][0]
    corr = rev._correction_body(q["correction_id"])
    body = stu.correction.load_question(q["question_id"])
    ans = data["answers"][t["position"]]["answer"]
    par = dict(effective_policy("MOCK_EXAM")["parameters"])
    par["feedback_lang"] = "es"
    fb_es = _RV.build_feedback(corr, body, params=par, answer=ans,
                               formula_lookup=rev._formula_record)
    exp = t["expect"]
    _check(fb_ca.get("explanation") == exp["ca_explanation"],
           "ca %r" % fb_ca.get("explanation"), fails)
    _check(fb_es.get("explanation") == exp["es_explanation"],
           "es %r" % fb_es.get("explanation"), fails)
    if exp.get("latex_stable"):
        _check(fb_ca.get("formula", {}).get("latex")
               == fb_es.get("formula", {}).get("latex") and bool(
                   fb_ca.get("formula", {}).get("latex")),
               "latex inestable o ausente", fails)
    if exp.get("hints_differ"):
        ca_h = [g["hint"] for g in fb_ca.get("guidance", [])]
        es_h = [g["hint"] for g in fb_es.get("guidance", [])]
        _check(bool(ca_h) and ca_h != es_h, "hints no difieren", fails)
    detail["render_pair"] = {"ca": fb_ca.get("explanation"),
                             "es": fb_es.get("explanation")}


def _origin_info(rev, exam, tmp, sess, sid, args):
    data = rev.exam.read_session(sess, sid)
    r = rev.grading.get_result(sess, sid)
    out = []
    for q in r["questions"]:
        body = rev.stu.correction.load_question(q["question_id"])
        out.append({"position": q["position"],
                    "question_origin": body.get("origin", ""),
                    "attempt_prefix": q["attempt_id"].split("-")[0],
                    "exam_match": None})
    con = sqlite3.connect("file:%s?mode=ro" % rev.stu.store.path, uri=True)
    try:
        for o in out:
            att = [q["attempt_id"] for q in r["questions"]
                   if q["position"] == o["position"]][0]
            row = con.execute("SELECT exam_id FROM attempts WHERE "
                              "attempt_id=?", (att,)).fetchone()
            brow = con.execute("SELECT body_json FROM corrections WHERE "
                               "attempt_id=? ORDER BY version DESC LIMIT 1",
                               (att,)).fetchone()
            body = json.loads(brow[0]) if brow else {}
            o["exam_match"] = (row is not None and row[0] == r["exam_id"]
                               and body.get("exam_id") == r["exam_id"]
                               and body.get("session_id") == sess)
    finally:
        con.close()
    return {"items": out, "result_exam": r["exam_id"]}


def _formula_check(rev, exam, tmp, sess, sid):
    data = rev.exam.read_session(sess, sid)
    out = []
    for inst in data["instances"]:
        body = rev.stu.correction.load_question(inst["question_id"])
        for fid in body.get("formula_ids", []) or []:
            rec = rev._formula_record(fid)
            kb = _kb_expression(fid)
            out.append({"formula_id": fid, "resolved": rec is not None,
                        "latex_eq_kb": bool(rec) and rec.get("expression")
                        == kb,
                        "topic": rec.get("topic") if rec else None,
                        "has_section": bool(rec and rec.get("section")),
                        "has_doc": bool(rec and rec.get("document"))})
    return {"items": out}


def _kb_expression(fid: str):
    con = sqlite3.connect("file:%s?mode=ro" % KB, uri=True)
    try:
        row = con.execute("SELECT expression FROM formulas WHERE "
                          "equation_id=?", (fid,)).fetchone()
    finally:
        con.close()
    return row[0] if row else None


def _correction_shape(rev, exam, stu, tmp, sess, sid, args):
    data = rev.exam.read_session(sess, sid)
    r = rev.grading.get_result(sess, sid)
    out = []
    for q in r["questions"]:
        if args.get("position") is not None and q["position"] != args[
                "position"]:
            continue
        body = rev._correction_body(q["correction_id"])
        out.append({"position": q["position"],
                    "keys": sorted(body.keys()),
                    "provider": body.get("provider", ""),
                    "model": body.get("model", ""),
                    "status": body.get("status", "")})
    return {"items": out}


def _expect_probe(res, expect, tag, fails, tmp):
    for k, v in expect.items():
        if k == "keys":
            _check(sorted(res.keys()) == sorted(v),
                   "%s: keys %r != %r"
                   % (tag, sorted(res.keys()), sorted(v)), fails)
        elif k == "absent":
            for gone in v:
                _check(gone not in res, "%s: fuga %r" % (tag, gone), fails)
        elif k == "absent_recursive":
            bad = _find_keys(res, set(v))
            _check(not bad, "%s: fugas %r" % (tag, bad), fails)
        elif k == "present":
            for want in v:
                _check(want in res, "%s: falta %r" % (tag, want), fails)
        elif k == "digest_equal":
            _check(res == v, "%s: digest difiere" % tag, fails)
        elif k == "each":
            items = res.get("items", res.get("questions",
                                             res.get("units", [])))
            for it in items:
                for sk, sv in v.items():
                    _check(it.get(sk) == sv,
                           "%s: item %r.%s=%r != %r"
                           % (tag, it.get("position",
                                          it.get("formula_id",
                                                 it.get(
                                                     "knowledge_unit_id"))),
                              sk, it.get(sk), sv), fails)
        elif k == "states_subset":
            for uid, want in v.items():
                got = (res.get("states", {}) or {}).get(uid)
                _check(got == want, "%s: state %s=%r != %r"
                       % (tag, uid, got, want), fails)
        else:
            got = res
            for seg in k.split("."):
                if isinstance(got, list) and seg.lstrip("-").isdigit():
                    idx = int(seg)
                    got = got[idx] if -len(got) <= idx < len(got) else None
                elif isinstance(got, dict):
                    got = got.get(seg)
                else:
                    got = None
                    break
            _check(got == v, "%s: %s=%r != %r" % (tag, k, got, v), fails)


def _find_keys(o, deny: set, path="") -> list:
    bad = []
    if isinstance(o, dict):
        for k, v in o.items():
            if k in deny:
                bad.append("%s.%s" % (path, k))
            bad.extend(_find_keys(v, deny, "%s.%s" % (path, k)))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            bad.extend(_find_keys(v, deny, "%s[%d]" % (path, i)))
    return bad


def _run_units(case, tmp, fails, detail):
    from app.exam.review_policy import (
        BLIND_DEFAULTS,
        REVIEW_POLICY,
        effective_policy,
        get_review_policy,
    )
    from app.exam import review as _RV
    outs = []
    mock = effective_policy("MOCK_EXAM")
    real = effective_policy("REAL_EXAM")
    for f in ("reveal_correct_answer", "reveal_solution", "reveal_formula"):
        _check(mock["parameters"][f] is True and real["parameters"][f]
               is False, "flag ciega %s" % f, fails)
        outs.append(["blind", f])
    _check(mock["parameters"]["reveal_score"] is True, "score visible",
           fails)
    try:
        get_review_policy("review-policy-v99")
        fails.append("versión fantasma aceptada")
    except Exception as e:  # noqa: BLE001
        _check("REVIEW_POLICY_NOT_FOUND" in str(e), "marcador policy",
               fails)
        outs.append(["unknown_version", str(e)[:60]])
    _check(REVIEW_POLICY.key() == "review-policy@review-policy-v1",
           "policy key", fails)
    for t in case.get("checks", []):
        kind = t["kind"]
        if kind == "error_fixture":
            fb = _RV.build_feedback(t["correction"], t["question"],
                                    params=dict(mock["parameters"]), answer="")
            for k, v in t["expect"].items():
                if k == "errors":
                    got = [(e["type"], e["root"], sorted(e["consequences"]))
                           for e in fb["errors"]]
                    _check(got == [tuple(x) for x in v],
                           "errors %r != %r" % (got, v), fails)
                elif k == "guidance_for":
                    got = sorted(g["for_error"] for g in fb["guidance"])
                    _check(got == sorted(v), "guidance %r != %r" % (got, v),
                           fails)
                else:
                    _check(fb.get(k) == v, "feedback.%s=%r != %r"
                           % (k, fb.get(k), v), fails)
            outs.append(["fixture", t["name"]])
        elif kind == "bands":
            got = {s: _RV.BAND_HUMAN[s][0] for s in
                   ("MINOR", "MODERATE", "MAJOR", "CRITICAL")}
            _check(got == t["expect_ca"], "bandas ca %r" % got, fails)
            got = {s: _RV.BAND_HUMAN[s][1] for s in
                   ("MINOR", "MODERATE", "MAJOR", "CRITICAL")}
            _check(got == t["expect_es"], "bandas es %r" % got, fails)
            outs.append(["bands", True])
        elif kind == "taxonomy":
            from app.correction.models import ERROR_TYPES
            _check(sorted(_RV.ERROR_HUMAN.keys()) == sorted(ERROR_TYPES),
                   "taxonomia divergente", fails)
            _check(len(ERROR_TYPES) == 16, "taxonomia != 16", fails)
            outs.append(["taxonomy", True])
        elif kind == "render_pair":
            _check_render_pair(tmp, t, fails, detail)
            outs.append(["render_pair", True])
        elif kind == "hints_parity":
            from app.correction.service import _FIX_HINTS
            es = {k: v[1] for k, v in _RV.FIX_HINT.items()}
            _check(set(es) >= set(_FIX_HINTS) and all(
                es[k] == _FIX_HINTS[k] for k in _FIX_HINTS),
                   "hints es derivan", fails)
            outs.append(["hints", True])
        else:
            raise ValueError("check desconocido: %r" % kind)
    detail["result"] = outs
    return (not fails, {**detail, "fails": fails})


def _run_isolate(case, tmp, fails, detail):
    targets = [KB, EVALDB, CHUNKS, MANIFEST]
    before = {t: _sha(t) for t in targets}
    before_gen = _gen_content()
    _gen_pool(tmp, case.get("pool", []))
    exam, stu, grading = _services(tmp)
    from app.exam.review import ExamReviewService
    rev = ExamReviewService(exam, grading, stu, KB)
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
    r1 = rev.get_review(sess, sid)
    r2 = rev.get_review(sess, sid)
    m1 = rev.get_mastery_view(sid, sess)
    after = {t: _sha(t) for t in targets}
    bad = [Path(t).name for t in targets if before[t] != after[t]]
    gen_now = _gen_content()
    detail["result"] = {"matches": not bad, "gen_stable": gen_now
                        == before_gen, "review_equal": r1 == r2,
                        "mastery_units": len(m1["units"])}
    _check(not bad, "hash cambio: %r" % bad, fails)
    _check(gen_now == before_gen, "GENDB cambio", fails)
    _check(r1 == r2, "review inestable", fails)
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
                " 'qm-%' OR question_id LIKE 'qb-%'").fetchone()[0],
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
        with tempfile.TemporaryDirectory(prefix="exam-review-") as td:
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
            {"spec": "review-policy-v1", "cases": details},
            ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        print("resultados en %s" % out)
    print("OK" if all_ok else "FALLOS")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
