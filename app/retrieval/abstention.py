"""Abstencion explicita (§31-34): sin resultados, debiles, ambiguos, tema
desconocido. Distingue 'no se' de 'sin evidencia suficiente' (siempre lo segundo).
"""
from __future__ import annotations

from dataclasses import dataclass

from . import config as cfg


@dataclass
class AbstentionDecision:
    abstain: bool
    reason: str | None
    confidence: float


def decide(ranked: list[dict], *, unknown_topic: bool = False, unknown_terms: int = 0,
           phrase_top: float = 0.0, formula_top: bool = False,
           mass_top: float = 0.0, intent_routed: bool = False,
           has_words: bool = True, has_lookup: bool = False) -> AbstentionDecision:
    """has_lookup: evidencia exacta de formula (lookup/substring); suprime
    abstencion por OOV/masa, nunca por topico desconocido ni vacio total."""
    if unknown_topic:
        return AbstentionDecision(True, "unknown_topic", 0.0)
    if unknown_terms >= 2 and not has_lookup:
        return AbstentionDecision(True, "unknown_terms", 0.0)
    if not ranked:
        # Con evidencia exacta de formula el pack se llena por union aunque no
        # haya chunks rankeados; sin nada, abstencion.
        if has_lookup:
            return AbstentionDecision(False, None, 0.5)
        return AbstentionDecision(True, "no_results", 0.0)
    if unknown_terms == 1 and not formula_top and not intent_routed and not has_lookup \
            and mass_top < 0.6:
        return AbstentionDecision(True, "unknown_term", 0.0)
    if has_words and mass_top < cfg.ABSTAIN_MASS and not formula_top and not has_lookup:
        return AbstentionDecision(True, "insufficient_evidence", 0.0)
    top = ranked[0]["final"]
    if top < cfg.ABSTAIN_MIN_SCORE:
        return AbstentionDecision(True, "weak_results", round(max(top, 0.0), 4))
    if len(ranked) > 1:
        margin = top - ranked[1]["final"]
        if top < 0.25 and margin < cfg.ABSTAIN_MARGIN:
            return AbstentionDecision(True, "ambiguous_results", round(top, 4))
    return AbstentionDecision(False, None, round(min(max(top, 0.0), 1.0), 4))


def conflict_warning(ranked: list[dict]) -> str | None:
    """Top-2 empatados de temas distintos con tipos de contenido distintos."""
    if len(ranked) < 2:
        return None
    a, b = ranked[0], ranked[1]
    if (a["final"] - b["final"]) < cfg.AMBIGUITY_MARGIN and a.get("topic") != b.get("topic"):
        return "possible_conflict: %s (T%s) vs %s (T%s)" % (
            a["chunk_id"], a.get("topic"), b["chunk_id"], b.get("topic"))
    return None
