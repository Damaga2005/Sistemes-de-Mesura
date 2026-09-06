"""Normalizacion determinista: Unicode NFC, espacios, tablas. LaTeX intocable."""
from __future__ import annotations

import re
import unicodedata

_WS_RE = re.compile(r"\s+")
_SENT_END_RE = re.compile(r"(.+?[.!?……][»\"”'’\)\]]?\s|.{1,1500}$)", re.S)


def normalize_text(text: str) -> str:
    """NFC + colapso de espacios. No toca contenido LaTeX (se procesa aparte)."""
    t = unicodedata.normalize("NFC", text)
    t = t.replace("\xa0", " ")
    t = _WS_RE.sub(" ", t)
    return t.strip()


def split_sentences(text: str) -> list[str]:
    """Segmentacion ingenua por fin de frase para cortes de chunk. Determinista."""
    parts = re.split(r"(?<=[.!?…])\s+(?=[A-ZÀ-Þ0-9«\"'‘(“])", text)
    return [p.strip() for p in parts if p.strip()]


def table_to_markdown(headers: list[str], rows: list[list[str]]) -> str:
    lines = []
    if headers:
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for r in rows:
        if headers and len(r) < len(headers):
            r = r + [""] * (len(headers) - len(r))
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def table_to_records(headers: list[str], rows: list[list[str]]) -> list[dict]:
    if not headers:
        return [{"col_%d" % i: c for i, c in enumerate(r)} for r in rows]
    return [{h or ("col_%d" % i): (r[i] if i < len(r) else "") for i, h in enumerate(headers)} for r in rows]
