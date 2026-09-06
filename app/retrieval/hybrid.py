"""Fusion hibrida por Reciprocal Rank Fusion + union de evidencias.

Justificacion (§22, benchmark dev): RRF no exige calibrar escalas dispares
(BM25 negativo vs coseno [0,1] vs simbolo [0,1]); el ranking fino con pesos
explicitos ocurre despues, en ranking.py. Sin pesos magicos 0.5/0.5.
"""
from __future__ import annotations

from . import config as cfg


def rrf_fuse(rankings: list[list[str]], k: int = cfg.RRF_K) -> dict[str, float]:
    """rankings: listas ordenadas de chunk_ids (una por rama). Devuelve id->score."""
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, cid in enumerate(ranking, start=1):
            fused[cid] = fused.get(cid, 0.0) + 1.0 / (k + rank)
    return fused
