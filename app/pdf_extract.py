"""Extraccion de PDFs (solo lectura). PyMuPDF preferido, pypdf como fallback.

Sin OCR: el material es texto nativo (Fase 0 §4). Si un PDF no diera texto,
se registra NEEDS_REVIEW en lugar de inventar contenido.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PdfImage:
    xref_or_index: str
    sha256: str
    bytes_len: int
    page: int


@dataclass
class PdfPage:
    number: int  # 1-based
    text: str
    images: list[PdfImage] = field(default_factory=list)


@dataclass
class PdfDocument:
    title: str | None
    pages: list[PdfPage] = field(default_factory=list)
    backend: str = ""
    needs_review: str | None = None


def extract_pdf(path: str | Path) -> PdfDocument:
    """Extrae texto por pagina + hash de imagenes. Nunca modifica el original."""
    try:
        import fitz  # PyMuPDF

        return _extract_pymupdf(path)
    except ImportError:
        return _extract_pypdf(path)


def _extract_pymupdf(path: str | Path) -> PdfDocument:
    import hashlib

    import fitz

    doc = fitz.open(path)
    pages: list[PdfPage] = []
    try:
        for i, page in enumerate(doc):
            text = page.get_text("text") or ""
            images: list[PdfImage] = []
            for img in page.get_images(full=True):
                xref = img[0]
                try:
                    pix = doc.extract_image(xref)
                    raw = pix["image"]
                    digest = hashlib.sha256(raw).hexdigest()
                    images.append(PdfImage(str(xref), digest, len(raw), i + 1))
                except Exception:
                    images.append(PdfImage(str(xref), "UNREADABLE", 0, i + 1))
            pages.append(PdfPage(i + 1, text, images))
        title = (doc.metadata or {}).get("title") or None
    finally:
        doc.close()
    needs = None
    if not any(p.text.strip() for p in pages):
        needs = "PDF sin texto extraible (posible escaneo); requiere OCR manual, no aplicado"
    return PdfDocument(title=title, pages=pages, backend="pymupdf", needs_review=needs)


def _extract_pypdf(path: str | Path) -> PdfDocument:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [PdfPage(i + 1, (pg.extract_text() or "")) for i, pg in enumerate(reader.pages)]
    md = reader.metadata
    title = str(md.title) if md and md.title else None
    needs = "Backend pypdf: imagenes no inventariadas (instalar PyMuPDF para visual completo)"
    if not any(p.text.strip() for p in pages):
        needs = (needs or "") + "; sin texto extraible"
    return PdfDocument(title=title, pages=pages, backend="pypdf", needs_review=needs)
