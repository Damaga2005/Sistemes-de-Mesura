"""Tests Fase 1: pipeline de ingesta real. Sin mocks: funciones reales sobre
fragmentos con los patrones observados en las fuentes + integridad de los
artefactos comprometidos (SQLite/JSONL generados por app.ingest).
"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.build import build_chunks, collect_concepts, collect_formulas  # noqa: E402
from app.html_extract import parse_html  # noqa: E402
from app.jsdata import find_image_maps  # noqa: E402
from app.questions import extract_questions  # noqa: E402

KB = ROOT / "data" / "processed" / "knowledge.sqlite"
EV = ROOT / "data" / "evaluation" / "eval.sqlite"
MANIFEST = {r["path"]: r for r in json.loads(
    (ROOT / "data" / "source_manifest.json").read_text(encoding="utf-8"))["manifest"]}

MINI_HTML = """<!DOCTYPE html><html lang="ca"><head><title>T</title><style>.x{}</style></head>
<body><header class="hero"><h1>Test</h1></header>
<h2>1. Prova</h2>
<p>La incertesa típica combinada <!-- $u_c(y)$ --> es calcula així.</p>
<div class="box clau"><p>Idea clau del tema.</p></div>
<table><tr><th>a</th></tr><tr><td>1</td></tr></table>
<figure><img data-fig="fig_1" alt="Corba de prova"><figcaption>Peu</figcaption></figure>
<script>var IMGDATA = {}</script>
</body></html>"""

T1_HTML = """<html lang="ca"><head><title>U</title></head><body><h1>Estàtiques</h1>
<h2>2. Sensibilitat</h2><p>La sensibilitat S = dY/dX amb subíndex u<sub>c</sub>(y) i 10<sup>-3</sup>.</p>
</body></html>"""

FIG_HTML = """<html lang="ca"><head><title>F</title></head><body><h1>F</h1><h2>S</h2>
<p><img data-fig="fig11" alt="Poma amb escales"></p>
<script>var FIGS = {"fig11": "data:image/png;base64,%s"}</script>
</body></html>""" % ("iVBORw0KGgo=" * 200)

BANC_HTML = """<html><body><script>var BANC = [{"n": 1, "d": "01", "a": "V",
"q": "Afirmació de prova.", "j": "Justificació.", "dt": "T", "df": "2_01_x.html"}];</script></body></html>"""


# 1. Cobertura total de fuentes.
def test_p1_all_sources_processed():
    con = sqlite3.connect(KB)
    try:
        assert con.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 91
        kinds = dict(con.execute("SELECT kind, COUNT(*) FROM documents GROUP BY kind").fetchall())
        assert kinds.get("teoria") == 61
        assert kinds.get("pdf-apunts") == 10
        assert "entrenament" not in kinds and "index" not in kinds
    finally:
        con.close()


# 2. Toda teoría tiene secciones y chunks.
def test_p1_theory_coverage():
    con = sqlite3.connect(KB)
    try:
        missing = con.execute(
            "SELECT d.id FROM documents d LEFT JOIN sections s ON s.doc_id=d.id "
            "WHERE d.kind='teoria' GROUP BY d.id HAVING COUNT(s.id)=0").fetchall()
        assert missing == []
        missing_c = con.execute(
            "SELECT d.id FROM documents d LEFT JOIN chunks c ON c.doc_id=d.id "
            "GROUP BY d.id HAVING COUNT(c.id)=0").fetchall()
        assert missing_c == []
    finally:
        con.close()


# 3. Fidelidad LaTeX sobre patrón real (subíndices y exponentes intactos).
def test_p1_formula_fidelity_patterns():
    doc = parse_html(MINI_HTML)
    uni, _, nxt = collect_formulas(doc, 2, "Tema 2/x.html", 1)
    assert uni == []
    chunks, latexs, _ = build_chunks(doc, 2, "Tema 2/x.html", "sha", "sm-02-aaa", 0, nxt, {}, {})
    assert [f.expression for f in latexs] == ["$u_c(y)$"]
    assert any("$u_c(y)$" in c.text for c in chunks)
    doc1 = parse_html(T1_HTML)
    uni1, _, _ = collect_formulas(doc1, 1, "Tema 1/y.html", 1)
    assert len(uni1) == 1 and uni1[0].encoding == "unicode-sub-sup"
    assert "_{c}" in uni1[0].expression and "^{-3}" in uni1[0].expression


# 4. Integridad del banco: expresiones bien formadas y con trazabilidad.
def test_p1_formula_table_integrity():
    con = sqlite3.connect(KB)
    try:
        bad = con.execute(
            "SELECT COUNT(*) FROM formulas WHERE expression='' OR"
            " (encoding='latex-comment' AND expression NOT LIKE '$%$')").fetchone()[0]
        assert bad == 0
        uni_bad = con.execute(
            "SELECT COUNT(*) FROM formulas WHERE encoding='unicode-sub-sup' AND"
            " expression NOT LIKE '%_{%}%' AND expression NOT LIKE '%^{%}%'").fetchone()[0]
        assert uni_bad == 0
        n_latex = con.execute("SELECT COUNT(*) FROM formulas WHERE encoding='latex-comment'").fetchone()[0]
        assert n_latex == 2858
        orphans = con.execute(
            "SELECT COUNT(*) FROM formulas WHERE source_path NOT LIKE 'Tema %'").fetchone()[0]
        assert orphans == 0
    finally:
        con.close()


# 5. Sin boilerplate en chunks.
def test_p1_no_boilerplate_in_chunks():
    con = sqlite3.connect(KB)
    try:
        n = con.execute(
            "SELECT COUNT(*) FROM chunks WHERE text LIKE '%var BANC%' OR text LIKE '%COM EDITAR%'"
            " OR text LIKE '%IMGDATA%' OR text LIKE '%breadcrumb%'").fetchone()[0]
        assert n == 0
    finally:
        con.close()


# 6. Trazabilidad total contra el manifest.
def test_p1_chunk_traceability():
    con = sqlite3.connect(KB)
    try:
        rows = con.execute(
            "SELECT DISTINCT source_path, source_hash, topic FROM chunks").fetchall()
        assert len(rows) > 0
        for path, sha, topic in rows:
            assert path in MANIFEST, path
            assert MANIFEST[path]["sha256"] == sha
            assert MANIFEST[path]["topic"] == topic
    finally:
        con.close()


# 7. IDs únicos y deterministas.
def test_p1_ids_unique_and_deterministic():
    con = sqlite3.connect(KB)
    try:
        n = con.execute("SELECT COUNT(*), COUNT(DISTINCT id) FROM chunks").fetchone()
        assert n[0] == n[1] and n[0] > 1000
        n2 = con.execute("SELECT COUNT(*), COUNT(DISTINCT equation_id) FROM formulas").fetchone()
        assert n2[0] == n2[1]
    finally:
        con.close()
    doc = parse_html(MINI_HTML)
    a, _, _ = build_chunks(doc, 2, "Tema 2/x.html", "s", "sm-02-aaa", 0, 1, {}, {})
    b, _, _ = build_chunks(doc, 2, "Tema 2/x.html", "s", "sm-02-aaa", 0, 1, {}, {})
    assert [c.id for c in a] == [c.id for c in b]


# 8. Separación física conocimiento/evaluación.
def test_p1_eval_separation():
    assert EV.is_file() and KB != EV
    con = sqlite3.connect(KB)
    try:
        n = con.execute("SELECT COUNT(*) FROM chunks WHERE source_path LIKE '%ntrenament%'").fetchone()[0]
        assert n == 0
    finally:
        con.close()
    ce = sqlite3.connect(EV)
    try:
        assert ce.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 500
        bad = ce.execute("SELECT COUNT(*) FROM questions WHERE answer NOT IN ('V','F')").fetchone()[0]
        assert bad == 0
    finally:
        ce.close()


# 9. Resolución de fuentes de evaluación.
def test_p1_eval_sources_resolve():
    ce = sqlite3.connect(EV)
    try:
        rows = ce.execute("SELECT qid, topic, expected_source, origin FROM questions").fetchall()
        assert len(rows) == 500
        for qid, topic, src, origin in rows:
            if ":DATA" in origin:
                assert src is None  # blocs temáticos, no archivos: por diseño
            else:
                assert src is not None, qid
                assert src in MANIFEST, (qid, src)
                assert MANIFEST[src]["topic"] == topic
    finally:
        ce.close()
    qs, fmt = extract_questions(BANC_HTML, 2, "Tema 2/e.html")
    assert fmt == "BANC" and qs[0].answer == "V" and qs[0].question.startswith("Afirmació")


# 10. Reconciliación completa y acotada.
def test_p1_reconciliation_complete():
    con = sqlite3.connect(KB)
    try:
        rows = con.execute("SELECT topic, coverage, status FROM reconciliation").fetchall()
        assert sorted(t for t, _, _ in rows) == list(range(1, 11))
        for _, cov, status in rows:
            assert 0.0 <= cov <= 1.0
            assert status in ("OK", "NEEDS_REVIEW")
    finally:
        con.close()


# 11. Dedup registra sin borrar.
def test_p1_dedup_recorded():
    con = sqlite3.connect(KB)
    try:
        n = con.execute("SELECT COUNT(*) FROM chunks WHERE dup_of IS NOT NULL").fetchone()[0]
        assert n > 0
        dangling = con.execute(
            "SELECT COUNT(*) FROM chunks WHERE dup_of IS NOT NULL AND dup_of NOT IN (SELECT id FROM chunks)"
        ).fetchone()[0]
        assert dangling == 0
        vas = con.execute("SELECT COUNT(*), SUM(json_array_length(occurrences_json)) FROM visuals").fetchone()
        assert vas[0] > 0 and (vas[1] or 0) >= vas[0]
    finally:
        con.close()


# 12. Mapa de figuras (FIGS/IMGDATA/__IMG__) resuelto con alt como contexto.
def test_p1_imgdata_resolution():
    found, warnings = find_image_maps(FIG_HTML)
    assert warnings == []
    assert list(found) == ["fig11"]
    doc = parse_html(FIG_HTML)
    assert doc.sections[0].blocks[0].images[0]["fig_key"] == "fig11"
    assert "Poma" in doc.sections[0].blocks[0].images[0]["alt"]
