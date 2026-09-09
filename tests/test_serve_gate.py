from app import cli


def test_serve_aborts_when_check_fast_reports_problems(monkeypatch, capsys):
    monkeypatch.setattr("app.artifacts.check", lambda *a, **k: ["esquema roto"])
    rc = cli.main(["serve"])
    assert rc == 1
    assert "abortado" in capsys.readouterr().err


def test_serve_starts_when_artifacts_ok(monkeypatch):
    monkeypatch.setattr("app.artifacts.check", lambda *a, **k: [])
    called = {}
    monkeypatch.setattr("web.server.main",
                        lambda argv: called.setdefault("argv", argv) or 0)
    assert cli.main(["serve", "--port", "9", "--host", "127.0.0.1"]) == 0
    assert called["argv"] == ["--host", "127.0.0.1", "--port", "9"]
