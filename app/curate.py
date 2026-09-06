"""Ejecuta la curacion y mide cobertura (§133-134). Sin inventar: propone con
evidencia; confirma solo alta precision (patrones) y glosario SI (tablas).
Uso: python3 -m app.curate
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.curation import propose_conditions, propose_variables, si_glossary  # noqa: E402

WORKSPACE = Path(__file__).resolve().parent.parent
KB = str(WORKSPACE / "data" / "processed" / "knowledge.sqlite")
OUT = WORKSPACE / "data" / "metadata"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    variables = propose_variables(KB)
    units = si_glossary(KB)
    conditions = propose_conditions(KB)
    (OUT / "variable_proposals.jsonl").write_text("\n".join(
        json.dumps(r, ensure_ascii=False, sort_keys=True) for r in variables) + "\n",
        encoding="utf-8")
    (OUT / "si_glossary.jsonl").write_text("\n".join(
        json.dumps(r, ensure_ascii=False, sort_keys=True) for r in units) + "\n",
        encoding="utf-8")
    (OUT / "condition_candidates.jsonl").write_text("\n".join(
        json.dumps(r, ensure_ascii=False, sort_keys=True) for r in conditions) + "\n",
        encoding="utf-8")
    confirmed = sum(1 for r in variables if r["status"] == "CONFIRMED")
    cov = {"variables_proposed": len(variables), "variables_confirmed": confirmed,
           "units_glossary": len(units), "conditions_candidates": len(conditions)}
    (OUT / "curation_coverage.json").write_text(json.dumps(cov, ensure_ascii=False, indent=1),
                                                encoding="utf-8")
    print("curation: vars=%d (confirmed %d) units=%d conds=%d" % (
        len(variables), confirmed, len(units), len(conditions)))


if __name__ == "__main__":
    main()
