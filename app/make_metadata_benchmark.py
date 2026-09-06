"""Benchmark de metadata (§138): casos conocidos/desconocidos con veredicto.

Generador con verificacion interna (falla si el veredicto esperado no se
sostiene con los artefactos de curacion). Uso: python3 -m app.make_metadata_benchmark
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
WORKSPACE = Path(__file__).resolve().parent.parent
DEST = WORKSPACE / "data" / "evaluation" / "metadata_benchmark.jsonl"


def main() -> None:
    from app.curation import si_glossary, unit_for, variable_status
    kb = str(WORKSPACE / "data" / "processed" / "knowledge.sqlite")
    meta = str(WORKSPACE / "data" / "metadata")
    cases = [
        ("D01", "known-variable", {"formula_id": "eq-07-0178", "symbol": "C"},
         "CONFIRMED"),
        ("D02", "unknown-variable", {"formula_id": "eq-07-0178", "symbol": "wQQQ"},
         "UNKNOWN"),
        ("D03", "unknown-formula-variable", {"formula_id": "eq-99-0001", "symbol": "x"},
         "UNKNOWN"),
        ("D04", "known-unit", {"quantity": "Resistència"}, "CONFIRMED"),
        ("D05", "unknown-unit", {"quantity": "Xyzzyql"}, "UNKNOWN"),
        ("D06", "wrong-unit", {"quantity": "Resistència", "claimed": "V"}, "REJECT"),
        ("D07", "equivalent-unit", {"quantity": "Resistència", "claimed": "Ω"}, "ACCEPT"),
        ("D08", "correct-context", {"formula_id": "eq-02-0034"}, "HAS_CONTEXT"),
    ]
    out = []
    for cid, kind, payload, expected in cases:
        if kind == "known-variable":
            got = variable_status(kb, payload["formula_id"], payload["symbol"], meta)["status"]
            detail = payload["symbol"]
        elif kind in ("unknown-variable", "unknown-formula-variable"):
            got = variable_status(kb, payload["formula_id"], payload["symbol"])["status"]
            detail = "unknown"
        elif kind == "known-unit":
            r = unit_for(kb, payload["quantity"])
            got = r["status"] if r else "UNKNOWN"
            detail = (r or {}).get("unit", "")
        elif kind == "unknown-unit":
            got = "UNKNOWN" if unit_for(kb, payload["quantity"]) is None else "CONFIRMED"
            detail = "none"
        elif kind in ("wrong-unit", "equivalent-unit"):
            r = unit_for(kb, payload["quantity"])
            names = set()
            if r:
                names = {r["unit"].lower(), r["symbol"].lower(),
                         r["unit"].lower().rstrip("s"), r["symbol"].lower().rstrip("s")}
            ok = payload["claimed"].lower() in names
            got = "ACCEPT" if ok else "REJECT"
            detail = (r or {}).get("unit", "")
        else:
            import sqlite3
            con = sqlite3.connect("file:%s?mode=ro" % kb, uri=True)
            try:
                h2 = con.execute("SELECT section_h2 FROM formulas WHERE equation_id=?",
                                 (payload["formula_id"],)).fetchone()
            finally:
                con.close()
            got = "HAS_CONTEXT" if h2 and h2[0] else "NO_CONTEXT"
            detail = (h2[0][:60] if h2 and h2[0] else "")
        assert got == expected, (cid, got, expected)
        out.append({"id": cid, "kind": kind, "payload": payload, "expected": expected,
                    "detail": detail})
    with DEST.open("w", encoding="utf-8") as fh:
        for o in out:
            fh.write(json.dumps(o, ensure_ascii=False, sort_keys=True) + "\n")
    print("metadata benchmark: %d casos verificados" % len(out))


if __name__ == "__main__":
    main()
