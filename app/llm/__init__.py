"""Re-export de la interfaz LLM."""
from .interface import LLMProvider, LLMResponse, Message

__all__ = ["LLMProvider", "LLMResponse", "Message"]
