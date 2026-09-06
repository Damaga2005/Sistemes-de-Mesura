"""Tests de curacion (§129-138, item 25): propuestas con evidencia, overrides
versionados, sin invencion, sin tocar la fuente.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.curation import apply_override, si_glossary, unit_for, variable_status  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
META = str(ROOT / "data" / "metadata")


def test_known_variable_confirmed():
    r = variable_status(KB, "eq-07-0178", "C", META)
    assert r["status"] == "CONFIRMED" and r["meaning"]


def test_unknown_variable_abstains():
    r = variable_status(KB, "eq-07-0178", "wQQQ", META)
    assert r["status"] == "UNKNOWN"


def test_unknown_formula_variable():
    assert variable_status(KB, "eq-99-0001", "x", META)["status"] == "UNKNOWN"


def test_known_unit_from_si():
    r = unit_for(KB, "Resistència")
    assert r is not None and r["status"] == "CONFIRMED"
    assert r["unit"].lower() == "ohm" and r["symbol"] == "Ω"


def test_unknown_unit_none():
    assert unit_for(KB, "Xyzzyql") is None


def test_wrong_unit_rejected():
    r = unit_for(KB, "Resistència")
    assert r is not None and "V" not in (r["unit"], r["symbol"])


def test_equivalent_unit_accepted():
    r = unit_for(KB, "Resistència")
    assert r is not None and "Ω" in (r["unit"], r["symbol"])


def test_override_provenance_and_versioning(tmp_path):
    db = tmp_path / "ovr.sqlite"
    a = apply_override(db, formula_id="eq-02-0034", field="variables",
                       old_value="[]", new_value='["U"]',
                       evidence="chunk-x", reviewer="test")
    assert a["version"] == 1 and a["override_id"].startswith("ovr-")
    b = apply_override(db, formula_id="eq-02-0034", field="variables",
                       old_value='["U"]', new_value='["U","k"]',
                       evidence="chunk-y", reviewer="test")
    assert b["version"] == 2 and b["override_id"] != a["override_id"]


def test_override_requires_evidence(tmp_path):
    with pytest.raises(ValueError):
        apply_override(tmp_path / "o.sqlite", formula_id="eq-1", field="f",
                       old_value="", new_value="x", evidence="", reviewer="t")


def test_curation_outputs_exist_with_evidence():
    for name in ["variable_proposals.jsonl", "si_glossary.jsonl",
                 "condition_candidates.jsonl", "curation_coverage.json"]:
        p = ROOT / "data" / "metadata" / name
        assert p.is_file() and p.stat().st_size > 0
    rows = [json.loads(l) for l in
            (ROOT / "data" / "metadata" / "variable_proposals.jsonl").read_text(
                encoding="utf-8").splitlines()]
    assert all(r.get("evidence") and r.get("status") for r in rows)
    assert any(r["status"] == "CONFIRMED" for r in rows)


def test_metadata_benchmark_green():
    rows = [json.loads(l) for l in
            (ROOT / "data" / "evaluation" / "metadata_benchmark.jsonl").read_text(
                encoding="utf-8").splitlines()]
    assert len(rows) == 8


def test_curation_does_not_touch_sources():
    import hashlib
    man = json.loads((ROOT / "data" / "source_manifest.json").read_text(encoding="utf-8"))
    assert man["n_files"] == 91
