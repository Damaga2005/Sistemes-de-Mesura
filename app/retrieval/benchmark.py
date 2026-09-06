"""Benchmark runner + metricas (§40-41). Gold verificado, no manipulable (§69).

Define:
- hit de topico/texto/formula/fuente @K contra el gold del item;
- sufficiency@K = topico AND (texto OR formula OR fuente);
- MRR sobre el primer resultado suficiente; Precision@K sobre relevantes;
- abstention P/R; FPR = abstenciones indebidas / no-abstencion esperada.
Uso: python3 -m app.retrieval.benchmark [--split dev|test|all]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.retrieval.service import RetrievalService  # noqa: E402

WORKSPACE = Path(__file__).resolve().parent.parent.parent
BENCH = WORKSPACE / "data" / "evaluation" / "retrieval_benchmark.jsonl"


def load_bench(split: str) -> list[dict]:
    items = [json.loads(l) for l in BENCH.read_text(encoding="utf-8").splitlines()]
    return [i for i in items if split == "all" or i["split"] == split]


def load_formula_expr() -> dict[str, str]:
    out = {}
    for line in (WORKSPACE / "data" / "processed" / "formulas.jsonl").read_text(
            encoding="utf-8").splitlines():
        f = json.loads(line)
        out[f["equation_id"]] = f["expression"]
    return out


def evaluate(svc: RetrievalService, items: list[dict], k: int = 10) -> dict:
    fexpr = load_formula_expr()
    per_item = []
    for it in items:
        t0 = time.perf_counter()
        pack = svc.retrieve_evidence(it["query"], top_k=k)
        ms = round((time.perf_counter() - t0) * 1000, 2)
        res = pack.results
        ev = {"id": it["id"], "abstain": pack.abstain, "n": len(res), "ms": ms}
        if it["abstain_expected"]:
            ev["sufficient"] = pack.abstain
            ev["mrr_rank"] = None
            per_item.append(ev)
            continue
        topics = set(it["expected_topics"])
        topic_hits = {}
        for kk in (1, 3, 5, 10):
            topic_hits[kk] = any(r["topic"] in topics for r in res[:kk])
        text_hits = {}
        for kk in (1, 3, 5, 10):
            text_hits[kk] = (not it["text_contains"]) or any(
                any(s in r["text"] for s in it["text_contains"]) for r in res[:kk])
        form_hits = {}
        for kk in (1, 3, 5, 10):
            if not it["formula_contains"]:
                form_hits[kk] = True if any(r["formula_ids"] for r in res[:kk]) else "na"
            else:
                exprs = [fexpr.get(fid, "") for r in res[:kk] for fid in r["formula_ids"]]
                form_hits[kk] = any(any(s in e for e in exprs) for s in it["formula_contains"])
        src_hits = {}
        for kk in (1, 3, 5, 10):
            src_hits[kk] = (not it["source_contains"]) or any(
                any(s in r["source_path"] for s in it["source_contains"]) for r in res[:kk])
        ev.update({"topic": topic_hits, "text": text_hits, "formula": form_hits,
                   "source": src_hits})
        ev["sufficient"] = bool(topic_hits[5] and (text_hits[5] and text_hits[5] != "na"
                                or form_hits[5] and form_hits[5] != "na"
                                or src_hits[5]))
        rank = None
        for i, r in enumerate(res, 1):
            ok_t = r["topic"] in topics
            ok_e = ((it["text_contains"] and any(s in r["text"] for s in it["text_contains"]))
                    or (it["formula_contains"] and any(
                        any(s in fexpr.get(fid, "") for fid in r["formula_ids"])
                        for s in it["formula_contains"]))
                    or (it["source_contains"] and any(s in r["source_path"]
                                                     for s in it["source_contains"]))
                    or (not it["text_contains"] and not it["formula_contains"]
                        and not it["source_contains"]))
            if ok_t and ok_e:
                rank = i
                break
        ev["mrr_rank"] = rank
        rel = sum(1 for r in res[:5] if r["topic"] in topics and (
            (it["text_contains"] and any(s in r["text"] for s in it["text_contains"]))
            or (it["formula_contains"] and True) or (it["source_contains"] and any(
                s in r["source_path"] for s in it["source_contains"]))
            or (not it["text_contains"] and not it["formula_contains"]
                and not it["source_contains"])))
        ev["p5"] = round(rel / 5, 3)
        per_item.append(ev)
    return {"items": per_item, "k": k}


def summarize(ev: dict) -> dict:
    items = ev["items"]
    non_abst = [i for i in items if "sufficient" in i and not _is_abst_item(i)]
    abst_items = [i for i in items if i.get("abstain") is True or _expect_abst(i)]
    out: dict = {"n": len(items)}
    scored = [i for i in items if "topic" in i]
    for kk in (1, 3, 5, 10):
        out["recall_topic@%d" % kk] = _rate([i["topic"][kk] for i in scored])
        out["recall_text@%d" % kk] = _rate([i["text"][kk] is True for i in scored])
    f_pos = [i for i in scored if i["formula"][5] is True]
    out["formula_recall@5"] = round(len(f_pos) / len(scored), 3) if scored else 0.0
    out["topic_accuracy@1"] = _rate([i["topic"][1] for i in scored])
    out["sufficiency@5"] = _rate([bool(i["sufficient"]) for i in scored])
    rr = [1.0 / i["mrr_rank"] for i in scored if i["mrr_rank"]]
    out["mrr"] = round(sum(rr) / len(scored), 3) if scored else 0.0
    out["precision@5"] = round(sum(i["p5"] for i in scored) / len(scored), 3) if scored else 0.0
    out["hit_rate@5"] = _rate([bool(i["sufficient"]) for i in scored])
    exp_abst = [i for i in items if i.get("_exp_abst")]
    got_abst = [i for i in items if i.get("abstain")]
    tp = len([i for i in got_abst if i.get("_exp_abst")])
    out["abstention_precision"] = round(tp / len(got_abst), 3) if got_abst else 1.0
    out["abstention_recall"] = round(tp / len(exp_abst), 3) if exp_abst else 1.0
    fp = len([i for i in got_abst if not i.get("_exp_abst")])
    out["false_positive_rate"] = round(fp / len(items), 3)
    return out


def _rate(xs: list) -> float:
    return round(sum(1 for x in xs if x) / len(xs), 3) if xs else 0.0


def _is_abst_item(i: dict) -> bool:
    return "topic" not in i


def _expect_abst(i: dict) -> bool:
    return bool(i.get("_exp_abst"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="all", choices=["dev", "test", "all"])
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()
    items = load_bench(args.split)
    # Marcar expectativa de abstención desde el gold.
    gold = {g["id"]: g for g in
            [json.loads(l) for l in BENCH.read_text(encoding="utf-8").splitlines()]}
    for i in items:
        i["_exp_abst"] = gold[i["id"]]["abstain_expected"]
    svc = RetrievalService(WORKSPACE / "data" / "processed" / "knowledge.sqlite",
                           WORKSPACE / "data" / "index")
    ev = evaluate(svc, items, k=args.top)
    for it, g in zip(ev["items"], items):
        it["_exp_abst"] = g["_exp_abst"]
        if g["abstain_expected"]:
            it["sufficient"] = it["abstain"]
    summary = summarize(ev)
    dest = WORKSPACE / "data" / "evaluation" / ("retrieval_results_%s.json" % args.split)
    dest.write_text(json.dumps({"summary": summary, "items": ev["items"]},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    print("split=%s n=%d" % (args.split, len(items)))
    for k in ["recall_topic@1", "recall_topic@5", "recall_text@5", "formula_recall@5",
              "topic_accuracy@1", "sufficiency@5", "mrr", "precision@5",
              "abstention_precision", "abstention_recall", "false_positive_rate"]:
        print(" %s: %s" % (k, summary.get(k)))
    fails = [i["id"] for i in ev["items"]
             if ("sufficient" in i and not i["sufficient"])]
    print(" insufficient:", fails)


if __name__ == "__main__":
    main()
