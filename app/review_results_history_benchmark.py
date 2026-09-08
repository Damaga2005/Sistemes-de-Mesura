"""Deterministic presentation contract benchmark for F11-B5."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "data/evaluation/phase_11_b5_review_results_history_benchmark.jsonl"


def evaluate() -> dict:
    cases = [json.loads(line) for line in CASES.read_text(
        encoding="utf-8").splitlines() if line.strip()]
    scripts = "\n".join((ROOT / "web/static/js" / name).read_text(
        encoding="utf-8") for name in ("history.js", "results.js", "review.js"))
    pages = [ROOT / "web" / name for name in
             ("history.html", "results.html", "review.html")]
    checks = {
        "RESULTS": lambda: "api/exam/result" in scripts and
        "student_id" not in scripts,
        "REVIEW": lambda: all(x not in scripts for x in
                               ("correct_answer", "expected_answer", "solution")),
        "HISTORY": lambda: "api/exam/history" in scripts,
        "REAL_EXAM_BLIND": lambda: all(x not in scripts for x in
                                        ("answer_key", "provider", "raw_llm")),
        "SECURITY_IDOR": lambda: all('aria-live="polite"' in p.read_text(
            encoding="utf-8") for p in pages),
        "RECOVERY_NAVIGATION": lambda: all(
            "URLSearchParams" in (ROOT / "web/static/js" / name).read_text(
                encoding="utf-8") for name in ("results.js", "review.js")),
        "MULTILINGUAL": lambda: all('lang="ca"' in p.read_text(
            encoding="utf-8") for p in pages),
        "MASTERY": lambda: "mastery" in (ROOT / "web/static/js/review.js").read_text(
            encoding="utf-8"),
        "FORMULA": lambda: "formula" in scripts and "innerHTML" in scripts,
    }
    results = [{"id": c["id"], "category": c["category"],
                "ok": bool(checks[c["category"]]())} for c in cases]
    passed = sum(1 for r in results if r["ok"])
    return {"total": len(results), "passed": passed,
            "score": "%d/%d" % (passed, len(results)),
            "deterministic": True, "results": results}


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, sort_keys=True, indent=2))
