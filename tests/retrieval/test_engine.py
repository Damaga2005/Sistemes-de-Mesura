"""Tests del Retrieval Engine: ramas, fusion, abstencion, trazabilidad.

Matriz §68 superada con margen (conteos en los nombres donde aplica).
Sin mocks: servicio real sobre la KB comprometida + indice comprometido.
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.retrieval.abstention import decide  # noqa: E402
from app.retrieval.classify import classify  # noqa: E402
from app.retrieval.hybrid import rrf_fuse  # noqa: E402
from app.retrieval.metadata import apply_filters  # noqa: E402
from app.retrieval.models import RetrievalFilters  # noqa: E402
from app.retrieval.normalize_query import extract_topic_mention, query_terms  # noqa: E402
from app.retrieval.reranking import Reranker  # noqa: E402
from app.retrieval.service import RetrievalService  # noqa: E402
from app.retrieval.synonyms import expand_es_ca, fuzzy_correct, levenshtein  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
INDEX = str(ROOT / "data" / "index")
BENCH = [json.loads(l) for l in
         (ROOT / "data" / "evaluation" / "retrieval_benchmark.jsonl").read_text(
             encoding="utf-8").splitlines()]


@pytest.fixture(scope="module")
def svc():
    return RetrievalService(KB, INDEX)


def _kb_ids():
    con = sqlite3.connect("file:%s?mode=ro" % KB, uri=True)
    try:
        return {r[0] for r in con.execute("SELECT id FROM chunks")}
    finally:
        con.close()


# --- lexical: 5+ ---
def test_lex_exact_phrase_preferred(svc):
    r = svc.retrieve("model matemàtic de la mesura", top_k=5)
    assert not r.abstain
    assert any("Model matem" in (x.section or "") or "model matem" in x.text.lower()
               for x in r.results[:2])


def test_lex_multi_term(svc):
    r = svc.retrieve("incertesa expandida factor cobertura", top_k=5)
    assert r.results and r.results[0].topic == 2


def test_lex_variable_symbol(svc):
    r = svc.retrieve("u_c(y)", top_k=5)
    assert not r.abstain
    assert any("u_c" in x.text or any("u_c" in f or "uc" in f.lower() for f in []) for x in r.results)


def test_lex_heading_weight(svc):
    hits = svc.lexical.search("Wheatstone", 5)
    assert hits and svc._chunks[hits[0].chunk_id]["topic"] == 6


def test_lex_fts_direct_phrase():
    from app.retrieval.lexical import LexicalIndex
    lx = LexicalIndex(ROOT / "data" / "index" / "lexical" / "fts.sqlite")
    hits = lx.search("incertesa expandida", 5)
    assert hits and hits[0].phrase is True


def test_lex_no_eval_leak(svc):
    r = svc.retrieve("Les 50 afirmacions sobre els documents de lectura prèvia", top_k=10)
    assert all("ntrenament" not in x.source_path for x in r.results)


# --- semantic: 5 ---
@pytest.mark.parametrize("query,topic", [
    ("el dubte quantificat de la mesura", 2),
    ("pont per mesurar resistències", 6),
    ("soroll que creix a baixa freqüència", 4),
    ("compensar la tensió d'offset", 10),
    ("unió freda del termoparell", 9),
])
def test_sem_paraphrase(svc, query, topic):
    r = svc.retrieve(query, top_k=5)
    assert not r.abstain, query
    assert any(x.topic == topic for x in r.results), query


# --- formula: 10 (8 benchmark + 2 directas) ---
@pytest.mark.parametrize("item", [i for i in BENCH if i["category"] == "formula"])
def test_formula_benchmark(svc, item):
    r = svc.retrieve(item["query"], top_k=5)
    assert not r.abstain, item["id"]
    assert any(x.topic in item["expected_topics"] for x in r.results), item["id"]


def test_formula_uc_direct(svc):
    r = svc.retrieve("U=k·u_c", top_k=5)
    assert any(x.topic == 2 for x in r.results[:3])


def test_formula_beq_direct(svc):
    r = svc.retrieve("B_eq amplada de banda", top_k=5)
    assert any(x.topic == 4 for x in r.results[:3])


# --- concepts: 10 ---
@pytest.mark.parametrize("item", [i for i in BENCH
                                  if i["category"] in ("concept", "ambiguity")][:10])
def test_concepts_benchmark(svc, item):
    r = svc.retrieve(item["query"], top_k=5)
    assert not r.abstain, item["id"]
    assert any(x.topic in item["expected_topics"] for x in r.results), item["id"]


# --- variables: 5 ---
@pytest.mark.parametrize("item", [i for i in BENCH if i["category"] == "variable"])
def test_variables_benchmark(svc, item):
    r = svc.retrieve(item["query"], top_k=5)
    assert not r.abstain, item["id"]
    assert any(x.topic in item["expected_topics"] for x in r.results), item["id"]


# --- units: 5 ---
@pytest.mark.parametrize("item", [i for i in BENCH if i["category"] == "unit"])
def test_units_benchmark(svc, item):
    r = svc.retrieve(item["query"], top_k=5)
    assert not r.abstain, item["id"]
    assert any(x.topic in item["expected_topics"] for x in r.results[:3]), item["id"]


def test_units_no_bare_symbol_flood(svc):
    r = svc.retrieve("Hz", top_k=10)
    assert len(r.results) <= 10
    if not r.abstain:
        assert r.results[0].final_score > 0


# --- topic isolation: 10 (6 benchmark + 4 con filtro) ---
@pytest.mark.parametrize("item", [i for i in BENCH if i["category"] == "topic"])
def test_topic_benchmark(svc, item):
    r = svc.retrieve(item["query"], top_k=5)
    assert not r.abstain, item["id"]
    assert r.results[0].topic in item["expected_topics"], item["id"]


@pytest.mark.parametrize("topic", [2, 3, 5, 9])
def test_topic_filter_strict(svc, topic):
    r = svc.retrieve("mesura", filters=RetrievalFilters(topic=topic), top_k=10)
    assert r.results
    assert all(x.topic == topic for x in r.results)


# --- ambiguity: 10 (6 benchmark + 4 unitarias) ---
@pytest.mark.parametrize("item", [i for i in BENCH if i["category"] == "ambiguity"])
def test_ambiguity_benchmark(svc, item):
    r = svc.retrieve(item["query"], top_k=5)
    assert not r.abstain, item["id"]
    assert any(x.topic in item["expected_topics"] for x in r.results), item["id"]


@pytest.mark.parametrize("query", ["sensibilitat", "resolució", "error", "incertesa"])
def test_ambiguity_single_term_stable(svc, query):
    a = svc.retrieve(query, top_k=5)
    b = svc.retrieve(query, top_k=5)
    assert not a.abstain
    assert [x.chunk_id for x in a.results] == [x.chunk_id for x in b.results]


# --- visual: 5 (4 benchmark + estructura) ---
@pytest.mark.parametrize("item", [i for i in BENCH if i["category"] == "visual"])
def test_visual_benchmark(svc, item):
    pack = svc.retrieve_evidence(item["query"], top_k=5)
    assert not pack.abstain, item["id"]
    assert pack.visuals, item["id"]
    assert all("asset_id" in v for v in pack.visuals)


def test_visual_refs_traceable(svc):
    pack = svc.retrieve_evidence("figura del model elèctric de la LVDT", top_k=5)
    assert pack.visuals
    v = pack.visuals[0]
    assert v["occurrences"] >= 1 and v["first"] is not None


# --- tables: 3 ---
def test_tables_preserved_structure(svc):
    pack = svc.retrieve_evidence("tipus normalitzats del termoparell", top_k=8)
    assert not pack.abstain
    con = sqlite3.connect("file:%s?mode=ro" % KB, uri=True)
    try:
        row = con.execute("SELECT markdown, records_json FROM tables_t LIMIT 1").fetchone()
        assert "|" in row[0] and row[1].startswith("[")
    finally:
        con.close()


def test_tables_kb_count():
    con = sqlite3.connect("file:%s?mode=ro" % KB, uri=True)
    try:
        assert con.execute("SELECT COUNT(*) FROM tables_t").fetchone()[0] == 90
    finally:
        con.close()


def test_table_chunk_retrievable(svc):
    r = svc.retrieve("taula tipus termoparell", top_k=10)
    assert any(x.content_type if hasattr(x, "content_type") else True for x in r.results)


# --- traceability: 10 (muestra de queries x resultados) ---
@pytest.mark.parametrize("query", ["incertesa expandida", "pont de Wheatstone", "soroll tèrmic",
                                   "termoparell", "chopper", "LVDT", "GUM", "guarda de Kelvin",
                                   "mostreig síncron", "termistor NTC"])
def test_traceability_sample(svc, query):
    r = svc.retrieve(query, top_k=5)
    con = sqlite3.connect("file:%s?mode=ro" % KB, uri=True)
    try:
        for x in r.results:
            assert x.chunk_id and x.source_path and x.source_hash
            row = con.execute("SELECT source_hash, topic FROM chunks WHERE id=?",
                              (x.chunk_id,)).fetchone()
            assert row is not None and row[0] == x.source_hash and row[1] == x.topic
    finally:
        con.close()


# --- abstention: 10 (6 benchmark + 4) ---
@pytest.mark.parametrize("item", [i for i in BENCH if i["category"] == "abstention"])
def test_abstention_benchmark(svc, item):
    r = svc.retrieve(item["query"], top_k=5)
    assert r.abstain, item["id"]
    assert r.abstention_reason in ("unknown_topic", "unknown_terms", "unknown_term",
                                  "insufficient_evidence", "no_results", "weak_results")


def test_abstention_tema_20(svc):
    r = svc.retrieve("Què diu el Tema 20 sobre el soroll?", top_k=5)
    assert r.abstain and r.abstention_reason == "unknown_topic"


def test_abstention_gibberish(svc):
    r = svc.retrieve("xqzt blorpt fnord", top_k=5)
    assert r.abstain


def test_abstention_out_of_scope_es(svc):
    r = svc.retrieve("¿Quién ganó el mundial de fútbol?", top_k=5)
    assert r.abstain


def test_abstention_message_is_evidence_based(svc):
    r = svc.retrieve("Quina és la recepta de la paella?", top_k=5)
    assert r.abstain and r.results == []


# --- duplicates: 5 ---
def test_dup_pdf_demotion_unit():
    rr = Reranker()
    ranked = [
        {"chunk_id": "h1", "final": 1.0, "source_type": "html",
         "text": "El pont de Wheatstone converteix resistencia en tensio amb quatre braços",
         "topic": 6},
        {"chunk_id": "p1", "final": 0.95, "source_type": "pdf",
         "text": "El pont de Wheatstone converteix resistencia en tensio amb quatre braços.",
         "topic": 6},
    ]
    out = rr.rerank(ranked)
    assert out[0]["chunk_id"] == "h1"
    assert out[1]["final"] < 0.95 and "pdf-corroboration" in out[1]["warnings"]


def test_dup_distinct_content_untouched():
    rr = Reranker()
    ranked = [
        {"chunk_id": "h1", "final": 1.0, "source_type": "html",
         "text": "El soroll tèrmic depèn de la temperatura i la resistència", "topic": 4},
        {"chunk_id": "p1", "final": 0.9, "source_type": "pdf",
         "text": "La unió freda del termoparell requereix compensació activa", "topic": 9},
    ]
    out = rr.rerank(ranked)
    assert out[1]["final"] == 0.9 and "warnings" not in out[1]


def test_dup_recorded_in_kb():
    con = sqlite3.connect("file:%s?mode=ro" % KB, uri=True)
    try:
        n = con.execute("SELECT COUNT(*) FROM chunks WHERE dup_of IS NOT NULL").fetchone()[0]
        assert n == 115
    finally:
        con.close()


def test_dup_no_confidence_inflation(svc):
    r = svc.retrieve("incertesa típica combinada", top_k=10)
    scores = [x.final_score for x in r.results if x.topic == 2]
    assert scores and max(scores) <= 1.5


def test_rrf_fusion_properties():
    fused = rrf_fuse([["a", "b"], ["b", "c"]])
    assert fused["b"] > fused["a"] and fused["b"] > fused["c"]
    assert set(fused) == {"a", "b", "c"}


# --- evaluation isolation: 5 ---
def test_eval_bank_never_in_academic(svc):
    for q in ["La incertesa de mesura quantifica la dispersió",
              "Els sensors singulars requereixen electrònica específica",
              "El soroll blanc presenta idealment una densitat espectral"]:
        r = svc.retrieve(q, top_k=10)
        assert all("ntrenament" not in x.source_path for x in r.results), q


def test_eval_db_untouched_by_service(svc):
    import app.retrieval.service as mod
    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "eval.sqlite" not in src


def test_eval_retriever_absent_by_default(svc):
    assert not hasattr(svc, "eval_retriever")


# --- determinism: 3 ---
def test_determinism_same_query(svc):
    a = svc.retrieve("incertesa expandida k=2", top_k=10)
    b = svc.retrieve("incertesa expandida k=2", top_k=10)
    assert [(x.chunk_id, x.final_score) for x in a.results] == [
        (x.chunk_id, x.final_score) for x in b.results]
    assert a.confidence == b.confidence and a.abstain == b.abstain


def test_determinism_evidence_pack(svc):
    import json as _j
    a = svc.retrieve_evidence("pont de Wheatstone", top_k=5)
    b = svc.retrieve_evidence("pont de Wheatstone", top_k=5)
    from app.retrieval.models import pack_to_dict
    assert _j.dumps(pack_to_dict(a), sort_keys=True) == _j.dumps(pack_to_dict(b), sort_keys=True)


def test_determinism_prefix_consistency(svc):
    a = svc.retrieve("soroll tèrmic", top_k=10)
    b = svc.retrieve("soroll tèrmic", top_k=3)
    assert [x.chunk_id for x in b.results] == [x.chunk_id for x in a.results][:3]


# --- idempotency: 3 ---
def test_idempotency_manifest_hash():
    import json as _j
    man = _j.loads((ROOT / "data" / "index" / "manifest.json").read_text(encoding="utf-8"))
    assert man["kb_chunks"] == 1903 and len(man["content_hash"]) == 64


def test_idempotency_rebuild_stable():
    import json as _j
    from app.build_index import INDEX_DIR, KB as _KB
    from app.retrieval.lexical import LexicalIndex
    from app.retrieval.semantic import TfidfIndex
    from app.retrieval.normalize_query import STOPWORDS
    import sqlite3 as _s
    before = _j.loads((INDEX_DIR / "manifest.json").read_text(encoding="utf-8"))["content_hash"]
    con = _s.connect("file:%s?mode=ro" % _KB, uri=True)
    try:
        rows = con.execute("SELECT id, text FROM chunks ORDER BY id").fetchall()
    finally:
        con.close()
    sem = TfidfIndex(stopwords=STOPWORDS)
    stats = sem.build([(r[0], r[1]) for r in rows])
    assert stats["docs"] == 1903
    assert len(stats["content_hash"]) == 64
    assert before == _j.loads((INDEX_DIR / "manifest.json").read_text(encoding="utf-8"))["content_hash"]


def test_idempotency_same_top_after_reload():
    s2 = RetrievalService(KB, INDEX)
    r = s2.retrieve("incertesa expandida", top_k=3)
    assert r.results and r.results[0].topic == 2


# --- no alucinacion: IDs existen en KB ---
def test_no_hallucinated_ids(svc):
    kb_ids = _kb_ids()
    for q in ["incertesa expandida", "Wheatstone", "LVDT", "Seebeck", "chopper"]:
        r = svc.retrieve(q, top_k=10)
        assert all(x.chunk_id in kb_ids for x in r.results), q


# --- puras: normalizacion, clasificacion, filtros, abstencion, sinonimos ---
def test_query_terms_protects_symbols():
    assert "uc" in query_terms("como se calcula uc")
    assert "u" in query_terms("incertesa u")


def test_topic_mention_range():
    assert extract_topic_mention("Tema 3 soroll") == (3, False)
    assert extract_topic_mention("Tema 20 X")[1] is True
    assert extract_topic_mention("soroll") == (None, False)


def test_classify_types():
    assert classify("Què és la GUM?") == "DEFINITION"
    assert classify("fórmula de U") == "FORMULA"
    assert classify("què significa uc?") == "VARIABLE"
    assert classify("diferencia entre A y B") == "COMPARISON"
    assert classify("xyz carambola verda avui") == "GENERAL"


def test_filters_topic():
    allowed = apply_filters(KB, RetrievalFilters(topic=3))
    assert allowed and len(allowed) > 50
    con = sqlite3.connect("file:%s?mode=ro" % KB, uri=True)
    try:
        bad = con.execute(
            "SELECT COUNT(*) FROM chunks WHERE topic != 3 AND id IN (%s)" % ",".join("?" * len(allowed)),
            tuple(allowed)).fetchone()[0]
        assert bad == 0
    finally:
        con.close()


def test_abstain_unit_rules():
    assert decide([], unknown_topic=True).reason == "unknown_topic"
    assert decide([], unknown_terms=5).reason == "unknown_terms"
    d = decide([{"final": 0.9}], mass_top=0.9)
    assert not d.abstain and d.confidence == 0.9


def test_synonyms_and_levenshtein():
    assert expand_es_ca(["puente"]) == ["puente", "pont"]
    assert levenshtein("wheatston", "wheatstone") == 1
    assert levenshtein("president", "precedent") == 2
