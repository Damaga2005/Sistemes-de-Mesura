"""Benchmark workflows Application F10-B4 (determinista, sin UI).

Casos scriptados por workflow + cross + seguridad + idempotencia +
provenance + determinismo. DBs temporales + copia GENDB (D73); KB e
índice reales solo en lectura; reasoning extractivo (determinista).
Uso: python3 app/application_workflow_benchmark.py [--write] [--out P]
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.adaptive.loop import AdaptiveLoop  # noqa: E402
from app.application.adaptive import AdaptivePracticeWorkflow  # noqa: E402
from app.application.errors import AppError  # noqa: E402
from app.application.exam import ExamWorkflow  # noqa: E402
from app.application.practice import PracticeWorkflow  # noqa: E402
from app.application.review import ReviewWorkflow  # noqa: E402
from app.application.service import ApplicationService  # noqa: E402
from app.application.tutor import TutorWorkflow  # noqa: E402
from app.exam.grading import ExamGradingService  # noqa: E402
from app.exam.review import ExamReviewService  # noqa: E402
from app.exam.service import ExamSessionService  # noqa: E402
from app.examiner.service import ExaminerEngine  # noqa: E402
from app.examiner.store import QuestionStore  # noqa: E402
from app.llm.extractive import ExtractiveProvider  # noqa: E402
from app.reasoning.engine import ReasoningEngine  # noqa: E402
from app.retrieval.service import RetrievalService  # noqa: E402
from app.student.service import StudentService  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
INDEX = str(ROOT / "data" / "index")
GENDB = str(ROOT / "data" / "generated" / "questions.sqlite")
CASES = ROOT / "data" / "evaluation" / "phase_10_workflow_benchmark.jsonl"
RESULTS = ROOT / "data" / "evaluation" / "phase_10_workflow_results.json"

_RETR = None


def load_cases() -> list[dict]:
    out = []
    for line in CASES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _retriever():
    global _RETR
    if _RETR is None:
        _RETR = RetrievalService(KB, INDEX)
    return _RETR


def wiring(tmp: Path):
    tmp = Path(tmp)
    qdb = str(tmp / "q.sqlite")
    shutil.copyfile(GENDB, qdb)
    sdb = str(tmp / "s.sqlite")
    reng = ReasoningEngine(_retriever(), KB, provider=ExtractiveProvider())
    eng = ExaminerEngine(_retriever(), KB, qdb)
    QuestionStore(qdb)
    stu = StudentService(KB, qdb, sdb)
    loop = AdaptiveLoop(stu)
    exs = ExamSessionService(sdb, qdb, KB)
    exg = ExamGradingService(exs, stu)
    exr = ExamReviewService(exs, exg, stu, KB)
    app = ApplicationService(
        retriever=_retriever(), reasoning=reng, examiner=eng,
        correction=stu.correction, students=stu, adaptive=loop,
        exam_sessions=exs, exam_grading=exg, exam_review=exr, kb_path=KB)
    flows = {"tutor": TutorWorkflow(app), "practice": PracticeWorkflow(app),
             "adaptive": AdaptivePracticeWorkflow(app),
             "exam": ExamWorkflow(app), "review": ReviewWorkflow(app)}
    return app, flows


def run_case(case: dict, tmp: Path) -> tuple[bool, dict]:
    fails: list[str] = []
    detail: dict = {"case_id": case["case_id"]}
    bound: dict = {}
    try:
        for rep in range(2 if case.get("repeat_fresh") else 1):
            app, flows = wiring(tmp)
            ctxs: dict = {}
            for i, st in enumerate(case.get("steps", [])):
                _run_step(flows, ctxs, bound, st, i, case["case_id"],
                          fails, rep)
    except Exception as e:  # noqa: BLE001 - fallo inesperado del runner
        fails.append("runner: %r" % e)
    detail["fails"] = fails
    return (not fails, detail)


_CTX_WF = {"adaptive": "ADAPTIVE_PRACTICE"}


def _ctx(app, ctxs, sid, workflow="TUTOR", language="ca"):
    key = (sid, workflow)
    if key not in ctxs:
        ctxs[key] = (app.create_context(sid, workflow, language),
                      app.create_session(sid, workflow, nonce="bench"))
    return ctxs[key]


_REF = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_0-9-]+)*$")


def _subst(args, bound, session):
    def one(v):
        if v == "$session":
            return session
        if isinstance(v, str) and _REF.fullmatch(v) \
                and v[1:].split(".")[0] in bound:
            return _dig({"b": bound}, "b." + v[1:])
        if isinstance(v, list):
            return [one(x) for x in v]
        if isinstance(v, dict):
            return {k: one(x) for k, x in v.items()}
        return v
    return {k: one(v) for k, v in args.items()}


def _run_step(flows, ctxs, bound, st, i, case_id, fails, rep=0):
    tag = "%s#%d(%s)" % (case_id, i, st.get("do", st.get("service", "?")))
    if rep > 0 and st.get("bind"):
        tag += "[r%d]" % rep
    if "service" in st:
        return _run_service_step(flows, bound, st, tag, fails)
    flow = flows[st["flow"]]
    sid = st.get("student", "alu-1")
    wf = _CTX_WF.get(st["flow"], st.get("ctx_workflow", st["flow"]).upper())
    c, s = _ctx(flow.app, ctxs, sid, wf, st.get("language", "ca"))
    op, args = st["do"], _subst(dict(st.get("args", {})), bound, s)
    if "session" not in args and op not in ("ask",):
        args["session"] = s
    try:
        res = getattr(flow, op)(c, **args)
    except Exception as e:  # noqa: BLE001
        if "expect_error" in st:
            if not isinstance(e, AppError) or e.code != st["expect_error"]:
                fails.append("%s: error %r != %r" % (
                    tag, getattr(e, "code", type(e).__name__),
                    st["expect_error"]))
        else:
            fails.append("%s lanzó: %r" % (tag, e))
        return
    if "expect_error" in st:
        fails.append("%s debió fallar (%s)" % (tag, st["expect_error"]))
        return
    for k, path in st.get("bind", {}).items():
        bound[k] = _dig(res, path)
    _apply_checks(res, st, tag, fails, bound)


def _apply_checks(res, st, tag, fails, bound=None):
    for k, v in st.get("expect", {}).items():
        if k == "exists":
            for path in v:
                if _dig(res, path) is None:
                    fails.append("%s: falta %r" % (tag, path))
            continue
        if k == "absent":
            for path in v:
                if _dig(res, path) is not None:
                    fails.append("%s: fuga %r" % (tag, path))
            continue
        got = _dig(res, k)
        if isinstance(v, str) and _REF.fullmatch(v):
            root = v[1:].split(".")[0]
            if not bound or root not in bound:
                fails.append("%s: sin binding %r" % (tag, v))
                continue
            v = _dig({"b": bound}, "b." + v[1:])
        if got != v:
            fails.append("%s: %s=%r != %r" % (tag, k, got, v))


def _run_service_step(flows, bound, st, tag, fails):
    app = flows["practice"].app
    target = {"exam_sessions": app.exam_sessions,
              "students": app.students}[st["service"]]
    op, args = st["do"], _subst(dict(st.get("args", {})), bound, None)
    try:
        res = getattr(target, op)(**args)
    except Exception as e:  # noqa: BLE001
        if "expect_error" in st:
            if st["expect_error"] not in "%s: %s" % (type(e).__name__, e):
                fails.append("%s: error %r != %r" % (tag, e,
                                                     st["expect_error"]))
        else:
            fails.append("%s lanzó: %r" % (tag, e))
        return
    if "expect_error" in st:
        fails.append("%s debió fallar (%s)" % (tag, st["expect_error"]))
        return
    env = {"ok": True, "data": res if isinstance(res, dict)
           else {"value": res}}
    for k, path in st.get("bind", {}).items():
        bound[k] = _dig(env, path)
    _apply_checks(env, st, tag, fails, bound)


def _dig(res, dotted):
    got = res
    for seg in dotted.split("."):
        if isinstance(got, list) and seg.lstrip("-").isdigit():
            idx = int(seg)
            got = got[idx] if -len(got) <= idx < len(got) else None
        elif isinstance(got, dict):
            got = got.get(seg)
        else:
            return None
    return got


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
        with tempfile.TemporaryDirectory(prefix="app-wf-") as td:
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
            {"spec": "app-1.0", "cases": details},
            ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        print("resultados en %s" % out)
    print("OK" if all_ok else "FALLOS")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
