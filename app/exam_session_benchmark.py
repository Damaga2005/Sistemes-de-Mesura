"""Benchmark Exam Session Core Bloque 2 (determinista, sin LLM, sin grading).

20 casos (E01-E20): blueprint, preparation, session, timer, answers,
submit, seguridad, determinismo, formulas, aislamiento. Sesiones en
student DB temporal (patron canonico); pool generado determinista en
questions DB temporal (KB/indice reales solo en lectura).

Uso: python3 app/exam_session_benchmark.py [--write] [--out P]
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.exam.models import STEM_FIELDS  # noqa: E402
from app.exam.service import ExamSessionService  # noqa: E402
from app.examiner.service import ExaminerEngine  # noqa: E402
from app.retrieval.service import RetrievalService  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
INDEX = str(ROOT / "data" / "index")
EVALDB = str(ROOT / "data" / "evaluation" / "eval.sqlite")
CHUNKS = str(ROOT / "data" / "processed" / "chunks.jsonl")
MANIFEST = str(ROOT / "data" / "source_manifest.json")
GENDB = str(ROOT / "data" / "generated" / "questions.sqlite")
CASES = ROOT / "data" / "evaluation" / "exam_session_core_benchmark.jsonl"
RESULTS = ROOT / "data" / "evaluation" / "exam_session_results.json"

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


def _setup(case: dict, tmp: Path) -> ExamSessionService:
    eng = _engine(tmp)
    for g in case.get("pool", []):
        kw = {"topic": g["topic"], "question_type": g["type"],
              "seed": g["seed"]}
        if g.get("formula_id"):
            kw["formula_id"] = g["formula_id"]
        q, log = eng.generate(**kw)
        assert q is not None, "pool no generable: %r (%r)" % (kw, log)
        assert q.validation.status == "VALID", q.question_id
    from app.student.store import StudentStore
    StudentStore(str(tmp / "student.sqlite"))  # tablas F5 (conteos felices)
    return ExamSessionService(str(tmp / "student.sqlite"),
                              str(tmp / "pool.sqlite"), KB)


def run_case(case: dict, tmp: Path) -> tuple[bool, dict]:
    method = case["method"]
    fails: list[str] = []
    detail: dict = {"case_id": case["case_id"]}
    if method == "blueprint":
        return _run_blueprint(case, tmp, fails, detail)
    if method == "flow":
        return _run_flow(case, tmp, fails, detail)
    if method == "determinism":
        return _run_determinism(case, tmp, fails, detail)
    if method == "isolate":
        return _run_isolate(case, tmp, fails, detail)
    raise ValueError("metodo desconocido: %r" % method)


def _check(cond: bool, msg: str, fails: list[str]) -> None:
    if not cond:
        fails.append(msg)


def _run_blueprint(case, tmp, fails, detail):
    from app.exam.models import ExamBlueprint
    svc = ExamSessionService(str(tmp / "s.sqlite"), str(tmp / "q.sqlite"),
                             KB)
    bp = ExamBlueprint.from_dict(case["blueprint"])
    errs = bp.validate()
    expect = case["expect"]
    if expect.get("valid"):
        _check(errs == [], "errores inesperados: %r" % errs, fails)
        out = svc.store_blueprint(case["blueprint"])
        _check(out["exam_id"] == bp.exam_id(), "exam_id inestable", fails)
        _check(out["exam_id"].startswith("exm-")
               and len(out["exam_id"]) == 16, "formato exam_id", fails)
        detail["result"] = {"exam_id": out["exam_id"], "created": True}
    else:
        _check(bool(errs), "debió ser inválido", fails)
        for s in expect.get("errors_contain", []):
            _check(any(s in e for e in errs),
                   "error %r ausente en %r" % (s, errs), fails)
        try:
            svc.store_blueprint(case["blueprint"])
            fails.append("store aceptó blueprint inválido")
        except Exception as e:  # noqa: BLE001
            detail["result"] = {"rejected": str(e)[:120]}
    return (not fails, {**detail, "fails": fails})


def _run_flow(case, tmp, fails, detail):
    svc = _setup(case, tmp)
    ctx: dict = {}
    steps_out = []
    for i, st in enumerate(case["steps"]):
        op = st["do"]
        try:
            res = _exec_op(svc, tmp, ctx, case, st)
            if "expect_error" in st:
                fails.append("paso %d (%s): debió fallar (%s)"
                             % (i, op, st["expect_error"]))
                steps_out.append({"op": op, "unexpected_ok": True})
                continue
            _expect_step(res, st.get("expect", {}), ctx, i, op, fails,
                         svc, tmp)
            steps_out.append({"op": op, "ok": True,
                              "summary": _summarize(res)})
        except Exception as e:  # noqa: BLE001
            if "expect_error" in st:
                _check(st["expect_error"] in str(e),
                       "paso %d (%s): error %r no contiene %r"
                       % (i, op, str(e)[:150], st["expect_error"]), fails)
                steps_out.append({"op": op, "expected_error": str(e)[:150]})
            else:
                fails.append("paso %d (%s) lanzó: %r" % (i, op, e))
                steps_out.append({"op": op, "error": str(e)[:150]})
    detail["result"] = steps_out
    return (not fails, {**detail, "fails": fails})


def _exec_op(svc, tmp, ctx, case, st):
    op = st["do"]
    S = ctx.get("session_id", "")
    if op == "store":
        out = svc.store_blueprint(st["blueprint"])
        ctx["exam_id"] = out["exam_id"]
        return out
    if op == "prepare_exam":
        return svc.prepare_exam(ctx.get("exam_id") or st.get("exam_id", ""))
    if op == "create":
        out = svc.create_session(ctx["exam_id"], st["student"])
        ctx["session_id"] = out["session_id"]
        return out
    if op == "prepare_session":
        return svc.prepare_session(S, st.get("student", ctx.get("student")))
    if op == "start":
        return svc.start_session(S, st.get("student", ctx.get("student")),
                                 now=st.get("now", ""))
    if op == "get":
        return svc.get_question(S, st["position"],
                                st.get("student", ctx.get("student")),
                                now=st.get("now", ""))
    if op == "save":
        return svc.save_answer(S, st["position"], st["answer"],
                               st.get("student", ctx.get("student")),
                               now=st.get("now", ""))
    if op == "answers":
        return {"answers": svc.get_answers(
            S, st.get("student", ctx.get("student")))}
    if op == "submit":
        return svc.submit_session(S, st.get("student", ctx.get("student")),
                                  now=st.get("now", ""))
    if op == "cancel":
        return svc.cancel_session(S, st.get("student", ctx.get("student")),
                                  now=st.get("now", ""))
    if op == "check_expiry":
        return {"expired": svc.check_expiry(S, now=st.get("now", ""))}
    if op == "status":
        return svc.session_status(S)
    if op == "tamper":
        return _tamper(tmp, ctx, svc, st)
    if op == "attempts_zero":
        return {"attempts": _count(svc, "attempts"),
                "corrections": _count(svc, "corrections"),
                "mastery_events": _count(svc, "mastery_events")}
    if op == "answer_log_count":
        return {"log_rows": _count_where(
            svc, "answer_log", "session_id=?", (S,))}
    if op == "list_sessions":
        return {"sessions": svc.list_sessions(st["student"])}
    raise ValueError("op desconocida: %r" % op)


def _tamper(tmp, ctx, svc, st):
    con = sqlite3.connect(str(tmp / "pool.sqlite"))
    try:
        row = con.execute("SELECT body_json FROM questions LIMIT 1 "
                          "OFFSET ?", (st.get("qindex", 0),)).fetchone()
        body = json.loads(row[0])
        body["prompt"] = "PREGUNTA ALTERADA EN TEST"
        con.execute("UPDATE questions SET body_json=? WHERE question_id=?",
                    (json.dumps(body, ensure_ascii=False, sort_keys=True),
                     body["question_id"]))
        con.commit()
    finally:
        con.close()
    return {"tampered": body["question_id"]}


def _count(svc, table: str) -> int:
    con = sqlite3.connect(svc.exams.path)
    try:
        return con.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
    finally:
        con.close()


def _count_where(svc, table: str, where: str, params: tuple) -> int:
    con = sqlite3.connect(svc.exams.path)
    try:
        return con.execute("SELECT COUNT(*) FROM %s WHERE %s" % (table,
                                                                 where),
                           params).fetchone()[0]
    finally:
        con.close()


def _summarize(res):
    if isinstance(res, dict):
        return {k: v for k, v in res.items()
                if k in ("status", "exam_id", "session_id", "version",
                         "started_at", "expires_at", "submitted_at",
                         "answers_frozen", "expired", "attempts",
                         "corrections", "mastery_events", "log_rows",
                         "tampered", "created")}
    return type(res).__name__


def _expect_step(res, expect, ctx, i, op, fails, svc, tmp):
    for k, v in expect.items():
        if k == "keys":
            _check(sorted(res.keys()) == sorted(v),
                   "paso %d (%s): keys %r != %r"
                   % (i, op, sorted(res.keys()), sorted(v)), fails)
        elif k == "absent":
            for gone in v:
                _check(gone not in res,
                       "paso %d (%s): fuga %r" % (i, op, gone), fails)
        elif k == "options_text_only":
            for o in res.get("options", []):
                _check(sorted(o.keys()) == ["text"],
                       "paso %d: opcion con fuga %r" % (i, o.keys()), fails)
        elif k == "instances":
            if isinstance(v, int):
                _check(res.get("instances") == v,
                       "paso %d (%s): instances=%r != %r"
                       % (i, op, res.get("instances"), v), fails)
            else:
                got = [(x["position"], x["question_id"]) for x in
                       res.get("instances", [])]
                _check(got == [(x[0], x[1]) for x in v],
                       "paso %d (%s): instancias %r != %r"
                       % (i, op, got, v), fails)
        elif k == "fingerprints_match":
            con = sqlite3.connect(str(tmp / "pool.sqlite"))
            try:
                ok = True
                for x in res.get("instances", []):
                    fp = con.execute("SELECT fingerprint FROM questions "
                                     "WHERE question_id=?",
                                     (x["question_id"],)).fetchone()[0]
                    if not fp:
                        ok = False
            finally:
                con.close()
            _check(ok, "paso %d: fingerprint vacío" % i, fails)
        elif k == "answers":
            got = [(a["position"], a["answer"], a["version"])
                   for a in res.get("answers", [])]
            _check(got == [(a[0], a[1], a[2]) for a in v],
                   "paso %d (%s): answers %r != %r" % (i, op, got, v), fails)
        elif k == "sessions":
            got = res.get("sessions", [])
            _check(len(got) == v.get("count", len(got)),
                   "paso %d: %d sesiones != %r" % (i, len(got), v), fails)
            if "statuses" in v:
                _check([s["status"] for s in got] == v["statuses"],
                       "paso %d: statuses %r != %r"
                       % (i, [s["status"] for s in got], v["statuses"]),
                       fails)
        elif k in ("quality", "versions"):
            for sk, sv in v.items():
                got = (res.get(k, {}) or {}).get(sk)
                if sk == "manifest_len":
                    _check(isinstance(got, str) and len(got) == sv,
                           "paso %d: %s.%s len %r != %r"
                           % (i, k, sk,
                              len(got) if isinstance(got, str) else got, sv),
                           fails)
                else:
                    _check(got == sv,
                           "paso %d: %s.%s=%r != %r" % (i, k, sk, got, sv),
                           fails)
        else:
            _check(res.get(k) == v,
                   "paso %d (%s): %s=%r != %r"
                   % (i, op, k, res.get(k), v), fails)


def _run_determinism(case, tmp, fails, detail):
    outs = []
    for n in ("a", "b"):
        sub = tmp / n
        sub.mkdir()
        svc = _setup(case, sub)
        out = svc.store_blueprint(case["blueprint"])
        pre = svc.prepare_exam(out["exam_id"])
        outs.append({"exam_id": out["exam_id"],
                     "instances": pre["instances"]})
    _check(outs[0] == outs[1], "doble preparacion difiere: %r vs %r"
           % (outs[0], outs[1]), fails)
    detail["result"] = outs[0]
    return (not fails, {**detail, "fails": fails})


def _run_isolate(case, tmp, fails, detail):
    targets = [KB, EVALDB, CHUNKS, MANIFEST, GENDB]
    before = {t: _sha(t) for t in targets}
    svc = _setup(case, tmp)
    ctx: dict = {}
    for st in case["steps"]:
        _exec_op(svc, tmp, ctx, case, st)
    after = {t: _sha(t) for t in targets}
    bad = [Path(t).name for t in targets if before[t] != after[t]]
    detail["result"] = {"matches": not bad, "checked": [Path(t).name
                                                        for t in targets]}
    _check(not bad, "hash cambio: %r" % bad, fails)
    return (not fails, {**detail, "fails": fails})


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
        with tempfile.TemporaryDirectory(prefix="exam-core-") as td:
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
