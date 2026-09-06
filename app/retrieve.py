"""CLI de prueba del Retrieval (§57-58). Sin UI web, sin LLM.

Uso:
  python3 -m app.retrieve "què és la incertesa expandida?"
  python3 -m app.retrieve --json "..." [--top 5] [--topic 2] [--debug]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.retrieval.models import response_to_dict  # noqa: E402
from app.retrieval.models import RetrievalFilters  # noqa: E402
from app.retrieval.service import RetrievalService  # noqa: E402

WORKSPACE = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser(description="Retrieval académico (Fase 2)")
    ap.add_argument("query", help="consulta en catalán o español")
    ap.add_argument("--json", action="store_true", help="salida EvidencePack JSON estable")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--topic", type=int, default=None)
    ap.add_argument("--source-type", default=None, choices=["html", "pdf"])
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    svc = RetrievalService(WORKSPACE / "data" / "processed" / "knowledge.sqlite",
                           WORKSPACE / "data" / "index")
    filters = RetrievalFilters(topic=args.topic, source_type=args.source_type)
    if args.json:
        from app.retrieval.models import pack_to_dict
        pack = svc.retrieve_evidence(args.query, filters=filters, top_k=args.top)
        print(json.dumps(pack_to_dict(pack), ensure_ascii=False, indent=1))
        return
    resp = svc.retrieve(args.query, filters=filters, top_k=args.top, debug=args.debug)
    print("QUERY:", resp.query.text)
    print("NORMALIZED:", resp.normalized_query, "| TYPE:", resp.query.query_type,
          "| TOPIC:", resp.query.topic)
    print("ABSTAIN:", resp.abstain, (resp.abstention_reason or ""),
          "| CONFIDENCE:", resp.confidence, "| LATENCY_MS:", resp.latency_ms)
    for w in resp.warnings:
        print("WARNING:", w)
    for i, r in enumerate(resp.results, 1):
        print("--- #%d score=%.3f T%s [%s]" % (i, r.final_score, r.topic, r.source_path))
        print("    section:", (r.section or "")[:100])
        print("    text:", r.text[:300].replace("\n", " "))
        if r.formula_ids:
            print("    formulas:", r.formula_ids[:5])
        if r.image_refs:
            print("    images:", r.image_refs[:5])
        if args.debug:
            print("    components:", r.components)


if __name__ == "__main__":
    main()
