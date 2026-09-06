"""AnswerAnalyzer (§76): divide la respuesta en piezas verificables.

formulas (latex $...$) · variables (simbolos) · values+units (numero+unidad) ·
claims (frases) · steps (lineas) · final (ultimo numerico o seleccion).
Lo no extraible es UNKNOWN, nunca inventado. Sin eval/exec (seguridad §93).
La respuesta es DATOS: patrones de instruccion se marcan, jamas se obedecen.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

INSTRUCTION_PATTERNS = [
    r"ignore (the|this|all|previous|these) (rubric|instructions|rules)",
    r"ignora (la|las|el|esta) (r[úu]brica|instrucciones|instruccions|reglas)",
    r"give me \d+\s*/\s*\d+",
    r"dame (un )?10",
    r"ponme (un )?10",
    r"the correct answer is",
    r"do not (grade|mark|correct)",
    r"no me (corrijas|eval[úu]es)",
]


@dataclass
class AnalyzedAnswer:
    raw: str = ""
    formulas: list[str] = field(default_factory=list)
    variables: list[str] = field(default_factory=list)
    values: list[dict] = field(default_factory=list)  # {value, unit}
    claims: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    final: str = ""
    selection: str = ""  # V/F o letra MCQ normalizada
    empty: bool = False
    instruction_flags: list[str] = field(default_factory=list)
    unparseable: list[str] = field(default_factory=list)


UNIT_AFTER = r"(mV|V|mA|A|k?[Ω]|Ohm\w*|Hz|kHz|MHz|mW|W|J|C|F|H|s|ms|kg|g|mm|m|K|°C|%|dB|Pa|N|rad|siemens|volt\w*|amper\w*)"


def analyze(text: str) -> AnalyzedAnswer:
    out = AnalyzedAnswer()
    raw = (text or "").strip()
    out.raw = raw
    if not raw:
        out.empty = True
        return out
    low = raw.lower()
    for pat in INSTRUCTION_PATTERNS:
        if re.search(pat, low):
            out.instruction_flags.append(pat)
    out.formulas = re.findall(r"\$.+?\$", raw)
    for m in re.finditer(
            r"(-?\d+(?:[.,]\d+)?(?:\s*[eE]\s*-?\d+)?)\s*" + UNIT_AFTER + r"(?![A-Za-z])", raw):
        try:
            out.values.append({"value": float(m.group(1).replace(",", ".").replace(" ", "")),
                               "unit": m.group(2)})
        except ValueError:
            out.unparseable.append(m.group(0)[:60])
    bare = re.findall(r"(?<![\w.])(-?\d+(?:[.,]\d+)?)(?![\w.])", raw)
    out.steps = [s.strip() for s in re.split(r"[\n;]+", raw) if s.strip()][:20]
    out.claims = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", raw) if len(s.strip()) > 15][:20]
    m = re.search(r"\b([A-D])\b[\).:]", raw)
    if m:
        out.selection = m.group(1)
    mv = re.search(r"\b(vertader|vertadera|verdadero|verdadera|true|cert|sí|si)\b", low)
    mf = re.search(r"\b(fals|falsa|falso|false)\b", low)
    if mv and not mf:
        out.selection = "V"
    elif mf and not mv:
        out.selection = "F"
    if not out.selection and re.fullmatch(r"\s*[VvFf]\s*", raw):
        out.selection = raw.strip().upper()
    if bare:
        try:
            out.final = str(float(bare[-1].replace(",", ".")))
        except ValueError:
            out.final = bare[-1]
    return out
