"""Normalizacion conservadora de consultas (ca/es). Preserva simbolos, unidades,
numeros, variables y expresiones matematicas. Stopwords minimas y solo de
palabras funcionales inequívocas; jamas filtra un token tecnico de 1-2 letras.
"""
from __future__ import annotations

import re
import unicodedata

_WS = re.compile(r"\s+")

# Funcionales inequívocas ca/es. Nada técnico, nada de 1 letra, nada numérico.
STOPWORDS = frozenset(
    "el la els les un una unos unas uno una del al de en y e o u con sin por para como cómo "
    "que qué cual cuál cuales cuáles cuando donde dondequiera este esta estos estas ese esa esos esas "
    "aquest aquesta aquests aquestes això allò aquel aquella aquello ello esto estos muy más mes molt "
    "tot tota tots totes todo toda todos todas también també pero però porque perquè pues doncs "
    "si no ni tan tanto tant hay ha han ser es son són és está estan estoy hay que cal fer fa fan "
    "se es su sus meu meu teva teu vostra le les li los las me mi mis tu tus nos notros vosotros "
    "jo jo soc ets jo mateix mateixa sobre entre hasta fins desde des de hacia cap als cap "
    "durante durant mentre mientras cuanto quanta cuanta antes abans después després cualsevol "
    "quisiera voldria puedes pots puede pot quiero vull necesito necessito dime digues explica "
    "explica'm dime por favor si us plau gracias gràcies hola bon dia "
    "a i com d l".split()
)

# Unidades y símbolos que JAMÁS se filtran (aunque sean cortos).
PROTECTED = frozenset(
    "u uc ux r s c v g k t f n p q x y z w m b e h j o "
    "σ μ Ω ω α β γ δ ε λ π ρ τ φ χ ψ Δ Σ θ "
    "hz khz mhz v a mv ma ω ohm ohmio hercio hertz db dbm % º °".split()
    + ["V", "A", "R", "S", "C", "U", "K", "T", "F", "N", "P", "Q", "X", "Y", "Z",
       "Hz", "kHz", "MHz", "mV", "mA", "dB", "dBm", "Ω", "μ", "σ", "RMS", "rms"]
)


def normalize_query(text: str) -> str:
    t = unicodedata.normalize("NFC", text)
    t = t.replace("\xa0", " ")
    # Elisions catalanes: l'amplificador -> amplificador (la proclitica no es
    # termino ni variable). General, no por query.
    t = re.sub(r"\b([dlsmcn])['’]([aeiouàèéíòóúh])", r"\2", t, flags=re.I)
    # Numeros de seccion pegados ("3Angle", "2La"): se separan. Solo a inicio
    # de token para no romper decimales ("3.5") ni simbolos ("I2C" interior... ).
    # General: los h2 de la KB traen esta numeracion pegada (Fase 1).
    t = re.sub(r"(?<!\S)(\d+)([A-Za-zÀ-ÿ])", r"\1 \2", t)
    t = _WS.sub(" ", t).strip()
    return t


def query_terms(text: str, *, remove_stopwords: bool = True) -> list[str]:
    """Tokens en minúsculas para matching; los protegidos siempre se conservan.

    La clase incluye ·’ (geminadas/morfologia catalana) igual que el indice
    TF-IDF: 'oscil·ladors' es un token a ambos lados; el plural lo resuelven
    los stems, no el split.
    """
    toks = re.findall(r"[A-Za-zÀ-ÿā-ʯ0-9_μΩσ\%°º+\-·'’]+", normalize_query(text).lower())
    out = []
    for tok in toks:
        if tok in PROTECTED:
            out.append(tok)
        elif remove_stopwords and tok in STOPWORDS:
            continue
        else:
            out.append(tok)
    return out


def extract_topic_mention(text: str) -> tuple[int | None, bool]:
    """Devuelve (tema mencionado, fuera_de_rango). 'Tema 20' -> (20, True)."""
    m = re.search(r"\btema\s*(\d{1,2})\b", text.lower())
    if not m:
        return None, False
    n = int(m.group(1))
    return n, not (1 <= n <= 10)


def directive_spans(text: str) -> list[str]:
    """Tokens directivos (tema/unitat/capitol + su numero): filtran, no puntuan.

    'Tema 2' ordena restringir a T2; la palabra 'tema' no es evidencia de
    contenido y su numero no es una magnitud. Los numeros SUELTOS ('2026',
    'k=2') si cuentan como contenido.
    """
    low = text.lower()
    toks: list[str] = []
    for m in re.finditer(r"\b(tema|unitat|cap[íi]tol)\s*(\d{1,2})\b", low):
        toks += [m.group(1), m.group(2)]
    return toks


MATH_CHARS = frozenset("=+-*/^_∫∑√∂≈≤≥±·×÷()[]{}")


def has_math(text: str) -> bool:
    return any(c in MATH_CHARS for c in text) or bool(re.search(r"[a-zA-Z]_[a-zA-Z0-9{]", text))
