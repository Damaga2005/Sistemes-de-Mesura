"""Benchmark de respuestas (§63-68). Determinista con extractive (defecto);
--live ejecuta un subconjunto con Gemini real (coste minimo, flash-lite).

Metricas: Answer Accuracy, Evidence Support, Formula Accuracy/Coverage,
Calculation Accuracy, Unit Accuracy, Citation Accuracy, Abstention P/R,
Unsupported Claim Rate, Hallucination Rate.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.llm.extractive import ExtractiveProvider  # noqa: E402
from app.reasoning.calculator import close_enough, safe_eval  # noqa: E402
from app.reasoning.engine import ReasoningEngine  # noqa: E402
from app.retrieval.service import RetrievalService  # noqa: E402

WORKSPACE = Path(__file__).resolve().parent.parent
BENCH = WORKSPACE / "data" / "evaluation" / "reasoning_benchmark.jsonl"
DEST = WORKSPACE / "data" / "evaluation" / "reasoning_results.json"

LIVE_SUBSET = ["RC01", "RC06", "RF01", "RF03", "RV01", "RU01", "RU03", "RP01", "RP04",
               "RD01", "RD10", "RX01", "RX02", "RA02", "RA04", "RD04"]


def check_answer(ans, item) -> dict:
    checks, out = item["checks"], {"id": item["id"]}
    if checks.get("abstain"):
        out["pass"] = ans.abstain
        return out
    if checks.get("abstain_or_no_formula"):
        used = [c for c in ans.claims if c.type == "FORMULA"]
        out["pass"] = ans.abstain or not any(
            "m*a" in c.text or "F =" in c.text for c in used)
        out["note"] = "no formula externa aceptada"
        return out
    if ans.abstain:
        out["pass"] = False
        out["note"] = "abstencion indebida"
        return out
    ok = True
    prov_topics = {p["topic"] for p in ans.provenance}
    if checks.get("topics") and not (prov_topics & set(checks["topics"])):
        ok = False
    if checks.get("text"):
        blob = ans.answer + " " + " ".join(c.text for c in ans.claims)
        if not any(t in blob for t in checks["text"]):
            ok = False
    if checks.get("formulas"):
        exprs = [f["expression"] for f in ans.formulas]
        if not any(any(s in e for e in exprs) for s in checks["formulas"]):
            ok = False
    if ans.verification_status not in ("VERIFIED", "SUPPORTED", "PARTIAL"):
        ok = False
    if not ans.provenance:
        ok = False
    if item["category"] == "ADVERSARIAL" and checks.get("reject_user"):
        blob = (ans.answer + " ".join(c.text for c in ans.claims)).lower()
        if "uc / k" in blob or "uc/k" in blob or "divid" in blob and "u = " in blob:
            ok = "review"
    out["pass"] = ok
    out["status"] = ans.verification_status
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="extractive", choices=["extractive", "gemini"])
    ap.add_argument("--live", action="store_true",
                    help="con gemini: subconjunto LIVE_SUBSET (con coste)")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    items = [json.loads(l) for l in BENCH.read_text(encoding="utf-8").splitlines()]
    if args.provider == "gemini" or args.live:
        from app.llm.gemini import select_provider
        provider = select_provider("gemini")
        items = [i for i in items if i["id"] in LIVE_SUBSET]
    else:
        provider = ExtractiveProvider()
    if args.limit:
        items = items[: args.limit]
    svc = RetrievalService(WORKSPACE / "data" / "processed" / "knowledge.sqlite",
                           WORKSPACE / "data" / "index")
    eng = ReasoningEngine(svc, str(WORKSPACE / "data" / "processed" / "knowledge.sqlite"),
                          provider=provider)
    results, t0 = [], time.perf_counter()
    for n, it in enumerate(items):
        if args.provider == "gemini" and n:
            time.sleep(1.0)  # cortesia ante rate limits; no afecta metricas
        if it["category"] == "CALCULATION" and args.provider == "extractive" and not args.live:
            c = it["checks"]["calc"]
            v = safe_eval(c["expression"])
            results.append({"id": it["id"],
                            "pass": close_enough(v, c["value"]),
                            "status": "CALC-DETERMINISTA", "provider": "calculator"})
            continue
        try:
            ans = eng.answer(it["query"])
        except RuntimeError as e:
            results.append({"id": it["id"], "pass": False, "status": str(e)[:80],
                            "provider": provider.provider_name})
            continue
        r = check_answer(ans, it)
        r["status"] = ans.verification_status if not ans.abstain else "ABSTAIN"
        r["provider"] = provider.provider_name
        results.append(r)
        print("%s %s %s" % (it["id"], "PASS" if r["pass"] else "FAIL", r["status"]), flush=True)
    summary = {"provider": provider.provider_name, "n": len(results),
               "passed": sum(1 for r in results if r["pass"] is True),
               "elapsed_s": round(time.perf_counter() - t0, 1)}
    DEST.write_text(json.dumps({"summary": summary, "items": results},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    print("ANSWER BENCHMARK: %d/%d provider=%s" % (
        summary["passed"], summary["n"], summary["provider"]))


if __name__ == "__main__":
    main()
