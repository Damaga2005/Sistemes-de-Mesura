"""Tests de asistencia LLM en correccion: plumbing determinista con stub +
camino live marcado (coste minimo). El stub NO afirma que el LLM funciona;
prueba que las sugerencias se validan y jamas deciden nota.
"""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.correction.service import CorrectionService  # noqa: E402
from app.llm.interface import LLMResponse, Message  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
GENDB = str(ROOT / "data" / "generated" / "questions.sqlite")
Q_OPEN = "q-06b1a2b5b858"
NEEDS_KEY = pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY"),
                               reason="sin GEMINI_API_KEY")


class StubProvider:
    provider_name = "stub"
    model_name = "stub-1"

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def generate(self, messages, *, temperature=0.0, max_tokens=600):
        self.calls += 1
        return LLMResponse(text=json.dumps(self.payload, ensure_ascii=False),
                           provider=self.provider_name, model=self.model_name)


@pytest.fixture(scope="module")
def svc():
    return CorrectionService(KB, GENDB)


def test_assist_confirm_keeps_deterministic(svc):
    stub = StubProvider({"hints": [{"criterion": "REASONING", "assessment": "confirm",
                                    "detail": "ok", "evidence_ids": []}]})
    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % GENDB, uri=True)
    try:
        qid = con.execute("SELECT question_id FROM questions WHERE type='OPEN' AND status='VALID' LIMIT 1").fetchone()[0]
    finally:
        con.close()
    a = svc.correct(qid, "Respuesta con conceptos del material.", student_id="t1")
    b = svc.correct(qid, "Respuesta con conceptos del material.", student_id="t1",
                    llm_assist=True, provider=stub)
    assert stub.calls == 1
    assert (a.status, a.score) == (b.status, b.score)


def test_assist_review_flags_needs_review(svc):
    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % GENDB, uri=True)
    try:
        row = con.execute("SELECT question_id FROM questions WHERE type='OPEN' AND status='VALID' LIMIT 1").fetchone()
        ev = con.execute("SELECT body_json FROM questions WHERE question_id=?", (row[0],)).fetchone()
    finally:
        con.close()
    import json as _j
    ev_ids = _j.loads(ev[0]).get("evidence_refs", [])[:1]
    stub = StubProvider({"hints": [{"criterion": "REASONING", "assessment": "review",
                                    "detail": "ambiguo", "evidence_ids": ev_ids}]})
    c = svc.correct(row[0], "Respuesta con conceptos del material.", student_id="t1",
                    llm_assist=True, provider=stub)
    assert stub.calls == 1
    assert c.status == "NEEDS_REVIEW"
    assert any(e.error_type == "AMBIGUOUS_ANSWER" for e in c.detected_errors)


def test_assist_invalid_evidence_ignored(svc):
    stub = StubProvider({"hints": [{"criterion": "REASONING", "assessment": "review",
                                    "detail": "x", "evidence_ids": ["chunk-falso"]}]})
    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % GENDB, uri=True)
    try:
        qid = con.execute("SELECT question_id FROM questions WHERE type='OPEN' AND status='VALID' LIMIT 1").fetchone()[0]
    finally:
        con.close()
    a = svc.correct(qid, "Respuesta.", student_id="t1")
    b = svc.correct(qid, "Respuesta.", student_id="t1", llm_assist=True, provider=stub)
    assert stub.calls == 1
    assert (a.status, a.score) == (b.status, b.score)
    assert not any(e.error_type == "AMBIGUOUS_ANSWER" for e in b.detected_errors)


def test_assist_malformed_json_safe(svc):
    class Bad:
        provider_name = "bad"
        model_name = "bad"

        def generate(self, messages, *, temperature=0.0, max_tokens=600):
            return LLMResponse(text="no json at all", provider="bad", model="bad")

    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % GENDB, uri=True)
    try:
        qid = con.execute("SELECT question_id FROM questions WHERE type='OPEN' AND status='VALID' LIMIT 1").fetchone()[0]
    finally:
        con.close()
    a = svc.correct(qid, "Respuesta.", student_id="t1")
    b = svc.correct(qid, "Respuesta.", student_id="t1", llm_assist=True, provider=Bad())
    assert (a.status, a.score) == (b.status, b.score)


@NEEDS_KEY
def test_live_assist_open(svc):
    from app.llm.gemini import GeminiProvider
    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % GENDB, uri=True)
    try:
        qid = con.execute("SELECT question_id FROM questions WHERE type='OPEN' AND status='VALID' LIMIT 1").fetchone()[0]
    finally:
        con.close()
    try:
        c = svc.correct(qid, "Respuesta con conceptos del material.", student_id="t1",
                        llm_assist=True, provider=GeminiProvider())
    except RuntimeError as e:
        import pytest as _pt
        if "HTTPError 429" in str(e) or "HTTPError 50" in str(e) or "transitorio" in str(e):
            _pt.skip("proveedor no disponible")
        raise
    assert c.status in ("CORRECT", "PARTIALLY_CORRECT", "INCORRECT", "NEEDS_REVIEW")
    assert c.provenance


def test_llm_score_field_ignored(svc):
    # Aunque el LLM devuelva un campo score, la nota sale de la rubrica.
    class Greedy:
        provider_name = "greedy"
        model_name = "greedy"

        def generate(self, messages, *, temperature=0.0, max_tokens=600):
            return LLMResponse(text='{"hints": [], "score": 10}',
                               provider="greedy", model="greedy")

    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % GENDB, uri=True)
    try:
        qid = con.execute("SELECT question_id FROM questions WHERE type='OPEN'"
                          " AND status='VALID' LIMIT 1").fetchone()[0]
    finally:
        con.close()
    a = svc.correct(qid, "Respuesta.", student_id="t1")
    b = svc.correct(qid, "Respuesta.", student_id="t1", llm_assist=True,
                    provider=Greedy())
    assert (a.status, a.score) == (b.status, b.score)
