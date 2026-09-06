"""Runner del benchmark de correccion (§82-83, §86-88). Determinista.

SELF:* se resuelve desde la pregunta generada (misma seed). No congela
salidas: verifica estados/errores/scores contra expectativas calculadas.
Uso: python3 -m app.correction_benchmark [--split dev|test]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.examiner.service import ExaminerEngine  # noqa: E402
from app.retrieval.service import RetrievalService  # noqa: E402
from app.student.service import StudentService  # noqa: E402

WORKSPACE = Path(__file__).resolve().parent.parent
KB = str(WORKSPACE / "data" / "processed" / "knowledge.sqlite")
GENDB = str(WORKSPACE / "data" / "generated" / "questions.sqlite")
STUDB = str(WORKSPACE / "data" / "student" / "student.sqlite")
BENCH = WORKSPACE / "data" / "evaluation" / "correction_benchmark.jsonl"
DEST = WORKSPACE / "data" / "evaluation" / "correction_results.json"


def resolve_self(kind: str, q) -> str:
    if kind == "correct":
        return q.correct_answer or q.expected_answer
    if kind == "flip":
        ca = (q.correct_answer or "").strip().upper()
        return "F" if ca == "V" else "V"
    if kind == "formula":
        return _formula_expr(q.formula_ids[0]) if q.formula_ids else q.correct_answer
    if kind == "round":
        try:
            return str(round(float(q.correct_answer), 2))
        except (ValueError, TypeError):
            return q.correct_answer
    if kind == "expected":
        return q.expected_answer or q.correct_answer
    raise ValueError("SELF desconocido: %s" % kind)


def _formula_expr(fid: str) -> str:
    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % KB, uri=True)
    try:
        row = con.execute("SELECT expression FROM formulas WHERE equation_id=?",
                          (fid,)).fetchone()
        return row[0] if row else ""
    finally:
        con.close()


def check(item: dict, corr: dict) -> tuple[bool, str]:
    exp = item["expected"]
    if corr["status"] not in exp.get("status", [corr["status"]]) and "status" in exp:
        if corr["status"] not in exp["status"]:
            return False, "status %s no esperado" % corr["status"]
    if "score" in exp and abs(corr["score"] - exp["score"]) > 1e-9:
        return False, "score %s != %s" % (corr["score"], exp["score"])
    if "min_score" in exp and corr["score"] < exp["min_score"]:
        return False, "score %s < min %s" % (corr["score"], exp["min_score"])
    if "errors" in exp:
        got = {e["error_type"] for e in corr["detected_errors"] if not e.get("derived_from")}
        if not set(exp["errors"]) <= got:
            return False, "errores %s no en %s" % (exp["errors"], sorted(got))
    if exp.get("no_instruction_follow"):
        for c in corr["criteria_results"]:
            if "10" in str(c.get("detail", "")) and "give me" in str(c.get("detail", "")).lower():
                return False, "siguio instruccion del estudiante"
    return True, corr["status"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="all", choices=["all", "dev", "test"])
    args = ap.parse_args()
    items = [json.loads(l) for l in BENCH.read_text(encoding="utf-8").splitlines()]
    if args.split != "all":
        items = [i for i in items if i["split"] == args.split]
    svc = RetrievalService(WORKSPACE / "data" / "processed" / "knowledge.sqlite",
                           WORKSPACE / "data" / "index")
    from app.examiner.service import ExaminerEngine as _EE
    eng = _EE(svc, KB, GENDB)
    stusvc = StudentService(KB, GENDB, STUDB)
    import time as _t
    nonce = "%d" % int(_t.time())
    results = []
    for it in items:
        q, rep = eng.generate(topic=it["qspec"]["topic"],
                              section=it["qspec"].get("section", ""),
                              question_type=it["qspec"]["type"],
                              formula_id=it["qspec"].get("formula_id", ""),
                              seed=it["qspec"]["seed"])
        if q is None:
            results.append({"id": it["id"], "pass": False, "note": "sin pregunta: %s" % rep.get("rejected")})
            print("%s NOQUESTION %s" % (it["id"], rep.get("rejected")), flush=True)
            continue
        ans = it["answer"]
        if ans.startswith("SELF:"):
            ans = resolve_self(ans[5:], q)
        out = stusvc.submit("bench-%s" % args.split, q.question_id, ans,
                            attempt_id="att-bench-%s-%s" % (it["id"], nonce))
        corr = out["correction"]
        ok, note = check(it, corr)
        results.append({"id": it["id"], "pass": ok, "note": note,
                        "status": corr["status"], "score": corr["score"]})
        print("%s %s %s" % (it["id"], "PASS" if ok else "FAIL", note), flush=True)
    summary = {"n": len(results), "passed": sum(1 for r in results if r["pass"])}
    DEST.write_text(json.dumps({"summary": summary, "items": results},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    print("CORRECTION BENCHMARK: %d/%d (%s)" % (summary["passed"], summary["n"], args.split))


if __name__ == "__main__":
    main()
