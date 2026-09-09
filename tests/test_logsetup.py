import logging
from pathlib import Path

from app import logsetup


def test_configure_writes_request_lines(tmp_path):
    logsetup.configure(tmp_path, "INFO")
    logsetup.request("GET", "/api/study/topics", 200, 12.5)
    for h in logging.getLogger("sistemes.request").handlers:
        h.flush()
    text = (tmp_path / "serve.log").read_text(encoding="utf-8")
    assert "GET /api/study/topics 200 12" in text


def test_no_student_content_helper_only_takes_scalars():
    # request() signature accepts only method/path/status/ms — enforced by call sites
    import inspect
    params = list(inspect.signature(logsetup.request).parameters)
    assert params == ["method", "path", "status", "ms"]


def test_error_log_captures_exceptions(tmp_path):
    logsetup.configure(tmp_path, "INFO")
    try:
        raise ValueError("boom")
    except ValueError:
        logsetup.exception("fallo de prueba")
    for h in logging.getLogger("sistemes.error").handlers:
        h.flush()
    text = (tmp_path / "error.log").read_text(encoding="utf-8")
    assert "fallo de prueba" in text and "ValueError" in text


def test_configure_is_idempotent(tmp_path):
    logsetup.configure(tmp_path)
    logsetup.configure(tmp_path)
    assert len(logging.getLogger("sistemes.request").handlers) == 1


def test_level_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SM_LOG_LEVEL", "WARNING")
    logsetup.configure(tmp_path)
    assert logging.getLogger("sistemes.request").level == logging.WARNING
