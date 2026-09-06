"""CLI del Examiner (§62-63). Sin UI, sin memoria, sin examen interactivo.

  python3 -m app.examiner generate --topic 2 --type FORMULA --formula eq-02-0034 --seed 7
  python3 -m app.examiner generate --topic 2 --type NUMERICAL --formula eq-02-0201 --seed 7
  python3 -m app.examiner generate --topic 1 --type TRUE_FALSE --seed 42
  python3 -m app.examiner exam --topics 2,3 --count 10 --seed 42 [--json]
  python3 -m app.examiner coverage
  python3 -m app.examiner benchmark [--live]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.examiner.service import ExaminerEngine  # noqa: E402
from app.retrieval.service import RetrievalService  # noqa: E402

WORKSPACE = Path(__file__).resolve().parent.parent.parent
KB = str(WORKSPACE / "data" / "processed" / "knowledge.sqlite")
STORE = str(WORKSPACE / "data" / "generated" / "questions.sqlite")


def _engine(use_llm: bool = False):
    svc = RetrievalService(WORKSPACE / "data" / "processed" / "knowledge.sqlite",
                           WORKSPACE / "data" / "index")
    return ExaminerEngine(svc, KB, STORE, use_llm=use_llm)


def cmd_generate(args) -> int:
    eng = _engine(use_llm=args.llm)
    q, rep = eng.generate(topic=args.topic, section=args.section or "",
                          question_type=args.type, difficulty=args.difficulty or "",
                          formula_id=args.formula or "", seed=args.seed,
                          debug=args.debug)
    if args.json:
        print(json.dumps({"question": q.to_dict() if q else None, "report": rep},
                         ensure_ascii=False, indent=1))
        return 0 if q else 1
    if q is None:
        print("REJECTED:", rep.get("rejected"))
        return 1
    print("=" * 60)
    print("[%s/%s] %s" % (q.type, q.difficulty, q.prompt))
    for i, o in enumerate(q.options):
        print("  %s) %s" % (chr(65 + i), o.text[:160]))
    print("ANSWER:", (q.correct_answer or q.expected_answer)[:300])
    print("STATUS:", q.validation.status, "| ID:", q.question_id, "| FP:", q.fingerprint[:12])
    if args.debug:
        print("REPORT:", json.dumps(rep, ensure_ascii=False)[:1500])
    return 0


def cmd_exam(args) -> int:
    from app.examiner.exam import assemble_exam
    from app.examiner.store import QuestionStore
    store = QuestionStore(STORE)
    topics = [int(t) for t in args.topics.split(",")]
    types = dict(kv.split("=") for kv in (args.types or []))
    types = {k: int(v) for k, v in types.items()}
    exam = assemble_exam(store, topics=topics, question_count=args.count,
                         types=types or None, seed=args.seed,
                         kb_version=_kb_version())
    store.put_exam(exam["exam_id"], args.seed, exam["blueprint"],
                   exam["question_ids"], exam["versions"])
    if args.json:
        print(json.dumps(exam, ensure_ascii=False, indent=1))
    else:
        print("EXAM:", exam["exam_id"], "| questions:", len(exam["question_ids"]),
              "| shortfall:", exam["coverage"]["shortfall"])
        print("IDS:", exam["question_ids"][:20])
    return 0


def _kb_version() -> str:
    h = hashlib.sha256()
    for name in ["data/processed/knowledge.sqlite", "data/processed/chunks.jsonl",
                 "data/evaluation/formula_retrieval_benchmark.jsonl"]:
        h.update(Path(WORKSPACE / name).read_bytes())
    return "kb-%s" % h.hexdigest()[:12]


def cmd_coverage(_args) -> int:
    print(Path(WORKSPACE / "data" / "evaluation"
               / "formula_examiner_coverage.json").read_text(encoding="utf-8"))
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Examiner verificable (Fase 4)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--topic", type=int, required=True)
    g.add_argument("--section", default="")
    g.add_argument("--type", required=True)
    g.add_argument("--difficulty", default="")
    g.add_argument("--formula", default="")
    g.add_argument("--seed", type=int, default=0)
    g.add_argument("--llm", action="store_true")
    g.add_argument("--json", action="store_true")
    g.add_argument("--debug", action="store_true")
    e = sub.add_parser("exam")
    e.add_argument("--topics", required=True)
    e.add_argument("--count", type=int, required=True)
    e.add_argument("--types", nargs="*", default=[])
    e.add_argument("--seed", type=int, default=0)
    e.add_argument("--json", action="store_true")
    sub.add_parser("coverage")
    b = sub.add_parser("benchmark")
    b.add_argument("--live", action="store_true")
    b.add_argument("--split", default="all", choices=["all", "dev", "test"])
    args = ap.parse_args()
    if args.cmd == "generate":
        raise SystemExit(cmd_generate(args))
    if args.cmd == "exam":
        raise SystemExit(cmd_exam(args))
    if args.cmd == "coverage":
        raise SystemExit(cmd_coverage(args))
    if args.cmd == "benchmark":
        from app.examiner_benchmark import main as bench
        raise SystemExit(bench(split=args.split, live=args.live))


if __name__ == "__main__":
    main()
