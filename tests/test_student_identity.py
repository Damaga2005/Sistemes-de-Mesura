import importlib

import web.server as server


def test_bridge_defaults_student_to_me(monkeypatch, tmp_path):
    monkeypatch.delenv("SM_STUDENT", raising=False)
    b = server.Bridge(workdir=str(tmp_path))
    assert b.student == "me"


def test_bridge_reads_sm_student_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("SM_STUDENT", "damaga")
    b = server.Bridge(workdir=str(tmp_path))
    assert b.student == "damaga"


def test_no_demo_student_constant_remains():
    src = importlib.import_module("web.server").__file__
    with open(src, encoding="utf-8") as fh:
        assert "DEMO_STUDENT" not in fh.read()
