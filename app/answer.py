"""CLI del Tutor verificable (§57-59). Sin UI web, sin memoria todavía (Fase 5+).

Uso:
  python3 -m app.answer "què és la incertesa expandida?" [--provider auto|gemini|extractive]
  python3 -m app.answer --json "..." | --debug "..."
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.llm.gemini import select_provider  # noqa: E402
from app.reasoning.engine import ReasoningEngine  # noqa: E402
from app.retrieval.models import RetrievalFilters  # noqa: E402
from app.retrieval.service import RetrievalService  # noqa: E402

WORKSPACE = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser(description="Tutor verificable (Fase 3)")
    ap.add_argument("query")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--provider", default="auto", choices=["auto", "gemini", "extractive"])
    ap.add_argument("--topic", type=int, default=None)
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()

    svc = RetrievalService(WORKSPACE / "data" / "processed" / "knowledge.sqlite",
                           WORKSPACE / "data" / "index")
    try:
        provider = select_provider(args.provider)
    except RuntimeError as e:
        print("ABSTAIN reasoning_unavailable: %s" % e)
        raise SystemExit(2)
    eng = ReasoningEngine(svc, str(WORKSPACE / "data" / "processed" / "knowledge.sqlite"),
                          provider=provider)
    try:
        ans = eng.answer(args.query, filters=RetrievalFilters(topic=args.topic), top_k=args.top)
    except RuntimeError as e:
        print("ABSTAIN reasoning_unavailable: %s" % e)
        raise SystemExit(2)
    if args.json:
        print(json.dumps(ans.to_dict(), ensure_ascii=False, indent=1))
        return
    if args.debug:
        print("QUERY:", ans.query)
        print("LANGUAGE:", ans.language)
        print("PROVIDER:", ans.versions.get("provider"))
        print("LATENCY:", ans.latency_ms)
        print("STATUS:", ans.verification_status, "| FORMULA:", ans.formula_verification,
              "| ABSTAIN:", ans.abstain, ans.abstention_type or "")
    print("=" * 60)
    print(ans.answer)
    print("=" * 60)
    print("VERIFICATION:", ans.verification_status, "| CONFIDENCE:", ans.confidence)
    for c in ans.claims[:10]:
        print("  [%s/%s] %s" % (c.type, c.status, c.text[:120]))
    for calc in ans.calculations:
        print("  [CALC match=%s] %s = %s %s (%s)" % (
            calc.match, calc.expression, calc.computed, calc.unit, calc.detail[:100]))
    print("PROVENANCE:")
    for p in ans.provenance[:6]:
        print("  Tema %s <- %s (%s...)" % (p["topic"], p["source_path"], p["source_hash"][:12]))
    if ans.warnings:
        print("WARNINGS:", ans.warnings[:5])


if __name__ == "__main__":
    main()
