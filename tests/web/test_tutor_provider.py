"""Fase 3: wiring del proveedor de razonamiento en el tutor (Bridge).

Sin red: auto/gemini/extractive se comprueban por construccion; el fallback
en peticion se prueba inyectando un proveedor que revienta. El camino live
(Gemini real) esta bajo @NEEDS_KEY, como en tests/reasoning/test_provider.py.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web"))

import server as S  # noqa: E402

from app.llm.extractive import ExtractiveProvider  # noqa: E402
from app.llm.gemini import GeminiProvider  # noqa: E402

KB = ROOT / "data" / "processed" / "knowledge.sqlite"
INDEX = ROOT / "data" / "index"
NEEDS_KEY = pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY"),
                               reason="sin GEMINI_API_KEY")
_Q = "què és la incertesa expandida?"


def _bridge(**kw):
    return S.Bridge(workdir=tempfile.mkdtemp(prefix="sm-tp-"), **kw)


def test_default_sin_clave_es_extractive(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("SM_PROVIDER", raising=False)
    assert isinstance(_bridge().app.reasoning.provider, ExtractiveProvider)


def test_auto_con_clave_es_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x" * 20)
    assert isinstance(_bridge(provider="auto").app.reasoning.provider, GeminiProvider)


def test_extractive_forzado_ignora_clave(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x" * 20)
    assert isinstance(_bridge(provider="extractive").app.reasoning.provider,
                      ExtractiveProvider)


def test_gemini_forzado(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x" * 20)
    assert isinstance(_bridge(provider="gemini").app.reasoning.provider, GeminiProvider)


def test_gemini_forzado_sin_clave_error_controlado(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="reasoning_unavailable"):
        _bridge(provider="gemini")


def test_env_SM_PROVIDER_respetado(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x" * 20)
    monkeypatch.setenv("SM_PROVIDER", "extractive")
    assert isinstance(_bridge().app.reasoning.provider, ExtractiveProvider)


class _Boom:
    provider_name = "boom"
    model_name = "boom-1"

    def generate(self, *a, **k):
        raise RuntimeError("reasoning_unavailable: HTTPError 503")


def test_fallback_extractivo_en_peticion(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    b = _bridge(provider="extractive")
    b.app.reasoning.provider = _Boom()
    st, data, _ = b.route("POST", "/api/tutor/ask", body={"query": _Q})
    assert st == 200
    assert data["abstain"] is False
    assert data["versions"]["provider"]["provider"] == "extractive-fallback"


def test_contrato_http_intacto(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    st, data, _ = _bridge().route("POST", "/api/tutor/ask", body={"query": _Q})
    assert st == 200
    assert {"answer", "status", "abstain", "claims", "provenance",
            "versions"} <= set(data)


def test_ci_no_depende_de_gemini_live(monkeypatch):
    """test_tutor_abstain_e2e y hermanos: sin clave, jamas se llama a Gemini."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    b = _bridge()
    assert not isinstance(b.app.reasoning.provider, GeminiProvider)
    st, data, _ = b.route("POST", "/api/tutor/ask", body={"query": "Explica aixo"})
    assert st == 200 and data["abstain"] is True


@NEEDS_KEY
def test_live_tutor_gemini_identifica_proveedor():
    b = _bridge(provider="gemini")
    assert isinstance(b.app.reasoning.provider, GeminiProvider)
    try:
        st, data, _ = b.route("POST", "/api/tutor/ask", body={"query": _Q})
    except RuntimeError as e:
        if "HTTPError 429" in str(e) or "HTTPError 50" in str(e):
            pytest.skip("proveedor no disponible")
        raise
    assert st == 200
    prov = data["versions"]["provider"]["provider"]
    assert prov in ("gemini", "extractive-fallback")
