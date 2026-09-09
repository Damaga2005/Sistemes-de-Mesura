"""Tests del proveedor LLM: protocolo + fallback controlado + camino live (con coste).

Lo live se salta sin GEMINI_API_KEY. Minimo deliberado: el coste por ejecucion
debe ser despreciable (flash-lite, pocas llamadas cortas).
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.llm.extractive import ExtractiveProvider  # noqa: E402
from app.llm.gemini import GeminiProvider, select_provider  # noqa: E402
from app.llm.interface import Message  # noqa: E402
from app.reasoning.engine import ReasoningEngine  # noqa: E402
from app.retrieval.service import RetrievalService  # noqa: E402

KB = ROOT / "data" / "processed" / "knowledge.sqlite"
INDEX = ROOT / "data" / "index"
NEEDS_KEY = pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY"),
                               reason="sin GEMINI_API_KEY")


def _live_or_skip(fn, *args, **kwargs):
    """La API puede estar transitoriamente no disponible (5xx/429 tras
    reintentos): skip honesto, no fallo. Los errores de formato/contenido
    (fallos reales) si fallan."""
    try:
        return fn(*args, **kwargs)
    except RuntimeError as e:
        msg = str(e)
        if "HTTPError 429" in msg or "HTTPError 50" in msg or "transitorio" in msg:
            pytest.skip("proveedor no disponible: %s" % msg[:120])
        raise


def test_select_provider_fallback_sin_clave(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    p = select_provider("auto")
    assert p.provider_name == "extractive-fallback"


def test_select_provider_gemini_exige_clave(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="reasoning_unavailable"):
        select_provider("gemini")


def test_gemini_requiere_clave(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="reasoning_unavailable"):
        GeminiProvider(api_key="")


def test_extractive_no_finge_generate():
    with pytest.raises(RuntimeError):
        ExtractiveProvider().generate([Message("user", "hola")])


def test_prompt_versionado_existe():
    p = ROOT / "app" / "llm" / "prompts" / "reasoning_v1.txt"
    txt = p.read_text(encoding="utf-8")
    assert "única font" in txt or "única fuente" in txt or "font de veritat" in txt
    assert "JSON" in txt


# ---- Fase 0: fallback ante fallo del proveedor LLM en _reason() ----

class _FakeLLM:
    provider_name = "fake-llm"
    model_name = "fake-1"

    def __init__(self, text: str) -> None:
        self._text = text

    def generate(self, messages, *, temperature=0.0, max_tokens=1500):
        from app.llm.interface import LLMResponse
        return LLMResponse(text=self._text, provider=self.provider_name,
                           model=self.model_name)


class _BoomLLM:
    provider_name = "boom"
    model_name = "boom-1"

    def generate(self, *a, **k):
        raise RuntimeError("reasoning_unavailable: HTTPError 503: transitorio")


class _BugLLM:
    provider_name = "bug"
    model_name = "bug-1"

    def generate(self, *a, **k):
        raise TypeError("bug real en el codigo, no fallo de proveedor")


_Q = "què és la incertesa expandida?"


def test_gemini_success_provider_is_used():
    svc = RetrievalService(str(KB), str(INDEX))
    pack = svc.retrieve_evidence(_Q, top_k=10)
    good = ExtractiveProvider().answer_from_pack(_Q, pack).text
    eng = ReasoningEngine(svc, str(KB), provider=_FakeLLM(good))
    ans = eng.answer(_Q)
    assert not ans.abstain
    assert ans.versions["provider"]["provider"] == "fake-llm"


def test_gemini_runtime_error_falls_back_to_extractive():
    svc = RetrievalService(str(KB), str(INDEX))
    eng = ReasoningEngine(svc, str(KB), provider=_BoomLLM())
    ans = eng.answer(_Q)
    assert not ans.abstain
    prov = ans.versions["provider"]
    assert prov["provider"] == "extractive-fallback"
    assert "503" in prov["fallback_reason"]


def test_provider_error_no_credential_leak(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "SECRET-should-never-appear")
    svc = RetrievalService(str(KB), str(INDEX))
    eng = ReasoningEngine(svc, str(KB), provider=_BoomLLM())
    ans = eng.answer(_Q)
    import json as _json
    assert "SECRET-should-never-appear" not in _json.dumps(ans.to_dict())


def test_programming_error_not_swallowed():
    svc = RetrievalService(str(KB), str(INDEX))
    eng = ReasoningEngine(svc, str(KB), provider=_BugLLM())
    with pytest.raises(TypeError):
        eng.answer(_Q)


def test_extractive_direct_unchanged():
    svc = RetrievalService(str(KB), str(INDEX))
    eng = ReasoningEngine(svc, str(KB), provider=ExtractiveProvider())
    ans = eng.answer(_Q)
    assert not ans.abstain
    assert ans.versions["provider"]["provider"] == "extractive-fallback"


@NEEDS_KEY
def test_live_theory_answer_verified():
    svc = RetrievalService(str(KB), str(INDEX))
    eng = ReasoningEngine(svc, str(KB), provider=GeminiProvider())
    ans = _live_or_skip(eng.answer, "què és la incertesa expandida?")
    assert not ans.abstain
    assert ans.verification_status in ("VERIFIED", "SUPPORTED", "PARTIAL")
    assert ans.provenance


@NEEDS_KEY
def test_live_abstention_out_of_scope():
    svc = RetrievalService(str(KB), str(INDEX))
    eng = ReasoningEngine(svc, str(KB), provider=GeminiProvider())
    ans = _live_or_skip(eng.answer, "Qui va guanyar la Champions el 2026?")
    assert ans.abstain


@NEEDS_KEY
def test_live_calculation_verified():
    svc = RetrievalService(str(KB), str(INDEX))
    eng = ReasoningEngine(svc, str(KB), provider=GeminiProvider())
    ans = _live_or_skip(eng.answer, "Calcula U amb k=2 i u_c=0.5")
    assert not ans.abstain
    assert any(c.match for c in ans.calculations) or ans.verification_status in (
        "VERIFIED", "SUPPORTED", "PARTIAL")
