"""Re-export de la interfaz de embeddings."""
from .interface import EmbeddingProvider, TfidfEmbeddingProvider

__all__ = ["EmbeddingProvider", "TfidfEmbeddingProvider"]
