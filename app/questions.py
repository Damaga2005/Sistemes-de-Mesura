"""Extractor del banco V/F de entrenament (solo lectura). Tres formatos JS reales:
BANC (T1,T2): [{n,d,a,q,j,dt?,df?}] · ITEMS+DOCS (T6-T10): [{n,d,a,q,j}] + DOCS{d:{f,t}}
DATA (T3,T4,T5): {blocs:[...], items:[{n,bloc,text,resp,just}]}. Todo parsea como JSON.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass
class EvalQuestion:
    qid: str
    topic: int
    question: str
    answer: str  # V | F
    justification: str
    expected_source: str | None
    origin: str


def _extract_bracket(js: str, start: int) -> str:
    """Extrae literal [...] balanceado respetando strings. Determinista."""
    depth = 0
    instr = False
    esc = False
    quote = ""
    for j in range(start, len(js)):
        c = js[j]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == quote:
                instr = False
        elif c in "\"'":
            instr, quote = True, c
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return js[start : j + 1]
    raise ValueError("array JS sin cierre")


def _scripts(html: str) -> str:
    return "\n".join(re.findall(r"<script.*?>(.*?)</script>", html, flags=re.S | re.I))


def _extract_braced_object(js: str, name: str) -> dict:
    m = re.search(r"(?:var|const)\s+" + re.escape(name) + r"\s*=\s*\{", js)
    if not m:
        return {}
    i = m.end() - 1
    depth = 0
    instr = False
    esc = False
    quote = ""
    for j in range(i, len(js)):
        c = js[j]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == quote:
                instr = False
        elif c in "\"'":
            instr, quote = True, c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return json.loads(js[i : j + 1])
    raise ValueError("objeto JS %s sin cierre" % name)


def extract_questions(html: str, topic: int, source_path: str) -> tuple[list[EvalQuestion], str]:
    """Devuelve (preguntas, formato). Falla en voz alta si el formato es desconocido."""
    js = _scripts(html)
    out: list[EvalQuestion] = []
    m = re.search(r"(?:var|const)\s+(BANC|ITEMS)\s*=\s*\[", js)
    if m:
        raw = _extract_bracket(js, m.end() - 1)
        items = json.loads(raw)
        docs = _extract_braced_object(js, "DOCS") if "DOCS" in js else {}
        for it in items:
            doc_file = it.get("df") or (docs.get(it.get("d", ""), {}).get("f"))
            src = ("Tema %d/%s" % (topic, doc_file)) if doc_file else None
            n = it.get("n")
            out.append(
                EvalQuestion(
                    qid="eval-t%02d-%03d" % (topic, n),
                    topic=topic,
                    question=it["q"],
                    answer=it["a"],
                    justification=it.get("j", ""),
                    expected_source=src,
                    origin="%s:%s" % (source_path, "BANC" if m.group(1) == "BANC" else "ITEMS"),
                )
            )
        return out, m.group(1)
    m = re.search(r'"items"\s*:\s*\[', js)
    if m:
        raw = _extract_bracket(js, js.index("[", m.start()))
        items = json.loads(raw)
        for it in items:
            out.append(
                EvalQuestion(
                    qid="eval-t%02d-%03d" % (topic, it.get("n")),
                    topic=topic,
                    question=it["text"],
                    answer=it["resp"],
                    justification=it.get("just", ""),
                    expected_source=None,
                    origin="%s:DATA[bloc=%s]" % (source_path, it.get("bloc")),
                )
            )
        return out, "DATA"
    raise ValueError("formato de entrenament desconocido en %s" % source_path)
