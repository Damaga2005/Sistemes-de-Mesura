"""Gate absoluto de formulas (§61-62, §86): coverage == 100%.

Lee el resultado comprometido del benchmark completo (13 min, no se re-ejecuta
en CI) + re-verificacion viva de una muestra fija (seed) contra retrieval real
para detectar pudricion del gold. Sin excepciones por formula (§2).
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.retrieval.service import RetrievalService  # noqa: E402

RESULTS = ROOT / "data" / "evaluation" / "formula_retrieval_results.json"
GOLD = ROOT / "data" / "evaluation" / "formula_retrieval_benchmark.jsonl"
SEED, SPOT = 20260903, 25


def test_formula_coverage_is_100():
    res = json.loads(RESULTS.read_text(encoding="utf-8"))
    assert res["total"] == 2896, res["total"]
    assert res["missed"] == [], res["missed"][:10]
    assert res["coverage"] == 1.0


def test_formula_gold_complete():
    rows = [json.loads(l) for l in GOLD.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2896
    for r in rows:
        assert r["acceptable_queries"], r["formula_id"]
        assert r["latex"] and r["source_id"]


def test_formula_spot_reverification():
    rows = [json.loads(l) for l in GOLD.read_text(encoding="utf-8").splitlines()]
    rng = random.Random(SEED)
    sample = rng.sample(rows, SPOT)
    svc = RetrievalService(str(ROOT / "data" / "processed" / "knowledge.sqlite"),
                           str(ROOT / "data" / "index"))
    for g in sample:
        found = False
        for q in g["acceptable_queries"]:
            pack = svc.retrieve_evidence(q, top_k=10)
            if g["formula_id"] in [f["equation_id"] for f in pack.formulas]:
                found = True
                break
        assert found, g["formula_id"]
