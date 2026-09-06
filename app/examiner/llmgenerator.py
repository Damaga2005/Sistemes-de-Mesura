"""Generacion via LLM (THEORY/CONCEPTUAL/OPEN/SHORT/MCQ conceptual): blueprint +
evidencia -> JSON estructurado -> parse estricto. Sin JSON valido:
INVALID_GENERATION, nunca texto libre como pregunta.
"""
from __future__ import annotations

import json
from pathlib import Path

PROMPTS = Path(__file__).resolve().parent / "prompts"


def build_generation_messages(blueprint, evidence: dict, language: str,
                              prompt_version: str = "question_generation_v1") -> list:
    from app.llm.interface import Message
    system = (PROMPTS / (prompt_version + ".txt")).read_text(encoding="utf-8")
    lines = [
        "BLUEPRINT: topic=%s section=%s type=%s difficulty=%s seed=%s" % (
            blueprint.topic, blueprint.section, blueprint.question_type,
            blueprint.difficulty, blueprint.seed),
        "OBJECTIVE: %s" % blueprint.learning_objective,
        "IDIOMA DE LA PREGUNTA: %s" % language,
    ]
    for f in evidence.get("formulas", [])[:6]:
        lines.append("FORMULA %s: %s [%s]" % (
            f["equation_id"], f["expression"], f.get("section_h2", "")))
    for c in evidence.get("chunks", [])[:6]:
        lines.append("EVIDENCIA [%s]: %s" % (c["chunk_id"], c["text"][:1200]))
    lines.append("Genera UNA pregunta %s %s." % (blueprint.question_type,
                                                 blueprint.difficulty))
    return [Message("system", system), Message("user", "\n".join(lines))]


def parse_candidate(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        import re as _re
        t = _re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = _re.sub(r"\s*```$", "", t)
    try:
        cand = json.loads(t)
    except json.JSONDecodeError:
        s, e = t.find("{"), t.rfind("}")
        if 0 <= s < e:
            try:
                cand = json.loads(t[s:e + 1])
            except json.JSONDecodeError:
                raise ValueError("INVALID_GENERATION")
        else:
            raise ValueError("INVALID_GENERATION")
    if not isinstance(cand, dict) or not cand.get("prompt"):
        raise ValueError("INVALID_GENERATION")
    return cand
