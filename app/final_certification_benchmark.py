"""Reproducible F11-B6 cross-flow certification benchmark."""
from __future__ import annotations

import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CASES = ROOT / "data/evaluation/phase_11_b6_final_certification_benchmark.jsonl"


def _text(path):
    return path.read_text(encoding="utf-8")


def _checks():
    pages = [ROOT / "web" / name for name in
             ("index.html", "study.html", "learning.html", "practice.html",
              "exams.html", "exam.html", "history.html", "results.html",
              "review.html")]
    js = "\n".join(_text(ROOT / "web/static/js" / name) for name in
                       ("history.js", "results.js", "review.js"))
    checks = {}
    checks["APP_SHELL"] = all('id="main"' in _text(p) and
                               'aria-label="Principal"' in _text(p)
                               for p in pages)

    from web.server import Bridge
    with tempfile.TemporaryDirectory(prefix="sm-b6-") as work:
        bridge = Bridge(workdir=work, gen_src=str(
            ROOT / "data/generated/questions.sqlite"))
        checks["STUDY"] = bridge.route("GET", "/api/study/topics")[0] == 200
        checks["TUTOR"] = bridge.route(
            "POST", "/api/tutor/ask", body={"query": "incertesa"})[0] == 200
        checks["PRACTICE"] = bridge.route(
            "POST", "/api/practice/start", body={"topic": 2, "seed": 7})[0] == 200
        checks["ADAPTIVE_MASTERY"] = bridge.route(
            "GET", "/api/learn/priorities")[0] == 200
        body = {"title": "B6", "exam_kind": "REAL_EXAM", "topics": [2],
                "question_count": 1, "seed": 7}
        status, created, _ = bridge.route("POST", "/api/exam/create",
                                         body=body)
        xsid = created["exam_session"]["session_id"] if status == 200 else ""
        checks["EXAM"] = status == 200 and bridge.route(
            "GET", "/api/exam/state", {"exam_session_id": xsid})[0] == 200
        checks["RESULTS"] = "api/exam/result" in _text(
            ROOT / "web/static/js/results.js")
        checks["REVIEW"] = all(word not in js for word in
                                ("correct_answer", "expected_answer", "solution"))
        checks["HISTORY"] = bridge.route("GET", "/api/exam/history")[0] == 200
        checks["REAL_EXAM_BLIND"] = all(word not in js for word in
                                         ("answer_key", "provider", "raw_llm"))
        checks["SECURITY_IDOR"] = "def _own" in _text(
            ROOT / "app/application/exam.py") and "def _own" in _text(
            ROOT / "app/application/review.py")
    checks["RESULTS"] = checks["RESULTS"] and "percentage" in _text(
        ROOT / "web/static/js/results.js")
    checks["REVIEW"] = checks["REVIEW"] and "api/exam/review" in js
    return checks


def evaluate() -> dict:
    rows = [json.loads(line) for line in CASES.read_text(
        encoding="utf-8").splitlines() if line.strip()]
    checks = _checks()
    results = [{"id": row["id"], "category": row["category"],
                "ok": bool(checks[row["category"]])} for row in rows]
    passed = sum(1 for row in results if row["ok"])
    return {"benchmark": "phase_11_b6_final_certification",
            "distribution": dict(Counter(row["category"] for row in rows)),
            "total": len(results), "passed": passed,
            "score": "%d/%d" % (passed, len(results)),
            "deterministic": True, "results": results}


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, sort_keys=True, indent=2))
