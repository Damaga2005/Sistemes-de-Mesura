"""Benchmark Exam UX F11-B4 (bridge route(), sense xarxa).

100 casos: lifecycle/question-types/persistence/timer/submit/
grading/review/security/blind/recovery. DBs temporals per cas;
KB/eval canoniques intactes. Determinista: run1 == run2.
Uso: python3 app/exam_ux_benchmark.py [--write] [--out P]
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web"))

import server as S  # noqa: E402

CASES = ROOT / "data" / "evaluation" / "phase_11_b4_exam_ux_benchmark.jsonl"
RESULTS = ROOT / "data" / "evaluation" / "phase_11_b4_exam_ux_results.json"


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


def _is_ref(v):
    return isinstance(v, str) and len(v) > 1 and v.startswith("$") and \
        v[1:2].isalpha() and all(
            ch.isalnum() or ch in "_." for ch in v[1:])


def _resolve(v, bound):
    if isinstance(v, str) and _is_ref(v):
        root = v[1:].split(".")[0]
        if root not in bound:
            return (False, v)
        return (True, _dig({"b": bound}, "b." + v[1:]))
    if isinstance(v, list):
        out = []
        for x in v:
            ok, val = _resolve(x, bound)
            if not ok:
                return (False, val)
            out.append(val)
        return (True, out)
    if isinstance(v, dict):
        out = {}
        for k, x in v.items():
            ok, val = _resolve(x, bound)
            if not ok:
                return (False, val)
            out[k] = val
        return (True, out)
    return (True, v)


def run_case(case: dict, tmp: Path) -> tuple[bool, dict]:
    fails: list[str] = []
    b = S.Bridge(workdir=str(tmp))
    jar = ""
    bound: dict = {}
    for i, st in enumerate(case.get("steps", [])):
        tag = "%s#%d" % (case["case_id"], i)
        if st.get("reopen"):
            b = S.Bridge(workdir=str(tmp))
            continue
        ok, val = _resolve(st.get("body", {}), bound)
        if not ok:
            fails.append("%s: sin binding %r" % (tag, val))
            continue
        body = val
        ok, val = _resolve(st.get("query", {}), bound)
        if not ok:
            fails.append("%s: sin binding %r" % (tag, val))
            continue
        query = val
        try:
            status, data, setck = b.route(
                st.get("method", "GET"), st["api"], query, body, jar)
        except Exception as e:  # noqa: BLE001 - bug del runner/codi
            fails.append("%s lanzo: %r" % (tag, e))
            continue
        if setck and "sm_session=" in setck:
            jar = "sm_session=" + setck.split("sm_session=")[1].split(
                ";")[0]
        for k, path in st.get("bind", {}).items():
            if path == "cookie":
                bound[k] = jar
            elif path == "status":
                bound[k] = status
            else:
                bound[k] = _dig(data, path)
        exp = st.get("expect")
        if exp:
            if exp.get("status") is not None and status != exp["status"]:
                fails.append("%s: http %r != %r" % (
                    tag, status, exp["status"]))
            for k, v in exp.get("data", {}).items():
                if k == "exists":
                    for p in v:
                        if _dig(data, p) is None:
                            fails.append("%s: falta %r" % (tag, p))
                elif k == "absent":
                    for p in v:
                        if _dig(data, p) is not None:
                            fails.append("%s: fuga %r" % (tag, p))
                else:
                    ok2, want = _resolve(v, bound)
                    if not ok2:
                        fails.append("%s: sin binding %r" % (tag, want))
                    elif _dig(data, k) != want:
                        fails.append("%s: %s=%r != %r" % (
                            tag, k, _dig(data, k), want))
        ee = st.get("expect_error")
        if ee:
            if status == 200:
                fails.append("%s debio fallar (%r)" % (tag, ee))
            else:
                if data.get("code") != ee:
                    fails.append("%s: code %r != %r" % (
                        tag, data.get("code"), ee))
    return (not fails, {"case_id": case["case_id"], "fails": fails})


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
        with tempfile.TemporaryDirectory(prefix="ex-ux-") as td:
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
            {"spec": "exam-ux-1.0", "cases": details},
            ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        print("resultados en %s" % out)
    print("OK" if all_ok else "FALLOS")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
