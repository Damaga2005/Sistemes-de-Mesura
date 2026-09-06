"""Benchmark de cobertura de formulas (§86). Mecanico y general: las queries se
derivan de cada registro con reglas fijas (simbolos, seccion, latex), sin
excepciones por query (§2). No modifica la KB.

Uso:
  python3 -m app.formula_benchmark [--limit N] [--top 10]
Salida gate:
  FORMULA RETRIEVAL / Total / Retrieved / Missed / Coverage
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.retrieval.formula import normalize_latex, symbols_of  # noqa: E402
from app.retrieval.service import RetrievalService  # noqa: E402

WORKSPACE = Path(__file__).resolve().parent.parent
GOLD = WORKSPACE / "data" / "evaluation" / "formula_retrieval_benchmark.jsonl"
RESULTS = WORKSPACE / "data" / "evaluation" / "formula_retrieval_results.json"


def math_symbols(expression: str) -> list[str]:
    # symbols_of (sensible a caso), NO query_symbols: este minusculiza y
    # contaminaria ('T' -> 't') rompiendo covers().
    syms = sorted(
        {s for s in symbols_of(expression) if not s.startswith("base:")},
        key=lambda s: (-len(s), s),
    )
    # Sin palabras de prosa: solo simbolos cortos o con marcas matematicas.
    keep = [s for s in syms
            if len(s) <= 6 or any(c in s for c in "_^\\") or s != s.lower() or len(s) <= 3]
    return keep[:5]


def build_queries(form: dict, h1_map: dict[str, str]) -> list[str]:
    qs = []
    syms = math_symbols(form["expression"])
    if syms:
        qs.append(" ".join(syms))
    sec = (form["section_h2"] or "").strip()
    if sec:
        qs.append(sec)
    else:
        h1 = h1_map.get(form["source_path"], "")
        if h1:
            qs.append(h1)
    norm = normalize_latex(form["expression"])
    # Umbral len>=2 alineado con el canal latex-substring del servicio (union).
    # Nucleos de 1 char (')' aislado) no generan query: solo seccion.
    if len(norm) >= 2 and norm not in qs:
        qs.append(norm)
    # Deduplicar preservando orden.
    out = []
    for q in qs:
        if q and q not in out:
            out.append(q)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Cobertura de formulas (gate Fase 3)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()

    forms = [json.loads(l) for l in
             (WORKSPACE / "data" / "processed" / "formulas.jsonl").read_text(
                 encoding="utf-8").splitlines()]
    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % (WORKSPACE / "data" / "processed"
                                               / "knowledge.sqlite"), uri=True)
    try:
        h1_map = {}
        for doc_id, h1, path in con.execute(
                "SELECT d.id, d.h1, s.path FROM documents d JOIN sources s ON s.id=d.source_id"):
            h1_map[path] = h1
        src_ids = {}
        for mid, path in con.execute("SELECT id, path FROM sources"):
            src_ids[path] = mid
    finally:
        con.close()
    if args.limit:
        forms = forms[: args.limit]

    svc = RetrievalService(WORKSPACE / "data" / "processed" / "knowledge.sqlite",
                           WORKSPACE / "data" / "index")
    gold_rows, missed = [], []
    by_form: dict[str, str] = {}
    t0 = time.perf_counter()
    for i, f in enumerate(forms, 1):
        queries = build_queries(f, h1_map)
        hit, hit_rank, hit_q = False, None, None
        for q in queries:
            pack = svc.retrieve_evidence(q, top_k=args.top)
            ids = [x["equation_id"] for x in pack.formulas]
            if f["equation_id"] in ids:
                hit, hit_q = True, q
                hit_rank = ids.index(f["equation_id"]) + 1
                break
        by_form[f["equation_id"]] = hit_q or ""
        gold_rows.append({
            "formula_id": f["equation_id"], "topic": f["topic"], "section": f["section_h2"],
            "latex": f["expression"], "variables": f.get("variables", []), "units": [],
            "source_id": src_ids.get(f["source_path"], ""),
            "acceptable_queries": queries, "retrieved_by": hit_q, "rank": hit_rank,
        })
        if not hit:
            missed.append(f["equation_id"])
        if i % 250 == 0:
            print("... %d/%d missed=%d (%.0fs)" % (i, len(forms), len(missed),
                                                   time.perf_counter() - t0), flush=True)

    GOLD.write_text("\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True)
                              for r in gold_rows) + "\n", encoding="utf-8")
    total, got = len(forms), len(forms) - len(missed)
    RESULTS.write_text(json.dumps(
        {"total": total, "retrieved": got, "missed": missed,
         "coverage": round(got / total, 4) if total else 0.0,
         "top_k": args.top, "elapsed_s": round(time.perf_counter() - t0, 1)},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print("FORMULA RETRIEVAL")
    print("==================")
    print("Total formulas: %d" % total)
    print("Retrieved: %d" % got)
    print("Missed: %d" % len(missed))
    print("Coverage: %.2f%%" % (100.0 * got / total if total else 0.0))
    if missed[:20]:
        print("Sample missed: %s" % missed[:20])


if __name__ == "__main__":
    main()
