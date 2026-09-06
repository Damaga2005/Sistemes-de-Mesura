"""Proveedor Gemini via REST (stdlib, sin SDK). Clave solo desde entorno.

Variables: GEMINI_API_KEY (requerida), GEMINI_MODEL (defecto gemini-3.5-flash-lite).
Sin clave -> el factory devuelve ExtractiveProvider (fallo controlado §76).
La clave nunca se registra en logs (§78). Reintentos con backoff ante 429.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from .interface import LLMResponse, Message

DEFAULT_MODEL = "gemini-3.5-flash-lite"
GENERATION_URL = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"


class GeminiProvider:
    provider_name = "gemini"

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL) -> None:
        key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY", "")
        if not key:
            raise RuntimeError("reasoning_unavailable: falta GEMINI_API_KEY")
        self._key = key
        self.model_name = model

    def generate(self, messages: list[Message], *, temperature: float = 0.0,
                 max_tokens: int = 1500) -> LLMResponse:
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        user_parts = [m.content for m in messages if m.role == "user"]
        body: dict = {
            "system_instruction": {"parts": [{"text": system}]} if system else None,
            "contents": [{"role": "user", "parts": [{"text": t}]} for t in user_parts],
            "generationConfig": {"temperature": temperature,
                                 "maxOutputTokens": max_tokens,
                                 "responseMimeType": "application/json"},
        }
        body = {k: v for k, v in body.items() if v is not None}
        req = urllib.request.Request(
            GENERATION_URL % self.model_name + "?key=" + self._key,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        t0 = time.perf_counter()
        payload = None
        last_error = "respuesta vacia del proveedor"
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    payload = json.loads(r.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(2.0 * (attempt + 1))
                    last_error = "transitorio %s (reintentado)" % e.code
                    continue
                raise RuntimeError("reasoning_unavailable: HTTPError %s: %s" % (
                    e.code, str(e)[:150]))
            except Exception as e:
                raise RuntimeError("reasoning_unavailable: %s: %s" % (
                    type(e).__name__, str(e)[:200]))
        if payload is None:
            raise RuntimeError("reasoning_unavailable: %s" % last_error)
        ms = round((time.perf_counter() - t0) * 1000, 1)
        try:
            parts = payload["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError, TypeError):
            raise RuntimeError("reasoning_unavailable: respuesta vacia del proveedor")
        usage = payload.get("usageMetadata", {})
        return LLMResponse(text=text, provider=self.provider_name, model=self.model_name,
                           latency_ms=ms,
                           usage={"input": usage.get("promptTokenCount", 0),
                                  "output": usage.get("candidatesTokenCount", 0)})


def select_provider(prefer: str = "auto"):
    """auto: Gemini si hay clave, si no Extractive (controlado, sin fingir)."""
    from .extractive import ExtractiveProvider
    if prefer in ("auto", "gemini") and os.environ.get("GEMINI_API_KEY"):
        try:
            return GeminiProvider()
        except RuntimeError:
            if prefer == "gemini":
                raise
    if prefer == "gemini":
        raise RuntimeError("reasoning_unavailable: falta GEMINI_API_KEY")
    return ExtractiveProvider()
