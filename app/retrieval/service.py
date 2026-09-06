"""RetrievalService: orquesta ramas -> fusion -> ranking -> rerank -> abstencion.

Implementa el protocolo Retriever. Sin LLM, sin red, determinista.
La consulta se trata siempre como datos, nunca como instrucciones (§66).
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from app.embeddings.interface import TfidfEmbeddingProvider

from . import config as cfg
from .abstention import conflict_warning, decide
from .classify import classify
from .context import ContextExpander
from .evidence import assemble
from .formula import FormulaIndex, query_symbols
from .hybrid import rrf_fuse
from .lexical import LexicalIndex
from .metadata import apply_filters
from .models import EvidencePack, RetrievalFilters, RetrievalQuery, RetrievalResponse, RetrievalResult
from .normalize_query import STOPWORDS, directive_spans, extract_topic_mention, normalize_query, query_terms
from .ranking import rank
from .reranking import Reranker
from .semantic import TfidfIndex
from .synonyms import expand_es_ca, fuzzy_correct


class RetrievalService:
    def __init__(self, kb_path: str | Path, index_dir: str | Path) -> None:
        self.kb_path = str(kb_path)
        self.index_dir = Path(index_dir)
        self.lexical = LexicalIndex(self.index_dir / "lexical" / "fts.sqlite")
        self.semantic = TfidfIndex.load(self.index_dir / "semantic", stopwords=STOPWORDS)
        self.embeddings = TfidfEmbeddingProvider(self.semantic)
        from .ranking import _stems as _stem_fn
        vocab_stems: set[str] = set()
        for _vt in self.semantic.vocab:
            vocab_stems |= _stem_fn(_vt)
        self._vocab_stems = vocab_stems
        self.formulas = FormulaIndex()
        self.formulas.build(self.kb_path)
        self.reranker = Reranker()
        self.expander = ContextExpander(self.kb_path)
        self._sections: list[dict] = []  # {h2, words, doc_id, topic, chunks[]}
        self._chunks: dict[str, dict] = {}
        self._formula_chunks: dict[str, list[str]] = {}
        self._doc_source: dict[str, str] = {}
        con = sqlite3.connect("file:%s?mode=ro" % self.kb_path, uri=True)
        try:
            for sid, mid in con.execute("SELECT id, source_id FROM documents"):
                self._doc_source[sid] = mid
            for r in con.execute(
                    "SELECT c.id, c.doc_id, c.topic, c.source_path, c.source_hash, c.content_type,"
                    " c.text, c.formula_ids, c.image_refs, c.parent_context, c.dup_of,"
                    " s.h2, d.h1 FROM chunks c LEFT JOIN documents d ON d.id=c.doc_id"
                    " LEFT JOIN sections s ON s.id=c.section_id"):
                (cid, doc_id, topic, spath, sha, ctype, text, fids, irefs,
                 pctx, dup, h2, h1) = r
                fids_l = json.loads(fids or "[]")
                self._chunks[cid] = {
                    "doc_id": doc_id, "topic": topic, "source_path": spath,
                    "source_hash": sha, "content_type": ctype, "text": text,
                    "formula_ids": fids_l,
                    "image_refs": json.loads(irefs or "[]"),
                    "parent": json.loads(pctx or "{}"), "dup": dup,
                    "section": h2, "h1": h1 or "",
                    "source_type": "pdf" if "Apunts" in spath else "html"}
                for fid in fids_l:
                    self._formula_chunks.setdefault(fid, []).append(cid)
            sec_chunks: dict[str, list[str]] = {}
            for cid, m in self._chunks.items():
                sec = m.get("section") or ""
                if sec.strip():
                    sec_chunks.setdefault(m["doc_id"] + "\x00" + sec, []).append(cid)
            for key, cids in sec_chunks.items():
                doc_id, h2 = key.split("\x00")
                self._sections.append({
                    "h2": h2, "words": set(query_terms(h2)), "doc_id": doc_id,
                    "chunks": sorted(cids)})
        finally:
            con.close()

    def retrieve(self, query: str, *, filters: RetrievalFilters | None = None,
                 top_k: int = cfg.DEFAULT_TOP_K, debug: bool = False) -> RetrievalResponse:
        t0 = time.perf_counter()
        norm = normalize_query(query)
        topic_mentioned, unknown_topic = extract_topic_mention(norm)
        qtype = classify(norm)
        eff_topic = filters.topic if filters and filters.topic is not None else topic_mentioned
        allowed = apply_filters(self.kb_path, filters)

        # Expansion por termino: {original: [original, sinonimos, morfologicas, fuzzy]}.
        # El matching usa mejor-variante (recall); lo no resoluble cuenta como OOV.
        vocab = set(self.semantic.vocab)
        terms = query_terms(norm)
        variant_map: dict[str, list[str]] = {}
        fuzzy_map: dict[str, str] = {}
        for t in terms:
            vs = [t]
            # Solo se conservan expansiones presentes en el vocabulario del indice:
            # una conversion inexistente no aporta recall y ensuciaria el matching.
            for cand in expand_es_ca([t])[1:]:
                if cand in vocab and cand not in vs:
                    vs.append(cand)
            if t not in vocab and len(t) >= cfg.FUZZY_MIN_LEN:
                corr = fuzzy_correct(t, vocab, min_len=cfg.FUZZY_MIN_LEN,
                                     max_dist=cfg.FUZZY_MAX_DIST)
                if corr and corr not in vs:
                    vs.append(corr)
                    fuzzy_map[t] = corr
            variant_map[t] = vs
        directives = set(directive_spans(norm))
        scoring_map = {t: vs for t, vs in variant_map.items() if t not in directives}
        search_text = " ".join(v for vs in variant_map.values() for v in vs)
        # OOV por stems (plural catalan 'ladors'~'lador'): lo flexivo no es
        # desconocimiento; lo ausente de verdad ('president') si.
        from .ranking import _stems as _stem2

        def _known(term: str, variants: list[str]) -> bool:
            if any(v in vocab for v in variants):
                return True
            return bool(_stem2(term) & self._vocab_stems)

        unknown_terms = sum(1 for t, vs in variant_map.items()
                            if len(t) >= 4 and not _known(t, vs))

        lex_hits = self.lexical.search(search_text, cfg.CANDIDATE_K)
        sem_hits = self.semantic.search(search_text, cfg.CANDIDATE_K)
        form_hits = self.formulas.search(search_text, 20)

        lex_rank = [h.chunk_id for h in lex_hits]
        sem_rank = [h.chunk_id for h in sem_hits]
        form_chunk_rank: list[str] = []
        for fh in form_hits:
            form_chunk_rank.extend(self._formula_chunks.get(fh.equation_id, []))
        fused = rrf_fuse([lex_rank, sem_rank, form_chunk_rank])

        lex_map = {h.chunk_id: h.rank for h in lex_hits}
        sem_map = {h.chunk_id: h.score for h in sem_hits}
        form_map: dict[str, float] = {}
        strong_formulas: set[str] = set()
        for fh in form_hits:
            if fh.score >= 0.3:
                strong_formulas.add(fh.equation_id)
            for cid in self._formula_chunks.get(fh.equation_id, []):
                form_map[cid] = max(form_map.get(cid, 0.0), fh.score)

        # Cobertura exacta para bonus de ranking + evidencia suficiente (abstencion).
        from .formula import symbols_of as _syms0
        raw_syms0 = _syms0(norm)
        symbol_signal = bool(raw_syms0 & self.formulas.math_universe())
        lookup_cover: dict[str, float] = {}
        if symbol_signal:
            qwords_lu = set(query_terms(norm)) - directives
            for hit in self.formulas.lookup(raw_syms0, qwords_lu, limit=400):
                if hit["coverage"] >= 1.0:
                    for cid in self._formula_chunks.get(hit["equation_id"], []):
                        lookup_cover[cid] = max(lookup_cover.get(cid, 0.0), hit["score"])

        # Expansion de seccion: si la query nombra una seccion (>=2 palabras, >=50%),
        # sus chunks son evidencia natural (filosofia de contexto, §25).
        sec_expanded: set[str] = set()
        qwords = set(query_terms(search_text)) - directives
        if len(qwords) >= 2:
            best, best_shared = None, set()
            for sec in self._sections:
                shared = qwords & sec["words"]
                if len(shared) >= 2 and len(shared) / len(qwords) >= 0.5:
                    if best is None or len(shared) > len(best_shared):
                        best, best_shared = sec, shared
            if best is not None:
                sec_expanded = set(best["chunks"])

        candidates: dict[str, dict] = {}
        # Orden determinista: RRF primero, expansion de seccion despues (ordenada).
        for cid in list(fused) + sorted(c for c in sec_expanded if c not in fused):
            meta = self._chunks.get(cid)
            if not meta:
                continue
            if allowed is not None and cid not in allowed:
                continue
            candidates[cid] = {
                "lex": lex_map.get(cid), "sem": sem_map.get(cid), "form": form_map.get(cid),
                "chunk_topic": meta["topic"], "source": meta["source_type"],
                "dup": meta["dup"], "section_match": True,
                "content_type": meta["content_type"], "text": meta["text"],
                # La identidad del chunk incluye su jerarquia (h2/h1): la masa
                # y la frase se miden sobre el contexto, no solo el cuerpo.
                "context": "%s %s %s" % (meta["section"] or "", meta["h1"] or "",
                                         meta["text"]),
                "sec_expansion": cid in sec_expanded,
                "lookup_cover": lookup_cover.get(cid, 0.0)}

        ranked = rank(candidates, scoring_map or variant_map, norm, self.semantic.idf, eff_topic,
                      section_filter=filters.section if filters else None,
                      query_type=qtype, symbol_signal=symbol_signal)
        ordered = sorted(ranked, key=lambda c: -ranked[c]["final"])
        rows = []
        for cid in ordered[: max(top_k, cfg.RERANK_DEPTH)]:
            m = self._chunks[cid]
            rows.append({"chunk_id": cid, "final": ranked[cid]["final"],
                         "components": ranked[cid]["components"],
                         "source_type": m["source_type"], "text": m["text"],
                         "topic": m["topic"]})
        rows = self.reranker.rerank(rows)
        rows = rows[:top_k]

        results: list[RetrievalResult] = []
        for r in rows:
            m = self._chunks[r["chunk_id"]]
            results.append(RetrievalResult(
                chunk_id=r["chunk_id"], score=r["final"], final_score=r["final"],
                source_id=self._doc_source.get(m["doc_id"], ""),
                source_path=m["source_path"], source_hash=m["source_hash"],
                topic=m["topic"], section=m["section"], text=m["text"],
                evidence_type="hybrid", formula_ids=m["formula_ids"],
                image_refs=m["image_refs"], parent_context=m["parent"],
                components=r.get("components", {}), warnings=r.get("warnings", [])))

        formula_top_flag = any(
            fid in strong_formulas for r in results[:3] for fid in r.formula_ids)
        mass_top = max([ranked[r["chunk_id"]]["mass"] for r in rows[:3]],
                       default=0.0) if rows else 0.0
        decision = decide([{"final": r.final_score} for r in results],
                          unknown_topic=unknown_topic, unknown_terms=unknown_terms,
                          phrase_top=(rows[0]["components"].get("phrase", 0.0) if rows else 0.0),
                          formula_top=formula_top_flag, mass_top=mass_top,
                          intent_routed=qtype in ("FORMULA", "VARIABLE", "DEFINITION"),
                          has_words=any(len(t) >= 3 for t in scoring_map),
                          has_lookup=self._lookup_evidence(query))
        warnings: list[str] = []
        cw = conflict_warning([{"final": r.final_score, "chunk_id": r.chunk_id,
                                "topic": r.topic} for r in results])
        if cw:
            warnings.append(cw)
        for r in results:
            warnings.extend(r.warnings)
        latency = round((time.perf_counter() - t0) * 1000, 2)
        kb_version = self._meta("knowledge_version")
        resp = RetrievalResponse(
            query=RetrievalQuery(text=query, topic=eff_topic, query_type=qtype),
            normalized_query=norm, results=[] if decision.abstain else results,
            abstain=decision.abstain, abstention_reason=decision.reason,
            confidence=decision.confidence, warnings=warnings,
            retrieval_version=cfg.RETRIEVAL_VERSION,
            index_version=self._index_version(), knowledge_base_version=kb_version,
            latency_ms=latency,
            debug={"candidate_counts": {"lexical": len(lex_hits), "semantic": len(sem_hits),
                                        "formula": len(form_hits)},
                   "fused": len(fused), "after_filters": len(candidates),
                   "effective_variants": {k: v for k, v in list(variant_map.items())[:12]},
                   "fuzzy_map": fuzzy_map, "directives": sorted(directives),
                   "unknown_terms": unknown_terms} if debug else {})
        return resp

    def _lookup_ids(self, query: str) -> list[str]:
        """Formulas con cobertura exacta (covers) + nucleos latex por substring.

        Devuelve LISTA ordenada (lookup, luego rows): jamas set, el orden es
        evidencia (determinismo entre procesos). Lo usan abstencion y union.
        """
        from .formula import normalize_latex as _nl, symbols_of as _syms
        from .normalize_query import normalize_query as _nq, query_terms as _qt
        norm = _nq(query)
        raw_syms = _syms(norm)
        found: list[str] = []
        if raw_syms & self.formulas.math_universe():
            qwords = set(_qt(norm))
            expr_of = {r["equation_id"]: r["expression"] for r in self.formulas.rows}
            for hit in self.formulas.lookup(raw_syms, qwords, limit=400):
                if self.formulas.covers(raw_syms, expr_of.get(hit["equation_id"], "")):
                    if hit["equation_id"] not in found:
                        found.append(hit["equation_id"])
        core = _nl(norm)
        if len(core) >= 2:
            for r in self.formulas.rows:
                if core and core in r["norm"] and r["equation_id"] not in found:
                    found.append(r["equation_id"])
        return found

    def _lookup_evidence(self, query: str) -> bool:
        """¿Hay evidencia exacta suficiente para suprimir abstencion?

        Subconjunto estricto de _lookup_ids: covers o nucleo largo (>=4).
        Un nucleo corto ('-34') une al pack pero no basta para no abstenerse.
        """
        from .formula import normalize_latex as _nl, symbols_of as _syms
        from .normalize_query import normalize_query as _nq, query_terms as _qt
        norm = _nq(query)
        raw_syms = _syms(norm)
        if raw_syms & self.formulas.math_universe():
            qwords = set(_qt(norm))
            expr_of = {r["equation_id"]: r["expression"] for r in self.formulas.rows}
            for hit in self.formulas.lookup(raw_syms, qwords, limit=400):
                if self.formulas.covers(raw_syms, expr_of.get(hit["equation_id"], "")):
                    return True
        return len(_nl(norm)) >= 4 and any(
            _nl(norm) in r["norm"] for r in self.formulas.rows)

    def retrieve_evidence(self, query: str, *, filters: RetrievalFilters | None = None,
                          top_k: int = cfg.DEFAULT_TOP_K) -> EvidencePack:
        resp = self.retrieve(query, filters=filters, top_k=top_k)
        expanded = self.expander.expand([r.chunk_id for r in resp.results])
        pack = assemble(query, [self._result_dict(r) for r in resp.results], expanded,
                        self.kb_path, abstain=resp.abstain,
                        abstention_reason=resp.abstention_reason,
                        confidence=resp.confidence, warnings=list(resp.warnings))
        if not resp.abstain:
            self._union_lookup_formulas(query, pack, expanded)
        return pack

    def _union_lookup_formulas(self, query: str, pack: EvidencePack,
                               expanded: dict[str, dict]) -> None:
        """Canal formula-first (§13): las formulas con cobertura exacta de los
        simbolos consultados (o nucleo latex) entran al pack con su contexto,
        aunque su chunk no este en el top-K. General: sin reglas por query."""
        have = {f["equation_id"] for f in pack.formulas}
        cover_ids = list(dict.fromkeys(list(self._lookup_ids(query))))
        # Secciones nombradas por la query: sus formulas son evidencia (§13/§25).
        from .normalize_query import query_terms as _qt2
        qw = {w for w in _qt2(query) if len(w) >= 4}
        sec_hits: list[tuple[float, str]] = []
        if len(qw) >= 2:
            for r in self.formulas.rows:
                sec_w = set(_qt2(r["section_h2"] or ""))
                shared = qw & sec_w
                if len(shared) >= 2 and len(shared) / len(qw) >= 0.5:
                    sec_hits.append((len(shared) / len(qw), r["equation_id"]))
        sec_hits.sort(key=lambda x: (-x[0], x[1]))
        sec_ids = [eid for _, eid in sec_hits[:30]]
        # Orden final: covers exactos, evidencia rankeada (ya en pack), red de
        # seccion. Los covers mandan; la red no entierra lo rankeado.
        ordered = [e for e in cover_ids if e not in have]
        ordered += [e for e in sec_ids if e not in have and e not in set(ordered)]
        extra = ordered
        if not extra:
            return
        import sqlite3 as _s
        cover_recs, sec_recs = [], []
        con = _s.connect("file:%s?mode=ro" % self.kb_path, uri=True)
        try:
            for eid in extra:
                row = con.execute(
                    "SELECT equation_id, expression, topic, source_path, section_h2"
                    " FROM formulas WHERE equation_id=?", (eid,)).fetchone()
                if not row:
                    continue
                rec = {"equation_id": row[0], "expression": row[1],
                       "topic": row[2], "source_path": row[3],
                       "section_h2": row[4], "via": "formula-lookup"}
                (cover_recs if eid in set(cover_ids) else sec_recs).append(rec)
                cids = self._formula_chunks.get(eid, [])
                if cids and cids[0] not in expanded:
                    new_ctx = self.expander.expand(cids[:1])
                    expanded.update(new_ctx)
                    for v in new_ctx.values():
                        for vv in v.get("visuals", []):
                            if vv["asset_id"] not in {x["asset_id"] for x in pack.visuals}:
                                pack.visuals.append(vv)
        finally:
            con.close()
        # Covers exactos primero, evidencia rankeada despues, red de seccion
        # al final (recall sin enterrar). Determinista.
        pack.formulas[:] = cover_recs + pack.formulas + sec_recs

    @staticmethod
    def _result_dict(r: RetrievalResult) -> dict:
        return {"chunk_id": r.chunk_id, "final_score": r.final_score,
                "source_path": r.source_path, "source_hash": r.source_hash,
                "topic": r.topic, "section": r.section, "text": r.text,
                "formula_ids": r.formula_ids, "image_refs": r.image_refs,
                "components": r.components}

    def _meta(self, key: str) -> str:
        if key == "knowledge_version":
            import hashlib as _hl
            h = _hl.sha256()
            for cid in sorted(self._chunks):
                h.update(cid.encode())
            return "kb-%s" % h.hexdigest()[:12]
        return ""

    def _index_version(self) -> str:
        try:
            import json as _j
            man = _j.loads((self.index_dir / "manifest.json").read_text(encoding="utf-8"))
            return man.get("index_version", cfg.INDEX_VERSION)
        except OSError:
            return cfg.INDEX_VERSION
