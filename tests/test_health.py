import web.server as server


def test_health_ok_when_artifacts_present(tmp_path):
    b = server.Bridge(workdir=str(tmp_path))
    status, payload, _ = b.route("GET", "/api/health", {}, {}, "")
    assert status == 200
    assert payload["status"] == "ok"
    assert set(payload["checks"]) == {"kb", "index", "student_db"}


def test_health_degraded_when_kb_missing(tmp_path, monkeypatch):
    b = server.Bridge(workdir=str(tmp_path))
    monkeypatch.setattr(b, "kb", str(tmp_path / "nope.sqlite"))
    status, payload, _ = b.route("GET", "/api/health", {}, {}, "")
    assert status == 503 and payload["checks"]["kb"] is False
