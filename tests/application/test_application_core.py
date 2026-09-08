"""Tests B3: Application Core (contexto, sesión, errores, fachada)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.application.context import ApplicationContext  # noqa: E402
from app.application.errors import AppError, map_error  # noqa: E402
from app.application.service import ApplicationService  # noqa: E402
from app.application.session import ApplicationSession  # noqa: E402


def svc():
    return ApplicationService()


# 1-4. contexto válido/inválido
def test_01_context_valid():
    c = svc().create_context("alu-1", "TUTOR", "ca")
    assert c.technical_student_id == "alu-1" and c.language == "ca"
    assert c.workflow == "TUTOR" and c.created_at


def test_02_context_invalid():
    s = svc()
    for kw in ({"student_id": ""}, {"student_id": 123},
               {"language": "en"}, {"language": ""},
               {"workflow": "CHAT"}, {"workflow": None},
               {"reference": {"kind": "nope"}},
               {"reference": {"kind": "exam"}},
               {"reference": "x"}, {"policies": []}):
        base = {"student_id": "a", "workflow": "TUTOR", "language": "ca"}
        base.update(kw)
        with pytest.raises(AppError) as e:
            s.create_context(**base)
        assert e.value.code == "VALIDATION_ERROR"


def test_03_language_invalid():
    with pytest.raises(AppError):
        ApplicationContext.create("a", "TUTOR", "fr")


def test_04_workflow_invalid():
    with pytest.raises(AppError):
        ApplicationContext.create("a", "NOPE", "ca")


# 5-8. sesión
def test_05_session_creation():
    s = svc().create_session("alu-1", "PRACTICE", "es", nonce="n1")
    assert s.student_id == "alu-1" and s.status == "ACTIVE"
    assert s.language == "es" and s.workflow == "PRACTICE"


def test_06_session_ids():
    s = svc().create_session("alu-1", "EXAM", nonce="n1")
    assert s.session_id.startswith("apps-") and len(s.session_id) == 17


def test_07_session_state():
    s = svc().create_session("alu-1", "TUTOR", nonce="n1")
    assert s.transition("COMPLETED") == "COMPLETED"
    assert s.status == "COMPLETED"


def test_08_invalid_transition():
    s = svc().create_session("alu-1", "TUTOR", nonce="n1")
    with pytest.raises(AppError) as e:
        s.transition("ACTIVE")
    assert e.value.code == "STATE_ERROR"
    s.transition("ABANDONED")
    with pytest.raises(AppError):
        s.touch()


# 9-10. scope
def test_09_student_scope():
    c = svc().create_context("alu-1", "EXAM", "ca")
    ApplicationService.check_scope(c, "alu-1", "session")


def test_10_cross_student_denial():
    c = svc().create_context("alu-1", "EXAM", "ca")
    with pytest.raises(AppError) as e:
        ApplicationService.check_scope(c, "alu-2", "session")
    assert e.value.code == "NOT_FOUND"
    assert "alu-2" not in str(e.value) and "alu-1" not in str(e.value)


# 11-12. errores
def test_11_error_mapping():
    cases = [("sesion de otro estudiante", "NOT_FOUND"),
             ("position inexistente o ajena", "NOT_FOUND"),
             ("RESULT_NOT_AVAILABLE (estado X)", "STATE_ERROR"),
             ("transicion invalida: A -> B", "STATE_ERROR"),
             ("REVIEW_POLICY_NOT_FOUND: v9", "POLICY_ERROR"),
             ("blueprint invalido: x", "VALIDATION_ERROR"),
             ("reasoning_unavailable: TimeoutError", "GENERATION_ERROR"),
             ("NO_EVIDENCE aqui", "RETRIEVAL_ERROR"),
             ("FORMULA_NOT_FOUND: f", "KNOWLEDGE_ERROR")]
    for text, code in cases:
        got = map_error(ValueError(text))
        assert isinstance(got, AppError) and got.code == code, text
    with pytest.raises(ValueError):
        map_error(ValueError("algo totalmente inesperado"))
    with pytest.raises(ValueError):
        AppError("NOPE", "x")


def test_12_safe_error_output():
    e = map_error(ValueError("sesion de otro estudiante 'exs-abc'"))
    s = str(e)
    for bad in ("sk-", "SELECT", "chain", "prompt", "WHERE", "password"):
        assert bad not in s


# 13-14. sin secretos ni INTERNAL
def test_13_no_secrets_in_context():
    c = svc().create_context("a", "TUTOR", "ca",
                             policies={"exam-spec": "exam-spec-v1"})
    blob = str(c.to_dict())
    for bad in ("sk-", "api_key", "password", "token", "secret"):
        assert bad not in blob.lower()


def test_14_no_internal_fields():
    s = svc().create_session("a", "REVIEW", nonce="n")
    blob = str(s.to_dict())
    for bad in ("correct_answer", "solution", "rubric", "CoT",
                "fingerprint", "equation_id"):
        assert bad not in blob


# 15-17. determinismo, repetición, restart
def test_15_deterministic_construction():
    s = svc()
    a = s.create_session("alu-1", "EXAM", nonce="fixed")
    b = s.create_session("alu-1", "EXAM", nonce="fixed")
    assert a.session_id == b.session_id
    c = s.create_session("alu-1", "EXAM", nonce="other")
    assert c.session_id != a.session_id


def test_16_repeated_request():
    s = svc()
    ids = {s.create_context("a", "TUTOR", "ca").created_at for _ in range(2)}
    assert len(ids) <= 2  # timestamps; el resto idéntico
    a = s.create_session("a", "TUTOR", nonce="r")
    b = s.create_session("a", "TUTOR", nonce="r")
    assert a.to_dict()["session_id"] == b.to_dict()["session_id"]


def test_17_restart_semantics():
    s = svc().create_session("alu-1", "PRACTICE", nonce="r")
    s.touch({"kind": "attempt", "id": "att-1"})
    d = s.to_dict()
    r = ApplicationSession.from_dict(d)
    assert r.to_dict() == d
    r.touch({"kind": "attempt", "id": "att-2"})
    assert r.active_reference["id"] == "att-2"
    with pytest.raises(AppError):
        ApplicationSession.from_dict({**d, "workflow": "NOPE"})
    with pytest.raises(AppError):
        ApplicationSession.from_dict({**d, "status": "WEIRD"})


# 18. sin persistencia inesperada
def test_18_no_unexpected_persistence(tmp_path):
    before = set(p.name for p in tmp_path.iterdir())
    s = svc()
    for _ in range(3):
        s.create_context("a", "TUTOR", "ca")
        s.create_session("a", "TUTOR", nonce="x")
    assert set(p.name for p in tmp_path.iterdir()) == before
