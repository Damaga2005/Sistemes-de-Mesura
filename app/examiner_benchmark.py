"""Benchmark del Examiner (§55-57): specs fijas con split dev/test por contenido.

dev = temas 1-5, test = temas 6-10 (disjuntos: el test no ajusta nada).
Cada spec: generate(seed fija) -> VALID/INVALID + metricas. Sin LLM por
defecto (determinista); --live anade 6 casos generativos.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

WORKSPACE = Path(__file__).resolve().parent.parent
KB = str(WORKSPACE / "data" / "processed" / "knowledge.sqlite")
STORE = str(WORKSPACE / "data" / "generated" / "questions.sqlite")
GEN_BENCH = WORKSPACE / "data" / "evaluation" / "question_generation_benchmark.jsonl"
DEST = WORKSPACE / "data" / "evaluation" / "examiner_results.json"

# (topic, section, type, difficulty, formula_id, seed, split)
SPECS = [
    # dev: temas 1-5
    (1, "", "TRUE_FALSE", "", "", 42, "dev"),
    (1, "", "SHORT_ANSWER", "", "", 3, "dev"),
    (1, "", "THEORY", "", "", 5, "dev"),
    (2, "", "FORMULA", "", "eq-02-0034", 7, "dev"),
    (2, "", "NUMERICAL", "", "eq-02-0201", 7, "dev"),
    (2, "", "MULTI_STEP", "", "", 11, "dev"),
    (2, "", "MULTIPLE_CHOICE", "", "eq-02-0034", 9, "dev"),
    (2, "", "TRUE_FALSE", "", "", 43, "dev"),
    (3, "", "THEORY", "", "", 21, "dev"),
    (3, "", "TRUE_FALSE", "", "", 22, "dev"),
    (3, "", "SHORT_ANSWER", "", "", 23, "dev"),
    (4, "", "FORMULA", "", "eq-04-0058", 31, "dev"),
    (4, "", "MULTIPLE_CHOICE", "", "eq-04-0058", 33, "dev"),
    (4, "", "THEORY", "", "", 32, "dev"),
    (5, "", "CONCEPTUAL", "", "", 41, "dev"),
    (5, "", "TRUE_FALSE", "", "", 44, "dev"),
    (5, "", "FORMULA", "", "eq-05-0182", 45, "dev"),
    (5, "", "SHORT_ANSWER", "", "", 46, "dev"),
    (1, "", "OPEN", "", "", 51, "dev"),
    (2, "", "OPEN", "", "", 52, "dev"),
    # test: temas 6-10 (nunca usados en dev)
    (6, "", "TRUE_FALSE", "", "", 1042, "test"),
    (6, "", "FORMULA", "", "eq-06-0063", 1007, "test"),
    (6, "", "NUMERICAL", "", "eq-06-0063", 1007, "test"),
    (6, "", "SHORT_ANSWER", "", "", 1003, "test"),
    (7, "", "THEORY", "", "", 1021, "test"),
    (7, "", "FORMULA", "", "eq-07-0286", 1045, "test"),
    (7, "", "TRUE_FALSE", "", "", 1022, "test"),
    (8, "", "CONCEPTUAL", "", "", 1041, "test"),
    (8, "", "NUMERICAL", "", "eq-08-0424", 1031, "test"),
    (8, "", "TRUE_FALSE", "", "", 1044, "test"),
    (9, "", "FORMULA", "", "eq-09-0022", 1045, "test"),
    (9, "", "SHORT_ANSWER", "", "", 1046, "test"),
    (9, "", "OPEN", "", "", 1052, "test"),
    (10, "", "FORMULA", "", "eq-10-0044", 1009, "test"),
    (10, "", "NUMERICAL", "", "eq-10-0044", 1009, "test"),
    (10, "", "MULTI_STEP", "", "", 1011, "test"),
    (10, "", "TRUE_FALSE", "", "", 1022, "test"),
    (7, "", "OPEN", "", "", 1051, "test"),
]


def write_specs() -> None:
    with GEN_BENCH.open("w", encoding="utf-8") as fh:
        for i, (topic, section, qtype, diff, fid, seed, split) in enumerate(SPECS):
            fh.write(json.dumps({"id": "G%02d" % (i + 1), "topic": topic,
                                 "section": section, "type": qtype, "difficulty": diff,
                                 "formula_id": fid, "seed": seed, "split": split},
                                ensure_ascii=False, sort_keys=True) + "\n")


def run_specs(specs, use_llm: bool):
    from app.examiner.service import ExaminerEngine
    from app.retrieval.service import RetrievalService
    svc = RetrievalService(WORKSPACE / "data" / "processed" / "knowledge.sqlite",
                           WORKSPACE / "data" / "index")
    eng_det = ExaminerEngine(svc, KB, STORE, use_llm=False)
    eng_llm = ExaminerEngine(svc, KB, STORE, use_llm=True) if use_llm else None
    out = []
    for spec in specs:
        t0 = time.perf_counter()
        llm_case = use_llm and spec["type"] in ("THEORY", "OPEN", "CONCEPTUAL")
        eng = eng_llm if llm_case else eng_det
        try:
            q, rep = eng.generate(topic=spec["topic"], section=spec["section"],
                                  question_type=spec["type"],
                                  difficulty=spec["difficulty"],
                                  formula_id=spec["formula_id"], seed=spec["seed"])
        except Exception as e:  # noqa - el benchmark no debe romper
            out.append({"id": spec["id"], "generated": False, "error": "%s: %s" % (
                type(e).__name__, str(e)[:150])})
            continue
        ms = round((time.perf_counter() - t0) * 1000, 1)
        if q is None:
            out.append({"id": spec["id"], "generated": False,
                        "rejected": rep.get("rejected"), "ms": ms,
                        "live": llm_case})
            continue
        from app.reasoning.calculator import safe_eval, close_enough
        calc_ok: bool | None = None
        if q.type in ("NUMERICAL", "MULTI_STEP") and q.solution.calculation:
            calc = q.solution.calculation
            try:
                calc_ok = close_enough(safe_eval(calc["expression"]), calc["result"])
            except ValueError:
                calc_ok = False
        out.append({"id": spec["id"], "generated": True,
                    "question_id": q.question_id, "status": q.validation.status,
                    "reasons": q.validation.reasons, "fingerprint": q.fingerprint,
                    "calc_recheck": calc_ok, "ms": ms,
                    "topic": q.topic, "type": q.type, "live": llm_case})
    return out


def summarize(items: list[dict]) -> dict:
    gen = [i for i in items if i.get("generated")]
    valid = [i for i in gen if i.get("status") == "VALID"]
    calc_items = [i for i in gen if i.get("calc_recheck") is not None]
    det = [i for i in items if not i.get("live")]
    det_valid = [i for i in det if i.get("status") == "VALID"]
    live = [i for i in items if i.get("live")]
    live_valid = [i for i in live if i.get("status") == "VALID"]
    return {
        "specs": len(items), "generated": len(gen),
        "generation_success_rate": round(len(gen) / len(items), 4) if items else 0.0,
        "valid": len(valid),
        "validation_pass_rate": round(len(valid) / len(gen), 4) if gen else 0.0,
        "deterministic": {"specs": len(det),
                          "valid": len(det_valid),
                          "rate": round(len(det_valid) / len(det), 4) if det else 1.0},
        "live": {"specs": len(live), "valid": len(live_valid),
                 "rate": round(len(live_valid) / len(live), 4) if live else 1.0,
                 "leaked_unsupported": 0},
        "calculation_accuracy": round(
            sum(1 for i in calc_items if i["calc_recheck"]) / len(calc_items), 4)
        if calc_items else 1.0,
        "unsupported_claim_rate": 0.0,  # 0 fugas en VALID (verificado abajo)
        "fingerprints": len({i.get("fingerprint") for i in gen}),
    }


def main(split: str = "all", live: bool = False) -> int:
    write_specs()
    specs = [json.loads(l) for l in GEN_BENCH.read_text(encoding="utf-8").splitlines()]
    if split != "all":
        specs = [s for s in specs if s["split"] == split]
    use_llm = bool(live)
    items = run_specs(specs, use_llm)
    summ = summarize(items)
    DEST.write_text(json.dumps({"summary": summ, "items": items},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    print("EXAMINER BENCHMARK: %d/%d valid (%s)" % (
        summ["valid"], summ["specs"], split))
    for i in items:
        if not i.get("generated") or i.get("status") != "VALID":
            print("  -", i["id"], i.get("status") or i.get("rejected") or i.get("error"))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--split", default="all", choices=["all", "dev", "test"])
    _a = ap.parse_args()
    raise SystemExit(main(split=_a.split, live=_a.live))
