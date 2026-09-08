"""F11-B4: contractes de presentació d'examen, sense duplicar domini."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web"))
from server import Bridge


ROOT = Path(__file__).resolve().parents[2]


def _bridge(tmp_path):
    return Bridge(workdir=str(tmp_path), gen_src=str(
        ROOT / "data" / "generated" / "questions.sqlite"))


def _create(bridge, **overrides):
    body = {"title": "Examen UX", "exam_kind": "MOCK_EXAM",
            "topics": [2], "question_count": 1,
            "duration_seconds": 600, "seed": 7}
    body.update(overrides)
    status, payload, _ = bridge.route("POST", "/api/exam/create",
                                      body=body)
    assert status == 200
    return payload["exam_session"]["session_id"]


def test_exam_state_exposes_persisted_snapshot_metadata(tmp_path):
    bridge = _bridge(tmp_path)
    xsid = _create(bridge)

    status, state, _ = bridge.route(
        "GET", "/api/exam/state", {"exam_session_id": xsid})

    assert status == 200
    assert state["title"] == "Examen UX"
    assert state["question_count"] == 1
    assert state["duration_seconds"] == 600
    assert state["snapshot"]["immutable"] is True
    assert state["snapshot"]["instances"][0]["fingerprint"]


def test_exam_metadata_survives_reentry_with_new_bridge(tmp_path):
    first = _bridge(tmp_path)
    xsid = _create(first, title="Reentrada")

    second = _bridge(tmp_path)
    status, state, _ = second.route(
        "GET", "/api/exam/state", {"exam_session_id": xsid})

    assert status == 200
    assert state["title"] == "Reentrada"
    assert state["exam_id"]


def test_exam_mine_returns_actionable_metadata(tmp_path):
    bridge = _bridge(tmp_path)
    _create(bridge, title="Llista")

    status, payload, _ = bridge.route("GET", "/api/exam/mine")

    assert status == 200
    item = payload["sessions"][0]
    assert item["title"] == "Llista"
    assert item["question_count"] == 1
    assert item["duration_seconds"] == 600


def test_real_exam_ui_never_renders_answer_key(tmp_path):
    script = (ROOT / "web" / "static" / "js" / "exam.js").read_text(
        encoding="utf-8")
    assert "correct_answer" not in script
    assert "expected_answer" not in script
    assert "solution" not in script


def test_real_exam_review_does_not_send_formula_metadata(tmp_path):
    bridge = _bridge(tmp_path)
    xsid = _create(bridge, exam_kind="REAL_EXAM")
    bridge.route("POST", "/api/exam/start",
                 body={"exam_session_id": xsid,
                       "now": "2026-09-05T10:00:00+00:00"})
    bridge.route("POST", "/api/exam/save",
                 body={"exam_session_id": xsid, "position": 0,
                       "answer": "F",
                       "now": "2026-09-05T10:01:00+00:00"})
    bridge.route("POST", "/api/exam/submit",
                 body={"exam_session_id": xsid,
                       "now": "2026-09-05T10:04:00+00:00"})
    bridge.route("POST", "/api/exam/grade",
                 body={"exam_session_id": xsid,
                       "now": "2026-09-05T10:05:00+00:00"})

    status, review, _ = bridge.route(
        "GET", "/api/exam/review", {"exam_session_id": xsid})

    assert status == 200
    feedback = review["questions"][0]["feedback"]
    assert feedback["formula"] is None
    assert feedback["correct_answer"] is None
    assert feedback["solution"] is None
    assert "prompt" not in review["questions"][0]
    assert "options" not in review["questions"][0]


def test_history_is_backend_owned_and_includes_result_summary(tmp_path):
    bridge = _bridge(tmp_path)
    xsid = _create(bridge, title="Historial")
    bridge.route("POST", "/api/exam/start",
                 body={"exam_session_id": xsid,
                       "now": "2026-09-05T10:00:00+00:00"})
    bridge.route("POST", "/api/exam/submit",
                 body={"exam_session_id": xsid,
                       "now": "2026-09-05T10:04:00+00:00"})

    status, payload, _ = bridge.route("GET", "/api/exam/history")

    assert status == 200
    item = payload["history"][0]
    assert item["session_id"] == xsid
    assert item["title"] == "Historial"
    assert item["created_at"]
    assert item["submitted_at"] == "2026-09-05T10:04:00+00:00"
    assert item["result"]["available"] is False
    assert item["result"]["reason"] == "RESULT_NOT_AVAILABLE"


def test_history_exposes_result_only_after_backend_grading(tmp_path):
    bridge = _bridge(tmp_path)
    xsid = _create(bridge, title="Resultat")
    bridge.route("POST", "/api/exam/start", body={"exam_session_id": xsid})
    bridge.route("POST", "/api/exam/submit", body={"exam_session_id": xsid})
    bridge.route("POST", "/api/exam/grade", body={"exam_session_id": xsid})

    status, payload, _ = bridge.route("GET", "/api/exam/history")

    assert status == 200
    result = payload["history"][0]["result"]
    assert result["available"] is True
    assert result["percentage"]
    assert "student_id" not in result
    assert "questions" not in result


def test_history_route_preserves_forbidden_semantics(tmp_path):
    bridge = _bridge(tmp_path)
    xsid = _create(bridge)
    status, payload, _ = bridge.route(
        "GET", "/api/exam/history", {"student_id": "other"})
    assert status == 200
    assert payload["history"]
    status, payload, _ = bridge.route(
        "GET", "/api/exam/result", {"exam_session_id": "missing"})
    assert status == 404
    assert payload["code"] == "NOT_FOUND"


def test_review_results_history_pages_are_direct_entry_points(tmp_path):
    for name in ("history.html", "results.html", "review.html"):
        page = (ROOT / "web" / name).read_text(encoding="utf-8")
        assert 'lang="ca"' in page
        assert 'id="main"' in page
        assert 'aria-live="polite"' in page


def test_review_formula_uses_existing_safe_renderer_for_authorized_feedback():
    server = (ROOT / "web" / "server.py").read_text(encoding="utf-8")
    review = (ROOT / "web" / "static" / "js" / "review.js").read_text(
        encoding="utf-8")
    assert "render_latex" in server
    assert "formula" in review
    assert "innerHTML" in review
