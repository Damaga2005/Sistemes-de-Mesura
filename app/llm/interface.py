"""Abstraccion del proveedor LLM (§7-8). El core nunca importa SDKs concretos."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Message:
    role: str  # system | user
    content: str


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    prompt_version: str = ""
    latency_ms: float = 0.0
    usage: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


class LLMProvider(Protocol):
    provider_name: str
    model_name: str

    def generate(self, messages: list[Message], *, temperature: float = 0.0,
                 max_tokens: int = 1500) -> LLMResponse:
        ...
