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
