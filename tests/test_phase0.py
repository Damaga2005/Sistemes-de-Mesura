"""Tests minimos Fase 0 (10 exigidos por el brief). Solo stdlib + pytest.

Verifican el manifest derivado `data/source_manifest.json` y el comportamiento
determinista fijado en `app/phase0_spec.py`. No tocan los originales.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
from phase0_spec import (  # noqa: E402
    classify_kind,
    deterministic_id,
    extract_latex,
    sha256_bytes,
    strip_boilerplate,
    topic_from_path,
)

MANIFEST = json.loads((ROOT / "data" / "source_manifest.json").read_text(encoding="utf-8"))
ROWS = MANIFEST["manifest"]


# Test 1 — Completeness
def test_1_completeness_all_topics_and_files():
    assert MANIFEST["n_files"] == 91 == len(ROWS)
    by_suffix = {}
    for r in ROWS:
        by_suffix[r["suffix"]] = by_suffix.get(r["suffix"], 0) + 1
    assert by_suffix.get(".html") == 81
    assert by_suffix.get(".pdf") == 10
    topics = {r["topic"] for r in ROWS}
    assert topics == set(range(1, 11))
    for t in range(1, 11):
        paths = [r["path"] for r in ROWS if r["topic"] == t]
        assert any(p.lower().endswith(".pdf") for p in paths), t
        assert any("ndex" in p.lower() for p in paths), t
        assert any("ntrenament" in p.lower() for p in paths), t


# Test 2 — Source integrity
def test_2_originals_not_vendored_and_hashes_recorded():
    assert not list((ROOT).glob("Tema *")), "los originales no se copian al workspace"
    for r in ROWS:
        assert re.fullmatch(r"[0-9a-f]{64}", r["sha256"]), r["path"]
    assert len({r["sha256"] for r in ROWS}) == len(ROWS)


# Test 3 — Deterministic IDs
def test_3_deterministic_ids():
    for r in ROWS:
        assert deterministic_id(r["path"]) == r["id"], r["path"]
        assert deterministic_id(r["path"]) == deterministic_id(r["path"])
    assert len({r["id"] for r in ROWS}) == len(ROWS)


# Test 4 — Hash stability
def test_4_hash_stability():
    assert sha256_bytes(b"u_c(y)") == sha256_bytes(b"u_c(y)")
    assert sha256_bytes(b"u_c(y)") != sha256_bytes(b"uc(y)")
    assert len(sha256_bytes(b"x")) == 64


# Test 5 — Metadata completeness
def test_5_metadata_completeness():
    required = {"id", "path", "topic", "kind", "suffix", "bytes", "sha256", "language"}
    for r in ROWS:
        assert required.issubset(r.keys()), r["path"]
        assert r["topic"] in range(1, 11)
        assert r["bytes"] > 0
        assert r["kind"] in {"teoria", "index", "entrenament", "pdf-apunts"}
        if r["suffix"] == ".pdf":
            assert r["pdf_pages"] and r["pdf_pages"] > 0
        else:
            assert r["language"] == "ca"


# Test 6 — Traceability
def test_6_traceability_docs_exist():
    for doc in ["PHASE_0_AUDIT.md", "COURSE_STRUCTURE.md", "SOURCE_INVENTORY.md",
                "KNOWLEDGE_ARCHITECTURE.md", "DATA_MODEL.md", "RAG_DESIGN.md",
                "EVALUATION_PLAN.md", "DECISION_LOG.md"]:
        assert (ROOT / "docs" / doc).is_file(), doc
    for r in ROWS:
        assert r["id"].startswith("sm-%02d-" % r["topic"])
        assert r["path"].startswith("Tema %d/" % r["topic"])


# Test 7 — No boilerplate
def test_7_no_boilerplate():
    html = ('<style>.hero{}</style><div class="breadcrumb">x</div>'
            '<p>La sensibilitat relaciona sortida i mesurand</p>'
            '<script>var BANC=[];</script><!-- $U=k\\,u_c$ -->')
    clean = strip_boilerplate(html)
    assert ".hero" not in clean and "var BANC" not in clean
    assert "sensibilitat" in clean and "$U=k" in clean


# Test 8 — Formula preservation
def test_8_formula_preservation():
    html = "<!-- $U=k\\,u_c$ --><!-- $u_c(y)$ --><!-- $10^{-3}$ --><!-- nota -->"
    assert extract_latex(html) == ["$U=k\\,u_c$", "$u_c(y)$", "$10^{-3}$"]
    assert "$u_c(y)$" != "$uc(y)$"


# Test 9 — Idempotency
def test_9_idempotency():
    snap1 = [(r["id"], r["sha256"], r["topic"], r["kind"]) for r in ROWS]
    recomputed = [(deterministic_id(r["path"]), r["sha256"],
                   topic_from_path(r["path"]), classify_kind(r["path"].split("/")[-1]))
                  for r in ROWS]
    assert snap1 == recomputed


# Test 10 — Topic isolation
def test_10_topic_isolation_by_folder():
    assert topic_from_path("Tema 2/05_fake_Tema3.html") == 2
    assert topic_from_path("Tema 10/02_algo.html") == 10
    with pytest.raises(ValueError):
        topic_from_path("Otro/02_x.html")
    for r in ROWS:
        assert topic_from_path(r["path"]) == r["topic"]
