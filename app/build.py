"""Construccion canonica: formulas, chunks semanticos, conceptos, dedup, reconciliacion.

Determinista, sin LLM. La expresion LaTeX se conserva verbatim; las variables
se extraen con patrones explicitos (catala) y solo cuando hay evidencia local.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from .config import PARAGRAPH_MERGE_LIMIT
from .html_extract import BOX_TYPE_MAP, Block, HtmlDocument
from .normalize import normalize_text, split_sentences, table_to_markdown

# "on U és ..." / "amb k el factor ..." — evidencia local de variable (català).
_VAR_PATTERNS = [
    re.compile(r"\bon\s+\$?([A-Za-z][\w]*)\$?\s+(?:és|es|denota|representa|indica)\s+([^.;]{3,160})"),
    re.compile(r"\bamb\s+\$?([A-Za-z][\w]*)\$?\s+(?:el|la|com)\s+([^.;]{3,160})"),
]

_SUB_RE = re.compile(r"<sub>(.*?)</sub>", re.S)
_SUP_RE = re.compile(r"<sup>(.*?)</sup>", re.S)


@dataclass
class Formula:
    equation_id: str
    expression: str  # LaTeX verbatim del comentario, o conversion _{}/^{} trazada
    encoding: str  # latex-comment | unicode-sub-sup
    raw: str
    topic: int
    source_path: str
    section_h2: str
    variables: list[dict] = field(default_factory=list)
    status: str = "OK"


@dataclass
class Chunk:
    id: str
    topic: int
    doc: str
    section_h1: str
    section_h2: str
    source_path: str
    source_type: str
    content_type: str
    text: str
    formula_ids: list[str] = field(default_factory=list)
    image_refs: list[str] = field(default_factory=list)
    parent_context: dict = field(default_factory=dict)
    language: str = "ca"
    source_hash: str = ""
    dup_of: str | None = None


@dataclass
class Visual:
    asset_id: str
    sha256: str
    bytes_len: int
    topic: int
    source_kind: str  # html-base64 | pdf-embedded | mixed
    caption: str | None  # de la primera ocurrencia
    occurrences: list[dict] = field(default_factory=list)  # {doc_path, section_h2, neighbor}


@dataclass
class Concept:
    term_ca: str
    kind: str  # section | subsection
    topic: int
    source_path: str
    section_h2: str


def guess_variables(text: str) -> list[dict]:
    """Variables con evidencia local explícita. Sin evidencia -> []. Nunca inventa."""
    found: dict[str, dict] = {}
    for pat in _VAR_PATTERNS:
        for m in pat.finditer(text):
            sym, meaning = m.group(1), m.group(2).strip()
            if sym not in found:
                found[sym] = {"sym": sym, "meaning": meaning, "unit": ""}
    return list(found.values())


def sub_sup_to_latex(text: str) -> str:
    """Convierte marcadores <sub>/<sup> a _{}/^{}. Trazado vía encoding, no silencioso."""
    t = _SUB_RE.sub(r"_{\1}", text)
    t = _SUP_RE.sub(r"^{\1}", t)
    return t


def collect_formulas(
    doc: HtmlDocument, topic: int, source_path: str, start_seq: int
) -> tuple[list[Formula], dict[tuple[int, int], list[str]], int]:
    """Fórmulas unicode-sub-sup (Tema 1) por bloque. Devuelve (formulas, (sec,blk)->ids, next_seq).

    Las fórmulas latex-comment se asignan inline en build_chunks para conservar
    la asociación bloque<->fórmula exacta.
    """
    formulas: list[Formula] = []
    by_block: dict[tuple[int, int], list[str]] = {}
    seq = start_seq
    for sec in doc.sections:
        context_text = normalize_text(" ".join(b.text for b in sec.blocks)[:3000])
        variables = guess_variables(context_text)
        for pos, b in enumerate(sec.blocks):
            if ("<sub>" in b.html_inner or "<sup>" in b.html_inner) and b.text.strip():
                eid = "eq-%02d-%04d" % (topic, seq)
                seq += 1
                formulas.append(
                    Formula(
                        eid,
                        sub_sup_to_latex(normalize_text(b.text)),
                        "unicode-sub-sup",
                        b.text[:2000],
                        topic,
                        source_path,
                        sec.h2,
                        variables,
                    )
                )
                by_block.setdefault((sec.index, pos), []).append(eid)
    return formulas, by_block, seq


def _block_content_type(b: Block) -> str:
    if b.kind == "box":
        return BOX_TYPE_MAP.get(b.box_type or "", "explanation")
    if b.kind == "table":
        return "table"
    if b.kind == "figure":
        return "image_context"
    if b.kind == "code":
        return "example"
    if b.kind == "heading3":
        return "concept"
    return "explanation"


def build_chunks(
    doc: HtmlDocument,
    topic: int,
    source_path: str,
    source_hash: str,
    doc_id: str,
    doc_order: int,
    latex_seq_start: int,
    unicode_by_block: dict[tuple[int, int], list[str]],
    unicode_expr: dict[str, str] | None = None,
) -> tuple[list[Chunk], list[Formula], dict[int, list[str]]]:
    """Chunks semánticos + fórmulas latex-comment asignadas a su bloque exacto.

    Devuelve (chunks, formulas, visuals_por_seccion_idx). Un chunk por bloque
    tipado; párrafos/listas consecutivos se fusionan (<=límite, corte en frase).
    """
    chunks: list[Chunk] = []
    formulas: list[Formula] = []
    visuals_idx: dict[int, list[str]] = {}
    seq = latex_seq_start
    n_secs = len(doc.sections)
    expr_of: dict[str, str] = dict(unicode_expr or {})

    def alloc(exprs: list[str], sec_h2: str, variables: list[dict]) -> list[str]:
        nonlocal seq
        ids = []
        for expr in exprs:
            eid = "eq-%02d-%04d" % (topic, seq)
            seq += 1
            formulas.append(Formula(eid, expr, "latex-comment", expr, topic, source_path, sec_h2, variables))
            expr_of[eid] = expr
            ids.append(eid)
        return ids

    def parent(i: int) -> dict:
        prev_h2 = doc.sections[i - 1].h2 if i > 0 else None
        next_h2 = doc.sections[i + 1].h2 if i < n_secs - 1 else None
        return {"doc_order": doc_order, "section_index": i, "prev_section": prev_h2, "next_section": next_h2}

    for i, sec in enumerate(doc.sections):
        context_text = normalize_text(" ".join(b.text for b in sec.blocks)[:3000])
        variables = guess_variables(context_text)
        # Latex suelto a nivel de sección (fuera de bloques): irá al primer chunk.
        stray_ids = alloc(sec.latex, sec.h2, variables)
        stray_exprs = [expr_of[fid] for fid in stray_ids]
        pending: list[str] = []
        pending_fids: list[str] = []
        c_idx = 0
        first_chunk_done = False

        def _mk(text: str, ctype: str, fids: list[str], extra_latex: list[str]) -> Chunk:
            body = text
            if extra_latex:
                body = text + "\n" + "\n".join(extra_latex)
            elif fids and ctype == "explanation":
                body = text + "\n" + "\n".join(expr_of[f] for f in fids)
            return Chunk(
                id="%s#s%02dc%02d" % (doc_id, sec.index, c_idx),
                topic=topic,
                doc=doc_id,
                section_h1=doc.h1,
                section_h2=sec.h2,
                source_path=source_path,
                source_type="html",
                content_type=ctype,
                text=body,
                formula_ids=list(fids),
                image_refs=[],
                parent_context=parent(i),
                source_hash=source_hash,
            )

        def flush_pending() -> None:
            nonlocal c_idx, first_chunk_done
            if not pending:
                return
            text = normalize_text(" ".join(pending))
            fids = list(pending_fids)
            if not first_chunk_done:
                fids = stray_ids + fids
                first_chunk_done = True
            if len(text) > PARAGRAPH_MERGE_LIMIT:
                # Corte en fin de frase; el primer trozo conserva las fórmulas.
                acc = ""
                first_piece = True
                for s in split_sentences(text):
                    if len(acc) + len(s) + 1 > PARAGRAPH_MERGE_LIMIT and acc:
                        chunks.append(_mk(acc, "explanation", fids if first_piece else [], []))
                        c_idx += 1
                        first_piece = False
                        fids = []
                        acc = s
                    else:
                        acc = (acc + " " + s).strip()
                if acc.strip():
                    chunks.append(_mk(acc.strip(), "explanation", fids if first_piece else [], []))
                    c_idx += 1
            else:
                chunks.append(_mk(text, "explanation", fids, []))
                c_idx += 1
            pending.clear()
            pending_fids.clear()

        for pos, b in enumerate(sec.blocks):
            if b.kind in ("paragraph", "list") and b.text.strip():
                if len(normalize_text(" ".join(pending + [b.text]))) > PARAGRAPH_MERGE_LIMIT and pending:
                    flush_pending()
                pending.append(b.text)
                # El latex dentro de <p> también es fórmula canónica: se asigna aquí.
                pending_fids.extend(alloc(b.latex, sec.h2, variables))
                pending_fids.extend(unicode_by_block.get((sec.index, pos), []))
            else:
                flush_pending()
                ctype = _block_content_type(b)
                fids = alloc(b.latex, sec.h2, variables)
                fids += unicode_by_block.get((sec.index, pos), [])
                if not first_chunk_done:
                    fids = stray_ids + fids
                    first_chunk_done = True
                if b.kind == "table" and b.table:
                    md = table_to_markdown(b.table["headers"], b.table["rows"])
                    chunks.append(_mk("Taula. %s\n%s" % (b.caption or sec.h2, md), ctype, fids, []))
                elif b.kind == "figure" and (b.text.strip() or b.caption or b.latex or b.images):
                    cap = ("Figura. %s. " % b.caption) if b.caption else "Figura. "
                    alts = "; ".join(im["alt"] for im in b.images if im.get("alt"))
                    fig_text = cap + b.text + (" [imatge: %s]" % alts if alts else "")
                    chunks.append(_mk(fig_text, ctype, fids, b.latex))
                elif b.kind in ("box", "heading3", "code") and (b.text.strip() or b.latex):
                    chunks.append(_mk(b.text, ctype, fids, [] if ctype == "explanation" else b.latex))
                c_idx += 1
        flush_pending()
        if not first_chunk_done and stray_ids:
            # Sección solo con latex suelto: chunk de fórmulas.
            chunks.append(_mk("\n".join(stray_exprs), "formula", stray_ids, []))
    # Índices secuenciales por sección (determinista).
    counters: dict[int, int] = {}
    for c in chunks:
        s = c.parent_context["section_index"]
        c.id = "%s#s%02dc%02d" % (doc_id, s, counters.get(s, 0))
        counters[s] = counters.get(s, 0) + 1
    # Referencias visuales por sección (se resuelven en ingest con asset_ids reales).
    for c in chunks:
        visuals_idx.setdefault(c.parent_context["section_index"], [])
    return chunks, formulas, visuals_idx


def mark_exact_duplicates(chunks: list[Chunk]) -> int:
    """dup_of al primer chunk con texto normalizado idéntico. Devuelve nº marcados."""
    seen: dict[str, str] = {}
    n = 0
    for c in chunks:
        h = hashlib.sha256(c.text.encode("utf-8")).hexdigest()
        if h in seen:
            c.dup_of = seen[h]
            n += 1
        else:
            seen[h] = c.id
    return n


def tokenize(text: str, stopwords: frozenset = frozenset()) -> set[str]:
    words = re.findall(r"[a-zà-ÿ][a-zà-ÿ0-9_·'-]{2,}", text.lower())
    return {w for w in words if w not in stopwords}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def collect_concepts(doc: HtmlDocument, topic: int, source_path: str) -> list[Concept]:
    out = []
    for sec in doc.sections:
        if sec.h2.strip():
            out.append(Concept(sec.h2.strip(), "section", topic, source_path, sec.h2.strip()))
        for b in sec.blocks:
            if b.kind == "heading3" and b.text.strip():
                out.append(Concept(b.text.strip(), "subsection", topic, source_path, sec.h2.strip()))
    return out
