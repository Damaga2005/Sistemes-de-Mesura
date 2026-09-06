"""Extraccion estructural de HTML (stdlib únicamente). Solo lectura.

Captura la jerarquía Tema -> Documento (h1) -> Sección (h2) -> bloques tipados,
preservando comentarios LaTeX <!-- $...$ --> con su posición y las imágenes
base64 con su caption. Excluye style/script/hero/breadcrumb/instrucciones Tema 1.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

LATEX_COMMENT_RE = re.compile(r"<!--(.*?)-->", re.S)

# div class -> content_type del bloque (taxonomía emergente del propio material, Fase 0 §10).
BOX_TYPE_MAP = {
    "objectius": "summary",
    "resum": "summary",
    "nota": "warning",
    "atencio": "warning",
    "clau": "definition",
    "dada": "explanation",
    "llegir": "reference",
    "exemple": "example",
    "example": "example",
}


@dataclass
class Block:
    kind: str  # paragraph | box | table | figure | list | code | heading3
    box_type: str | None = None
    text: str = ""
    html_inner: str = ""
    latex: list[str] = field(default_factory=list)
    images: list[dict] = field(default_factory=list)  # {src_kind, bytes_len, sha256, alt}
    caption: str | None = None
    table: dict | None = None  # {headers, rows}


@dataclass
class Section:
    h2: str
    index: int
    blocks: list[Block] = field(default_factory=list)
    latex: list[str] = field(default_factory=list)  # fórmulas sueltas a nivel de sección


@dataclass
class HtmlDocument:
    title: str
    h1: str
    sections: list[Section] = field(default_factory=list)
    preamble_latex: list[str] = field(default_factory=list)


def _clean_text(raw: str) -> str:
    t = re.sub(r"\s+", " ", raw)
    return t.strip()


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self._in_title = False
        self._in_h1 = False
        self._h1_done = False
        self.sections: list[Section] = []
        self._cur_h2: list[str] | None = None
        self._cur_block: Block | None = None
        self._block_text: list[str] = []
        self._block_html: list[str] = []
        self._block_latex: list[str] = []
        self._block_images: list[dict] = []
        self._in_table = False
        self._table_headers: list[str] = []
        self._table_rows: list[list[str]] = []
        self._cur_row: list[str] | None = None
        self._cur_cell: list[str] | None = None
        self._cell_is_header = False
        self._in_caption = False
        self._caption_parts: list[str] = []
        self._skip_depth = 0  # style/script/hero
        self._svg_meta_depth = 0  # metadata/defs de SVG: texto RDF, nunca contenido
        self._in_h3 = False
        self._h3_parts: list[str] = []

    # ---------- helpers ----------
    def _ensure_section(self) -> Section:
        if not self.sections:
            self.sections.append(Section(h2="", index=0))
        return self.sections[-1]

    def _flush_block(self) -> None:
        if self._cur_block is None:
            return
        b = self._cur_block
        b.text = _clean_text("".join(self._block_text))
        b.html_inner = "".join(self._block_html)[:20000]
        b.latex = list(self._block_latex)
        b.images = list(self._block_images)
        if self._caption_parts:
            b.caption = _clean_text("".join(self._caption_parts))
            self._caption_parts = []
        if b.kind == "table":
            b.table = {"headers": self._table_headers, "rows": self._table_rows}
        # Los bloques vacíos sin texto ni latex ni imágenes ni tabla se descartan
        # (navegación, separadores), salvo tablas.
        if b.kind != "table" and not b.text and not b.latex and not b.images:
            pass
        else:
            self._ensure_section().blocks.append(b)
        self._cur_block = None
        self._block_text = []
        self._block_html = []
        self._block_latex = []
        self._block_images = []
        self._table_headers = []
        self._table_rows = []

    # ---------- HTMLParser ----------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        cls = (a.get("class") or "")
        if tag in ("style", "script"):
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in ("header", "nav", "footer") or "breadcrumb" in cls or "hero" in cls:
            self._skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
            return
        if tag == "h1" and not self._h1_done:
            self._in_h1 = True
            return
        if tag == "h2":
            self._flush_block()
            self._cur_h2 = []
            return
        if tag == "h3":
            self._flush_block()
            self._in_h3 = True
            self._h3_parts = []
            return
        if tag == "p" or tag == "li" and self._cur_block is None:
            if self._cur_block is None:
                self._cur_block = Block(kind="paragraph" if tag == "p" else "list")
            return
        if tag in ("ul", "ol"):
            self._flush_block()
            self._cur_block = Block(kind="list")
            return
        if tag == "div" and "box" in cls.split():
            self._flush_block()
            btype = next((c for c in cls.split() if c != "box"), "box")
            self._cur_block = Block(kind="box", box_type=btype)
            return
        if tag == "table":
            self._flush_block()
            self._cur_block = Block(kind="table")
            self._in_table = True
            return
        if tag == "tr" and self._in_table:
            self._cur_row = []
            return
        if tag in ("td", "th") and self._in_table:
            self._cur_cell = []
            self._cell_is_header = tag == "th"
            return
        if tag == "figure":
            self._flush_block()
            self._cur_block = Block(kind="figure")
            return
        if tag == "figcaption":
            self._in_caption = True
            self._caption_parts = []
            return
        if tag in ("metadata", "defs"):
            self._svg_meta_depth += 1
            return
        if tag == "pre":
            self._flush_block()
            self._cur_block = Block(kind="code")
            return
        if tag == "img":
            src = a.get("src") or ""
            alt = (a.get("alt") or "").strip()[:500]
            fig_key = (a.get("data-fig") or "").strip() or None
            if src.startswith("data:image"):
                import base64
                import hashlib

                b64 = src.split(",", 1)[1] if "," in src else ""
                try:
                    raw = base64.b64decode(b64, validate=False)
                    digest = hashlib.sha256(raw).hexdigest()
                except Exception:
                    raw, digest = b"", "INVALID"
                info = {"src_kind": "base64", "bytes_len": len(raw), "sha256": digest,
                        "alt": alt, "fig_key": fig_key}
            elif fig_key:
                info = {"src_kind": "data-fig-ref", "bytes_len": 0, "sha256": "",
                        "alt": alt, "fig_key": fig_key}
            else:
                info = {"src_kind": "external", "bytes_len": 0, "sha256": "",
                        "alt": alt, "fig_key": None}
            if self._cur_block is None:
                self._cur_block = Block(kind="figure")
            self._block_images.append(info)
            return
        if tag == "sub" or tag == "sup":
            self._block_text.append("<%s>" % tag)
            self._block_html.append("<%s>" % tag)
            return

    def handle_endtag(self, tag: str) -> None:
        if tag in ("style", "script", "header", "nav", "footer"):
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag == "title":
            self._in_title = False
            return
        if tag == "h1" and self._in_h1:
            self._in_h1 = False
            self._h1_done = True
            return
        if tag == "h2" and self._cur_h2 is not None:
            sec = Section(h2=_clean_text("".join(self._cur_h2)), index=len(self.sections))
            self.sections.append(sec)
            self._cur_h2 = None
            return
        if tag == "h3" and self._in_h3:
            self._in_h3 = False
            txt = _clean_text("".join(self._h3_parts))
            if txt:
                sec = self._ensure_section()
                sec.blocks.append(Block(kind="heading3", text=txt))
            return
        if tag in ("p", "ul", "ol", "div", "figure", "pre", "table"):
            if tag == "table":
                self._in_table = False
            self._flush_block()
            return
        if tag == "tr" and self._in_table and self._cur_row is not None:
            if any(c.strip() for c in self._cur_row):
                self._table_rows.append([_clean_text(c) for c in self._cur_row])
            self._cur_row = None
            return
        if tag in ("td", "th") and self._in_table and self._cur_cell is not None:
            cell = _clean_text("".join(self._cur_cell))
            if self._cell_is_header:
                self._table_headers.append(cell)
            if self._cur_row is not None:
                self._cur_row.append(cell)
            self._cur_cell = None
            return
        if tag == "figcaption":
            self._in_caption = False
            return
        if tag in ("metadata", "defs"):
            if self._svg_meta_depth:
                self._svg_meta_depth -= 1
            return
        if tag in ("sub", "sup"):
            self._block_text.append("</%s>" % tag)
            self._block_html.append("</%s>" % tag)
            return
        if tag == "li" and self._cur_block is not None and self._cur_block.kind in ("paragraph", "list"):
            self._block_text.append(" | ")

    def handle_data(self, data: str) -> None:
        if self._skip_depth or self._svg_meta_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
            return
        if self._in_h1:
            self.h1_parts.append(data)
            return
        if self._cur_h2 is not None:
            self._cur_h2.append(data)
            return
        if self._in_h3:
            self._h3_parts.append(data)
            return
        if self._in_caption:
            self._caption_parts.append(data)
            return
        if self._cur_cell is not None:
            self._cur_cell.append(data)
            return
        if self._cur_block is not None:
            self._block_text.append(data)
            if len(self._block_html) < 400:
                self._block_html.append(data)

    def handle_comment(self, data: str) -> None:
        if self._skip_depth:
            return
        body = data.strip()
        if len(body) >= 2 and body.startswith("$") and body.endswith("$"):
            if self._cur_block is not None:
                self._block_latex.append(body)
            else:
                sec = self._ensure_section()
                sec.latex.append(body)


def parse_html(html: str) -> HtmlDocument:
    """Parsea un documento HTML de teoría/index/entrenament. Determinista."""
    p = _Parser()
    p.feed(html)
    p._flush_block()
    doc = HtmlDocument(
        title=_clean_text("".join(p.title_parts)),
        h1=_clean_text("".join(p.h1_parts)),
        sections=p.sections,
    )
    return doc
