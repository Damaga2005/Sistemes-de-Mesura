"""CLI del corrector (§110). Sin UI.

  python3 -m app.correct --question <qid> --answer "..." [--student ID] [--json] [--debug]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.student.service import StudentService  # noqa: E402

WORKSPACE = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser(description="Corrector verificable (Fase 5)")
    ap.add_argument("--question", required=True)
    ap.add_argument("--answer", required=True)
    ap.add_argument("--student", default="local-01")
    ap.add_argument("--attempt", default="")
    ap.add_argument("--exam", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()
    svc = StudentService(str(WORKSPACE / "data" / "processed" / "knowledge.sqlite"),
                         str(WORKSPACE / "data" / "generated" / "questions.sqlite"),
                         str(WORKSPACE / "data" / "student" / "student.sqlite"))
    try:
        out = svc.submit(args.student, args.question, args.answer,
                         attempt_id=args.attempt, exam_id=args.exam)
    except KeyError as e:
        print("ERROR:", e)
        raise SystemExit(1)
    corr = out["correction"]
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
        return
    if args.debug:
        print("ATTEMPT:", out["attempt_id"], "| replayed:", out.get("replayed"))
        print("CRITERIA:")
        for c in corr["criteria_results"]:
            print("  %-14s %.2f src=%s %s" % (c["criterion_id"], c["score"],
                                              c.get("source", "?"), c.get("detail", "")[:80]))
        print("FORMULAS:", corr.get("formula_results"))
        print("CALC:", corr.get("calculation_results"))
        print("UNITS:", corr.get("unit_results"))
    print("=" * 60)
    print("STATUS:", corr["status"], "| SCORE: %.2f/%s (%.1f%%)" % (
        corr["score"], corr["max_score"], corr["percentage"]))
    fb = corr.get("feedback", {}) or {}
    if fb.get("points"):
        for p in fb["points"][:6]:
            print("  [%s/%s] %s -- %s" % (p["error"], p["severity"], p["why"][:100],
                                          p["how_to_fix"][:100]))
    else:
        print("  Correcto. Criterios:", fb.get("what_was_correct"))
    print("MASTERY UPDATES:", len(out["mastery_updates"]))
    for u in out["mastery_updates"][:8]:
        print("  %s score=%.3f conf=%.3f %s" % (u["unit"], u["score"], u["confidence"],
                                                u["status"]))


if __name__ == "__main__":
    main()
