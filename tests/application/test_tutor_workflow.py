"""Tests TutorWorkflow (B4.1/B4.6): delegación F3, sin alucinación."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from app.application.errors import AppError  # noqa: E402
from app.application.tutor import TutorWorkflow  # noqa: E402
from harness import build_app, ctx  # noqa


def wf(tmp_path):
    app = build_app(tmp_path)
    return app, TutorWorkflow(app)


def test_01_supported(tmp_path):
    app, w = wf(tmp_path)
    r = w.ask(ctx(app), "què és la incertesa expandida?")
    assert r["ok"] and r["data"]["answer"]
    assert r["data"]["abstain"] is False
    assert r["data"]["claims"]


def test_02_status_verified_or_supported(tmp_path):
    app, w = wf(tmp_path)
    r = w.ask(ctx(app), "què és la incertesa expandida?")
    assert r["data"]["status"] in ("VERIFIED", "SUPPORTED", "PARTIAL")


def test_03_unsupported_abstains(tmp_path):
    app, w = wf(tmp_path)
    r = w.ask(ctx(app), "qui va guanyar la Champions League 2024?")
    assert r["data"]["abstain"] is True


def test_04_contradiction_no_hallucination(tmp_path):
    app, w = wf(tmp_path)
    r = w.ask(ctx(app), "Per què la incertesa típica és sempre més gran que l'expandida?")
    d = r["data"]
    assert d["answer"] or d["abstain"]
    for c in d["claims"]:
        assert c["status"] in ("SUPPORTED", "PARTIALLY_SUPPORTED",
                               "UNSUPPORTED", "CONTRADICTED")


def test_05_empty_query(tmp_path):
    app, w = wf(tmp_path)
    with pytest.raises(AppError) as e:
        w.ask(ctx(app), "   ")
    assert e.value.code == "USER_ERROR"


def test_06_malformed_query(tmp_path):
    app, w = wf(tmp_path)
    with pytest.raises(AppError) as e:
        w.ask(ctx(app), 123)
    assert e.value.code == "USER_ERROR"


def test_07_provider_failure(tmp_path):
    app = build_app(tmp_path, reasoning_provider="broken")
    w = TutorWorkflow(app)
    try:
        r = w.ask(ctx(app), "què és la incertesa expandida?")
    except AppError as e:
        assert e.code in ("GENERATION_ERROR", "RETRIEVAL_ERROR",
                          "INTERNAL_ERROR")
    except RuntimeError:
        pass
    else:
        # degradación a extractivo declarada, nunca fallo silencioso
        assert r["ok"]


def test_08_catalan(tmp_path):
    app, w = wf(tmp_path)
    r = w.ask(ctx(app, language="ca"), "què és la incertesa típica?")
    assert r["ok"] and r["data"]["language"] == "ca"


def test_09_spanish(tmp_path):
    app, w = wf(tmp_path)
    r = w.ask(ctx(app, language="es"), "qué es la incertidumbre típica?")
    assert r["ok"] and r["data"]["answer"]


def test_10_provenance_intact(tmp_path):
    app, w = wf(tmp_path)
    r = w.ask(ctx(app), "què és la incertesa expandida?")
    d = r["data"]
    assert d["provenance"] and d["versions"]
    assert d["formulas"] == [] or all(
        "equation_id" in f for f in d["formulas"])


def test_11_no_secrets_no_scores(tmp_path):
    app, w = wf(tmp_path)
    blob = str(w.ask(ctx(app), "què és la incertesa expandida?"))
    for bad in ("sk-", "api_key", "chain", "system_prompt", "temperature",
                "candidate_score", "final_score"):
        assert bad not in blob


def test_12_direct_equivalence(tmp_path):
    app, w = wf(tmp_path)
    c = ctx(app)
    via_app = w.ask(c, "què és la incertesa expandida?")["data"]
    direct = app.reasoning.answer("què és la incertesa expandida?").to_dict()
    assert via_app["answer"] == direct["answer"]
    assert via_app["abstain"] == direct["abstain"]
    assert [x["status"] for x in via_app["claims"]] == [
        x["status"] for x in direct["claims"]]
