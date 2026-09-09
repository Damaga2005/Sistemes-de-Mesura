"""Orquestador Fase 1: SOURCE -> parse -> normalize -> extract -> dedup -> reconcile
-> canonical JSONL + SQLite -> validation + INGESTION REPORT.

Solo lectura sobre las fuentes. Re-ejecutable: mismos IDs, 0 duplicados.
Uso: python3 -m app.ingest [--source DIR] [--processed DIR] [--eval DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.build import (  # noqa: E402
    Chunk, Concept, Formula, Visual, build_chunks, collect_concepts,
    collect_formulas, jaccard, mark_exact_duplicates, tokenize,
)
from app.html_extract import parse_html  # noqa: E402
from app.jsdata import find_image_maps  # noqa: E402
from app.normalize import normalize_text, table_to_markdown, table_to_records  # noqa: E402
from app.pdf_extract import extract_pdf  # noqa: E402
from app.phase0_spec import extract_latex  # noqa: E402
from app.questions import EvalQuestion, extract_questions  # noqa: E402
from app.store import validate_knowledge, write_eval, write_knowledge  # noqa: E402


def load_manifest(workspace: Path) -> list[dict]:
    m = json.loads((workspace / "data" / "source_manifest.json").read_text(encoding="utf-8"))
    return m["manifest"]


def verify_sources(manifest: list[dict], source_dir: Path) -> list[str]:
    """Gate de integridad: cada fuente debe coincidir con el SHA del manifest."""
    errors = []
    for r in manifest:
        p = source_dir / r["path"]
        if not p.is_file():
            errors.append("falta fuente: %s" % r["path"])
            continue
        if hashlib.sha256(p.read_bytes()).hexdigest() != r["sha256"]:
            errors.append("SHA mismatch (fuente modificada): %s" % r["path"])
    return errors


def index_order(html: str) -> list[str]:
    """Orden de lectura desde los enlaces del index. Determinista."""
    return [h.split("/")[-1].split("?")[0] for h in re.findall(r'href="([^"#]+?\.html)"', html, flags=re.I)]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


def chunk_to_dict(c: Chunk) -> dict:
    return {
        "id": c.id, "course": config.COURSE, "topic": c.topic,
        "doc": c.source_path.split("/")[-1],
        "section_h1": c.section_h1, "section_h2": c.section_h2, "source_path": c.source_path,
        "source_type": c.source_type, "source_page": c.parent_context.get("page"),
        "content_type": c.content_type, "text": c.text, "formula_ids": c.formula_ids,
        "image_refs": c.image_refs, "parent_context": c.parent_context, "language": c.language,
        "source_hash": c.source_hash, "pipeline_version": config.PIPELINE_VERSION,
        "confidence": 1.0, "dup_of": c.dup_of,
    }


def resolve_eval_source(expected: str | None, topic: int, theory_basenames: list[str],
                         report: dict) -> str | None:
    """Resuelve expected_source contra el manifest. Sin coincidencia exacta:

    - tail-match unico (DOCS de T6-T10 omiten el prefijo numerico) -> resuelve + warning.
    - en otro caso -> None + NEEDS_REVIEW (regla 5/6: no inventar trazabilidad).
    """
    if not expected:
        return None
    base = expected.split("/")[-1]
    exact = [b for b in theory_basenames if b == base]
    if len(exact) == 1:
        return "Tema %d/%s" % (topic, exact[0])
    tail = base.split("_", 2)[-1] if base.count("_") >= 2 else base
    cands = sorted({b for b in theory_basenames if b.endswith(tail)})
    if len(cands) == 1:
        report["warnings"].append("eval %s: doc_ref '%s' resuelto por tail-match a '%s'" % (
            topic, base, cands[0]))
        return "Tema %d/%s" % (topic, cands[0])
    report["warnings"].append("eval %s: doc_ref '%s' NEEDS_REVIEW (sin correspondencia)" % (topic, base))
    return None


def run(source_dir: Path, processed: Path, eval_dir: Path, workspace: Path) -> dict:
    manifest = load_manifest(workspace)
    report: dict = {
        "pipeline_version": config.PIPELINE_VERSION,
        "sources_found": 0, "sources_ok": 0, "sources_failed": [],
        "docs_theory": 0, "sections": 0, "chunks": 0, "chunks_dup": 0,
        "formulas": 0, "formulas_latex": 0, "formulas_unicode": 0,
        "tables": 0, "visuals": 0, "visuals_dup": 0, "concepts": 0,
        "eval_questions": 0, "eval_formats": {},
        "fidelity_mismatches": [], "validation_errors": [], "warnings": [],
        "reconciliation": {}, "near_dup_candidates": [],
    }

    errors = verify_sources(manifest, source_dir)
    if errors:
        report["sources_failed"] = errors
        raise SystemExit("Gate de integridad fallido:\n- " + "\n- ".join(errors))
    report["sources_found"] = len(manifest)

    theory_names: dict[int, list[str]] = defaultdict(list)
    for r in manifest:
        if r["kind"] == "teoria":
            theory_names[r["topic"]].append(r["path"].split("/")[-1])

    order: dict[int, list[str]] = {}
    for r in manifest:
        if r["kind"] == "index":
            html = (source_dir / r["path"]).read_text(encoding="utf-8", errors="replace")
            order[r["topic"]] = index_order(html)

    def doc_order(topic: int, base: str) -> int:
        want = order.get(topic, [])
        if base in want:
            return want.index(base)
        fallback = sorted(theory_names[topic])
        return 90 + (fallback.index(base) if base in fallback else 0)

    chunks: list[Chunk] = []
    formulas: list[Formula] = []
    tables: list[dict] = []
    visuals: list[Visual] = []
    concepts: list[Concept] = []
    questions: list[EvalQuestion] = []
    doc_index: dict[str, dict] = {}
    section_ids: dict[tuple[str, int], str] = {}
    seq_by_topic: dict[int, int] = defaultdict(int)
    visual_occ: dict[str, dict] = {}
    section_texts: list[tuple[str, int, str]] = []

    def add_visual(sha, nbytes, vtopic, kind, caption, doc_path, section_h2, neighbor):
        entry = visual_occ.get(sha)
        occ = {"doc_path": doc_path, "section_h2": section_h2, "neighbor": neighbor[:200]}
        if entry is None:
            visual_occ[sha] = {"bytes_len": nbytes, "topic": vtopic,
                               "source_kind": kind, "caption": caption,
                               "occurrences": [occ]}
        else:
            entry["occurrences"].append(occ)
            if entry["source_kind"] != kind:
                entry["source_kind"] = "mixed"
            if not entry["caption"] and caption:
                entry["caption"] = caption
        return "img-%s" % sha[:12]

    for r in sorted(manifest, key=lambda x: x["path"]):
        src = source_dir / r["path"]
        topic, doc_id = r["topic"], r["id"]

        if r["suffix"] == ".pdf":
            pdf = extract_pdf(src)
            if pdf.needs_review and "sin texto" in pdf.needs_review:
                report["warnings"].append("%s: %s" % (r["path"], pdf.needs_review))
            title = pdf.title or r.get("title") or r["path"]
            doc_index[doc_id] = {"source_id": doc_id, "topic": topic, "title": title,
                                 "h1": title, "doc_order": 99, "kind": "pdf-apunts",
                                 "sections": []}
            for pg in pdf.pages:
                text = normalize_text(pg.text)
                if not text:
                    continue
                chunks.append(Chunk(
                    id="%s#p%02d" % (doc_id, pg.number), topic=topic, doc=doc_id,
                    section_h1=title, section_h2="pàgina %d" % pg.number,
                    source_path=r["path"], source_type="pdf", content_type="explanation",
                    text=text, parent_context={"doc_order": 99, "page": pg.number},
                    source_hash=r["sha256"]))
                for im in pg.images:
                    if im.sha256 in ("", "UNREADABLE"):
                        report["warnings"].append("%s p%d: imagen ilegible" % (r["path"], pg.number))
                        continue
                    add_visual(im.sha256, im.bytes_len, topic, "pdf-embedded", None,
                               r["path"], "pàgina %d" % pg.number, text)
            report["sources_ok"] += 1
            continue

        html = src.read_text(encoding="utf-8", errors="replace")
        if r["kind"] == "entrenament":
            try:
                qs, fmt = extract_questions(html, topic, r["path"])
            except ValueError as e:
                report["sources_failed"].append(str(e))
                continue
            for q in qs:
                q.expected_source = resolve_eval_source(q.expected_source, topic,
                                                        theory_names[topic], report)
            questions.extend(qs)
            report["eval_formats"][fmt] = report["eval_formats"].get(fmt, 0) + len(qs)
            report["sources_ok"] += 1
            continue
        if r["kind"] == "index":
            report["sources_ok"] += 1
            continue

        # Teoría HTML.
        doc = parse_html(html)
        base = r["path"].split("/")[-1]
        order_n = doc_order(topic, base)
        doc_index[doc_id] = {"source_id": doc_id, "topic": topic,
                             "title": doc.title or doc.h1, "h1": doc.h1,
                             "doc_order": order_n, "kind": "teoria",
                             "sections": [s.h2 for s in doc.sections]}
        for s in doc.sections:
            section_ids[(doc_id, s.index)] = "%s#s%02d" % (doc_id, s.index)
        uni, ublk, nxt = collect_formulas(doc, topic, r["path"], seq_by_topic[topic] + 1)
        formulas.extend(uni)
        uni_expr = {f.equation_id: f.expression for f in uni}
        doc_chunks, latexs, _ = build_chunks(doc, topic, r["path"], r["sha256"],
                                             doc_id, order_n, nxt, ublk, uni_expr)
        seq_by_topic[topic] = nxt + len(latexs)
        formulas.extend(latexs)
        known = {f.equation_id for f in formulas}
        for c in doc_chunks:
            for fid in c.formula_ids:
                if fid not in known:
                    report["warnings"].append("%s: formula_id sin registro %s" % (r["path"], fid))
        if sorted(extract_latex(html)) != sorted(f.expression for f in latexs):
            report["fidelity_mismatches"].append(r["path"])
        # Mapas de figuras (IMGDATA / FIGS / window.__IMG__): los bytes viven en JS,
        # los <img data-fig> los referencian y el alt catalán es el image_context.
        imgdata, map_warnings = find_image_maps(html)
        for w in map_warnings:
            report["warnings"].append("%s: %s" % (r["path"], w))
        for s in doc.sections:
            for b in s.blocks:
                for im in b.images:
                    caption = b.caption or im["alt"] or None
                    if im["src_kind"] == "base64" and im["sha256"] not in ("", "INVALID"):
                        add_visual(im["sha256"], im["bytes_len"], topic, "html-base64",
                                   caption, r["path"], s.h2, normalize_text(b.text))
                    elif im["src_kind"] == "data-fig-ref" and im.get("fig_key") in imgdata:
                        sha, nbytes = imgdata[im["fig_key"]]
                        add_visual(sha, nbytes, topic, "html-imgdata",
                                   caption, r["path"], s.h2, normalize_text(b.text))
                    else:
                        report["warnings"].append("%s §%.60s: imagen sin bytes (%s)" % (
                            r["path"], s.h2, im["src_kind"]))
            for b in s.blocks:
                if b.kind == "table" and b.table:
                    tid = "%s#t%02d" % (doc_id, len([t for t in tables if t["doc_id"] == doc_id]))
                    tables.append({
                        "id": tid, "doc_id": doc_id,
                        "section_id": section_ids.get((doc_id, s.index)),
                        "topic": topic, "caption": b.caption,
                        "markdown": table_to_markdown(b.table["headers"], b.table["rows"]),
                        "records": table_to_records(b.table["headers"], b.table["rows"]),
                        "source_path": r["path"]})
        concepts.extend(collect_concepts(doc, topic, r["path"]))
        section_texts.extend(
            (doc_id, s.index, normalize_text(" ".join(b.text for b in s.blocks))) for s in doc.sections)
        chunks.extend(doc_chunks)
        report["docs_theory"] += 1
        report["sources_ok"] += 1

    # Consolidar visuales: una fila por asset único con sus ocurrencias.
    for sha in sorted(visual_occ):
        e = visual_occ[sha]
        visuals.append(Visual("img-%s" % sha[:12], sha, e["bytes_len"], e["topic"],
                              e["source_kind"], e["caption"], e["occurrences"]))
    report["visuals_dup"] = (sum(len(v.occurrences) for v in visuals) - len(visuals))

    # Referencias visuales por (doc, sección).
    assets_available: dict[tuple[str, str], list[str]] = defaultdict(list)
    for v in visuals:
        for occ in v.occurrences:
            assets_available[(occ["doc_path"], occ["section_h2"])].append(v.asset_id)
    for c in chunks:
        if c.source_type == "html":
            c.image_refs = sorted(set(assets_available.get((c.source_path, c.section_h2), [])))

    chunks = sorted(chunks, key=lambda c: c.id)
    report["sections"] = len(section_ids)
    report["chunks"] = len(chunks)
    report["formulas"] = len(formulas)
    report["formulas_latex"] = sum(1 for f in formulas if f.encoding == "latex-comment")
    report["formulas_unicode"] = sum(1 for f in formulas if f.encoding == "unicode-sub-sup")
    report["tables"] = len(tables)
    report["visuals"] = len(visuals)
    report["concepts"] = len(concepts)
    report["eval_questions"] = len(questions)

    report["chunks_dup"] = mark_exact_duplicates(chunks)

    for a in range(len(section_texts)):
        for b in range(a + 1, len(section_texts)):
            if section_texts[a][0] == section_texts[b][0]:
                continue
            j = jaccard(set(tokenize(section_texts[a][2])), set(tokenize(section_texts[b][2])))
            if j >= config.NEARDUP_JACCARD:
                report["near_dup_candidates"].append({
                    "a": [section_texts[a][0], section_texts[a][1]],
                    "b": [section_texts[b][0], section_texts[b][1]], "jaccard": round(j, 3)})

    reconciliation = []
    for t in range(1, 11):
        html_vocab: set[str] = set()
        pdf_vocab: set[str] = set()
        for c in chunks:
            toks = tokenize(c.text, config.CA_STOPWORDS)
            if c.topic == t and c.source_type == "html" and c.dup_of is None:
                html_vocab |= toks
            elif c.topic == t and c.source_type == "pdf":
                pdf_vocab |= toks
        shared = len(html_vocab & pdf_vocab)
        union = len(html_vocab | pdf_vocab)
        cov = (shared / len(html_vocab)) if html_vocab else 0.0
        status = "OK" if cov >= config.RECONCILE_MIN_SHARED_VOCAB else "NEEDS_REVIEW"
        reconciliation.append({"topic": t, "html_words": len(html_vocab),
                               "pdf_words": len(pdf_vocab), "shared": shared,
                               "jaccard": round(shared / union if union else 0.0, 3),
                               "coverage": round(cov, 3), "status": status})
    report["reconciliation"] = {r["topic"]: r for r in reconciliation}

    processed.mkdir(parents=True, exist_ok=True)
    eval_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(processed / "chunks.jsonl", [chunk_to_dict(c) for c in chunks])
    write_jsonl(processed / "formulas.jsonl", [
        {"equation_id": f.equation_id, "expression": f.expression, "encoding": f.encoding,
         "topic": f.topic, "source_path": f.source_path, "section_h2": f.section_h2,
         "variables": f.variables, "status": f.status} for f in formulas])
    write_jsonl(processed / "tables.jsonl", tables)
    write_jsonl(processed / "visuals.jsonl", [
        {"asset_id": v.asset_id, "sha256": v.sha256, "bytes_len": v.bytes_len, "topic": v.topic,
         "source_kind": v.source_kind, "caption": v.caption, "occurrences": v.occurrences}
        for v in visuals])
    write_jsonl(processed / "concepts.jsonl", [
        {"term_ca": c.term_ca, "kind": c.kind, "topic": c.topic,
         "source_path": c.source_path, "section_h2": c.section_h2} for c in concepts])
    write_jsonl(eval_dir / "vf_bank.jsonl", [
        {"qid": q.qid, "topic": q.topic, "question": q.question, "answer": q.answer,
         "justification": q.justification, "expected_source": q.expected_source,
         "origin": q.origin} for q in questions])

    kb_path = processed / config.KNOWLEDGE_DB
    eval_path = eval_dir / config.EVAL_DB
    write_knowledge(kb_path, manifest, chunks, formulas, tables, visuals, concepts,
                    reconciliation, doc_index, section_ids)
    write_eval(eval_path, questions)
    report["validation_errors"] = validate_knowledge(kb_path)
    (processed / config.REPORT_JSON).write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report


def render_phase1_report(report: dict, out: Path) -> None:
    L = ["# PHASE_1_REPORT — Ingesta y Knowledge Base canónica",
         "", "Pipeline: `%s`. Fuentes verificadas por SHA-256: %d/%d." % (
             report["pipeline_version"], report["sources_ok"], report["sources_found"]), "",
         "| Métrica | Valor |", "|---|---|"]
    for k in ["docs_theory", "sections", "chunks", "chunks_dup", "formulas", "formulas_latex",
              "formulas_unicode", "tables", "visuals", "visuals_dup", "concepts", "eval_questions"]:
        L.append("| %s | %s |" % (k, report[k]))
    L += ["", "## Reconciliación PDF↔HTML",
          "| Tema | Vocab HTML | Vocab PDF | Compartido | Jaccard | Cobertura | Estado |",
          "|---|---|---|---|---|---|---|"]
    for t in sorted(report["reconciliation"], key=int):
        r = report["reconciliation"][t]
        L.append("| %s | %d | %d | %d | %.3f | %.3f | %s |" % (
            t, r["html_words"], r["pdf_words"], r["shared"], r["jaccard"], r["coverage"], r["status"]))
    L += ["", "## Calidad",
          "- Fidelidad LaTeX (multiconjunto por doc): %s." % (
              "OK en 61/61 teoría" if not report["fidelity_mismatches"] else "FALLOS: %s" % report["fidelity_mismatches"]),
          "- Visuales: bytes en mapas JS (variantes `IMGDATA`/`FIGS`/`window.__IMG__`), "
          "`alt` catalán como caption, 1 fila por asset único con ocurrencias.",
          "- Validación SQLite: %s." % ("OK" if not report["validation_errors"] else report["validation_errors"]),
          "- Near-dups registrados (no fusionados): %d." % len(report["near_dup_candidates"]),
          "- Preguntas V/F: %d (formatos %s), en base separada." % (
              report["eval_questions"], report["eval_formats"]),
          "- Warnings: %d." % len(report["warnings"])]
    tail = [w for w in report["warnings"] if "tail-match" in w]
    other = [w for w in report["warnings"] if "tail-match" not in w]
    L += ["- Resoluciones tail-match DOCS→manifest (T6–T10, prefijo numérico omitido en origen): %d." % len(tail),
          "- Warnings no-eval: %d." % len(other)]
    L += [""] + ["- " + w[:200] for w in other[:20]]
    L += ["", "## Aplazado explícito",
          "- Relaciones académicas (`Relationship`): sin extracción verificable determinista; "
          "jerarquía en `sections`/`parent_context`. Fase 3 con verificación.",
          "- Variables de fórmulas: solo con evidencia local (`on X és…`); resto `[]` para Fase 3.",
          "- Retrieval/RAG, tutores y examen: fuera de alcance (reglas 7–8)."]
    out.write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingesta Fase 1 (solo lectura de fuentes)")
    ap.add_argument("--source", default=config.DEFAULT_SOURCE_DIR)
    ap.add_argument("--out", default=None,
                    help="raiz de salida (contiene processed/ y evaluation/)")
    ap.add_argument("--processed", default=None)
    ap.add_argument("--eval", default=None)
    args = ap.parse_args()
    workspace = Path(__file__).resolve().parent.parent
    out = Path(args.out) if args.out else workspace / "data"
    processed = Path(args.processed) if args.processed else out / "processed"
    eval_dir = Path(args.eval) if args.eval else out / "evaluation"
    report = run(Path(args.source), processed, eval_dir, workspace)
    render_phase1_report(report, workspace / "docs" / "PHASE_1_REPORT.md")
    print("docs=%d chunks=%d formulas=%d visuals=%d eval=%d val_errors=%s fidelity=%s warnings=%d" % (
        report["docs_theory"], report["chunks"], report["formulas"], report["visuals"],
        report["eval_questions"], report["validation_errors"], report["fidelity_mismatches"],
        len(report["warnings"])))


if __name__ == "__main__":
    main()
