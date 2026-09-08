"""Benchmark integracion Application F10-B5 (determinista, sin UI).

76 casos: tutor/practice/adaptive/exam/review/cross/security/recovery/
idempotencia/provenance/determinismo. Reutiliza el motor del runner B4
(bindings, exists/absent, expect_error por codigo) y anade pasos `break`
(re-wiring en el mismo dir: simulacro de reinicio), pasos `subprocess`
(proceso Python separado de verdad) y cableado con proveedor roto.
Uso: python3 app/application_b5_benchmark.py [--write] [--out P]
"""
from __future__ import annotations

import json
import os
import subprocess as _sp
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import application_workflow_benchmark as B4  # noqa: E402
from app.application.errors import AppError  # noqa: E402
from app.llm.extractive import ExtractiveProvider  # noqa: E402

CASES = ROOT / "data" / "evaluation" / "phase_10_b5_benchmark.jsonl"
RESULTS = ROOT / "data" / "evaluation" / "phase_10_b5_results.json"


class _BrokenProvider:
    provider_name = "broken-b5"
    model_name = "broken-0"

    def generate(self, *a, **k):
        raise RuntimeError("proveedor caido (benchmark B5)")


def wiring(tmp: Path, provider: str = "extractive"):
    """Igual que B4 pero sin pisar q.sqlite si ya existe: un re-wiring
    en el mismo dir es un reinicio y debe conservar lo persistido."""
    tmp = Path(tmp)
    qdb = str(tmp / "q.sqlite")
    if not (tmp / "q.sqlite").exists():
        B4.shutil.copyfile(B4.GENDB, qdb)
    sdb = str(tmp / "s.sqlite")
    if provider == "broken":
        prov: object = _BrokenProvider()
    elif provider == "extractive":
        prov = ExtractiveProvider()
    else:
        raise ValueError("provider desconocido: %r" % provider)
    reng = B4.ReasoningEngine(B4._retriever(), B4.KB, provider=prov)
    eng = B4.ExaminerEngine(B4._retriever(), B4.KB, qdb)
    B4.QuestionStore(qdb)
    stu = B4.StudentService(B4.KB, qdb, sdb)
    loop = B4.AdaptiveLoop(stu)
    exs = B4.ExamSessionService(sdb, qdb, B4.KB)
    exg = B4.ExamGradingService(exs, stu)
    exr = B4.ExamReviewService(exs, exg, stu, B4.KB)
    from app.application.service import ApplicationService as AS
    app = AS(retriever=B4._retriever(), reasoning=reng, examiner=eng,
             correction=stu.correction, students=stu, adaptive=loop,
             exam_sessions=exs, exam_grading=exg, exam_review=exr,
             kb_path=B4.KB)
    from app.application.tutor import TutorWorkflow as TW
    from app.application.practice import PracticeWorkflow as PW
    from app.application.adaptive import AdaptivePracticeWorkflow as AW
    from app.application.exam import ExamWorkflow as EW
    from app.application.review import ReviewWorkflow as RW
    flows = {"tutor": TW(app), "practice": PW(app), "adaptive": AW(app),
             "exam": EW(app), "review": RW(app)}
    return app, flows


def run_case(case: dict, tmp: Path) -> tuple[bool, dict]:
    fails: list[str] = []
    detail: dict = {"case_id": case["case_id"]}
    bound: dict = {}
    try:
        for rep in range(2 if case.get("repeat_fresh") else 1):
            app, flows = wiring(tmp, case.get("provider", "extractive"))
            ctxs: dict = {}
            for i, st in enumerate(case.get("steps", [])):
                if st.get("break"):
                    app, flows = wiring(tmp, case.get("provider",
                                                      "extractive"))
                    ctxs = {}
                    continue
                if "subprocess" in st:
                    _run_subprocess(tmp, bound, st, i, case["case_id"],
                                    fails)
                    continue
                _run_step(flows, ctxs, bound, st, i, case["case_id"],
                          fails, tmp)
    except Exception as e:  # noqa: BLE001 - fallo inesperado del runner
        fails.append("runner: %r" % e)
    detail["fails"] = fails
    return (not fails, detail)


def _run_step(flows, ctxs, bound, st, i, case_id, fails, tmp):
    tag = "%s#%d(%s)" % (case_id, i, st.get("do", st.get("service", "?")))
    if "service" in st:
        return B4._run_service_step(flows, bound, st, tag, fails)
    flow = flows[st["flow"]]
    sid = st.get("student", "alu-1")
    wf = B4._CTX_WF.get(st["flow"], st.get("ctx_workflow", st["flow"])
                        .upper())
    try:
        c, s = B4._ctx(flow.app, ctxs, sid, wf, st.get("language", "ca"))
    except Exception as e:  # noqa: BLE001 - error creando contexto
        if "expect_error" in st:
            if not isinstance(e, AppError) or e.code != st["expect_error"]:
                fails.append("%s: ctx error %r != %r" % (
                    tag, getattr(e, "code", type(e).__name__),
                    st["expect_error"]))
        else:
            fails.append("%s ctx lanzo: %r" % (tag, e))
        return
    op, args = st["do"], B4._subst(dict(st.get("args", {})), bound, s)
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
            fails.append("%s lanzo: %r" % (tag, e))
        return
    if "expect_error" in st:
        fails.append("%s debio fallar (%s)" % (tag, st["expect_error"]))
        return
    for k, path in st.get("bind", {}).items():
        bound[k] = B4._dig(res, path)
    B4._apply_checks(res, st, tag, fails, bound)


_DRIVER = r"""
import json, os, sys
sys.path.insert(0, os.environ["APPREPO"])
from pathlib import Path
from app.application_b5_benchmark import wiring as b5wiring
from app.application.session import ApplicationSession

tmp = Path(os.environ["APPTMP"])
app, flows = b5wiring(tmp)
WF = {"tutor": "TUTOR", "practice": "PRACTICE", "adaptive":
      "ADAPTIVE_PRACTICE", "exam": "EXAM", "review": "REVIEW"}
req = json.loads(os.environ["APPARGS"])
flow = req["flow"]
op = req["op"]
args = dict(req.get("args", {}))
sid = req.get("student", "alu-1")
wf = WF[flow]
c = app.create_context(sid, wf, req.get("language", "ca"))
s = app.create_session(sid, wf, nonce="sub")
if isinstance(args.get("session"), dict):
    args["session"] = ApplicationSession.from_dict(args["session"])
elif op != "ask":
    args.setdefault("session", s)
try:
    res = getattr(flows[flow], op)(c, **args)
    print(json.dumps({"ok": True, "data": res.get("data", {})}))
except Exception as e:  # noqa: BLE001 - driver de prueba
    print(json.dumps({"ok": False, "code": getattr(e, "code",
          type(e).__name__), "error": str(e)[:200]}))
"""


def _run_subprocess(tmp, bound, st, i, case_id, fails):
    tag = "%s#%d(sub)" % (case_id, i)
    spec = st["subprocess"]
    args = B4._subst(dict(spec.get("args", {})), bound, None)
    env = dict(os.environ, APPREPO=str(ROOT), APPTMP=str(tmp),
               APPARGS=json.dumps({"flow": spec["flow"], "op": spec["op"],
                                   "args": args,
                                   "student": spec.get("student", "alu-1"),
                                   "language": spec.get("language", "ca")}))
    try:
        p = _sp.run([sys.executable, "-c", _DRIVER], capture_output=True,
                    text=True, timeout=300, cwd=str(ROOT), env=env)
    except Exception as e:  # noqa: BLE001
        fails.append("%s: no arranca subproceso: %r" % (tag, e))
        return
    if p.returncode != 0:
        fails.append("%s: exit %d: %s" % (tag, p.returncode,
                                          p.stderr[-300:]))
        return
    try:
        res = json.loads(p.stdout.strip().splitlines()[-1])
    except Exception as e:  # noqa: BLE001
        fails.append("%s: salida no JSON: %r" % (tag, e))
        return
    if not res.get("ok"):
        if spec.get("expect_error") == res.get("code"):
            return
        fails.append("%s: subproceso %r != %r" % (
            tag, res.get("code"), spec.get("expect_error")))
        return
    if "expect_error" in spec:
        fails.append("%s debio fallar (%s)" % (tag, spec["expect_error"]))
        return
    env2 = {"ok": True, "data": res.get("data", {})}
    for k, path in spec.get("bind", {}).items():
        bound[k] = B4._dig(env2, path)
    B4._apply_checks(env2, spec, tag, fails, bound)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    cases = [json.loads(l) for l in
             CASES.read_text(encoding="utf-8").splitlines() if l.strip()]
    print("casos: %d" % len(cases))
    all_ok, details = True, []
    for case in cases:
        with tempfile.TemporaryDirectory(prefix="app-b5-") as td:
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
            {"spec": "app-b5-1.0", "cases": details},
            ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        print("resultados en %s" % out)
    print("OK" if all_ok else "FALLOS")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
