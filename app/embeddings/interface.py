"""Proveedor de embeddings: protocolo abstracto + implementacion TF-IDF local.

Mouse Spark es un LLM, no un modelo de embeddings (§18): el proveedor es
independiente y sustituible. Sin red, sin pesos externos, reproducible.
"""
from __future__ import annotations

from typing import Protocol


class EmbeddingProvider(Protocol):
    model_name: str
    dimension: int

    def embed(self, texts: list[str]) -> list[dict[str, float]]:
        """Devuelve vectores dispersos {término: peso} (o densos en el futuro)."""
        ...


class TfidfEmbeddingProvider:
    """Adaptador sobre el índice TF-IDF de app.retrieval.semantic."""

    model_name = "tfidf-local-1.0"
    dimension = -1  # vocabulario abierto, disperso

    def __init__(self, index) -> None:  # index: TfidfIndex
        self._index = index
        self.dimension = len(index.vocab)

    def embed(self, texts: list[str]) -> list[dict[str, float]]:
        return [self._index.vectorize(t) for t in texts]
