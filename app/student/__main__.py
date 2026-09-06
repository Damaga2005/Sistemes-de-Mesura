"""CLI del estudiante (§110-111, §161 sin UI). Solo lectura salvo submit.

  python3 -m app.student mastery --student local-01 [--topic 2|--formula eq-02-0034]
  python3 -m app.student errors --student local-01
  python3 -m app.student memory --student local-01
  python3 -m app.student weak --student local-01 [--kind formula]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.student.service import StudentService  # noqa: E402

WORKSPACE = Path(__file__).resolve().parent.parent.parent


def main() -> None:
    ap = argparse.ArgumentParser(description="Student mastery/memory (Fase 5)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mastery")
    m.add_argument("--student", default="local-01")
    m.add_argument("--topic", type=int, default=None)
    m.add_argument("--formula", default=None)
    m.add_argument("--unit", default=None)
    e = sub.add_parser("errors")
    e.add_argument("--student", default="local-01")
    e.add_argument("--prefix", default="")
    me = sub.add_parser("memory")
    me.add_argument("--student", default="local-01")
    w = sub.add_parser("weak")
    w.add_argument("--student", default="local-01")
    w.add_argument("--kind", default="")
    w.add_argument("--limit", type=int, default=10)
    r = sub.add_parser("recent")
    r.add_argument("--student", default="local-01")
    r.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()
    svc = StudentService(str(WORKSPACE / "data" / "processed" / "knowledge.sqlite"),
                         str(WORKSPACE / "data" / "generated" / "questions.sqlite"),
                         str(WORKSPACE / "data" / "student" / "student.sqlite"))
    if args.cmd == "mastery":
        if args.formula:
            print(json.dumps(svc.get_formula_mastery(args.student, args.formula),
                             ensure_ascii=False, indent=1))
        elif args.unit:
            print(json.dumps(svc.get_mastery(args.student, args.unit),
                             ensure_ascii=False, indent=1))
        elif args.topic is not None:
            print(json.dumps(svc.get_topic_mastery(args.student, args.topic),
                             ensure_ascii=False, indent=1))
        else:
            print(json.dumps(svc.get_weak_units(args.student, limit=50),
                             ensure_ascii=False, indent=1)[:2000])
    elif args.cmd == "errors":
        print(json.dumps(svc.get_error_profile(args.student, args.prefix),
                         ensure_ascii=False, indent=1))
    elif args.cmd == "memory":
        print(json.dumps(svc.get_memory(args.student), ensure_ascii=False, indent=1))
    elif args.cmd == "weak":
        print(json.dumps(svc.get_weak_units(args.student, args.kind, args.limit),
                         ensure_ascii=False, indent=1))
    elif args.cmd == "recent":
        print(json.dumps(svc.get_recent_attempts(args.student, args.limit),
                         ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
