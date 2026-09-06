"""Esqueleto determinista Fase 0 (spec-as-code, sin LLM, sin IO de red).

Estas funciones puras fijan el comportamiento que la Fase 1 debe honrar.
Todo lo no determinista (embeddings, LLM) queda fuera a proposito.
"""
import hashlib
import re
from pathlib import PurePosixPath

TOPICS = set(range(1, 11))

_BOILERPLATE_SELECTORS = (
    "style", "script", "breadcrumb", "hero",
    "COM EDITAR AQUEST FITXER",
)

_KIND_BY_NAME = (
    ("index", "index"),
    ("entrenament", "entrenament"),
)


def topic_from_path(path: str) -> int:
    """El topic se deriva de la carpeta `Tema N`. Nunca del nombre de archivo."""
    parts = PurePosixPath(path.replace("\\", "/")).parts
    if not parts:
        raise ValueError("ruta vacia")
    m = re.fullmatch(r"Tema\s+(\d+)", parts[0])
    if not m:
        raise ValueError("sin carpeta Tema N: %r" % path)
    n = int(m.group(1))
    if n not in TOPICS:
        raise ValueError("tema fuera de 1..10: %r" % path)
    return n


def classify_kind(filename: str) -> str:
    """index | entrenament | teoria | pdf-apunts (por nombre, el topic va por carpeta)."""
    low = filename.lower()
    if low.endswith(".pdf"):
        return "pdf-apunts"
    for kind, needle in _KIND_BY_NAME:
        if needle in low:
            return kind
    return "teoria"


def deterministic_id(path: str) -> str:
    """sm-<tt>-<10 hex>. Estable ante re-ejecuciones y renombrados fuera de Tema/."""
    norm = path.replace("\\", "/")
    topic = topic_from_path(norm)
    h = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:10]
    return "sm-%02d-%s" % (topic, h)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_latex(html: str) -> list:
    """Fuentes LaTeX canonicas de comentarios <!-- $...$ -->. Sin normalizar: fidelidad total."""
    out = []
    for m in re.finditer(r"<!--(.*?)-->", html, flags=re.S):
        body = m.group(1).strip()
        if len(body) >= 2 and body.startswith("$") and body.endswith("$"):
            out.append(body)
    return out


def strip_boilerplate(html: str) -> str:
    """Elimina style/script y marcadores de plantilla. Conserva texto academico y LaTeX.

    Los comentarios <!-- $...$ --> son la fuente canonica de formulas: se protegen
    antes de eliminar etiquetas (un strip ingenuo los destruiria).
    """
    latex = extract_latex(html)

    def _protect(m):
        body = m.group(1).strip()
        if len(body) >= 2 and body.startswith("$") and body.endswith("$"):
            _protect.slots.append(body)
            return " \x00LATEX%d\x00 " % (len(_protect.slots) - 1)
        return " "  # comentario no-latex: descartar

    _protect.slots = []
    protected = re.sub(r"<!--(.*?)-->", _protect, html, flags=re.S)
    t = re.sub(r"<script\b.*?</script\s*>", " ", protected, flags=re.S | re.I)
    t = re.sub(r"<style\b.*?</style\s*>", " ", t, flags=re.S | re.I)
    t = re.sub(r"COM EDITAR AQUEST FITXER.*?(?=-->)", " ", t, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    for i, expr in enumerate(_protect.slots):
        t = t.replace("\x00LATEX%d\x00" % i, " " + expr + " ")
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def is_boilerplate_only(text: str) -> bool:
    """Detecta fragmentos que nunca deben indexarse (navegacion, instrucciones de edicion)."""
    low = text.lower()
    return any(s.lower() in low for s in ("breadcrumb", "com editar aquest fitxer")) or len(text.strip()) == 0
