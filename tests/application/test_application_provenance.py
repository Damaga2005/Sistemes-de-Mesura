"""Tests provenance/idempotencia/fronteras Application (B4.9-B4.13)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from app.application.errors import AppError  # noqa: E402
from app.application.exam import ExamWorkflow  # noqa: E402
from app.application.practice import PracticeWorkflow  # noqa: E402
from app.application.review import ReviewWorkflow  # noqa: E402
from app.application.tutor import TutorWorkflow  # noqa: E402
from harness import build_app, ctx, sess  # noqa: E402

T0 = "2026-09-05T10:00:00+00:00"
BP = {"title": "t", "version": "1", "seed": 7, "duration_seconds": 600,
      "question_count": 1, "topics": [2], "types": {"TRUE_FALSE": 1},
      "difficulty": {"EASY": 1.0}, "exam_kind": "MOCK_EXAM"}


def test_tutor_chain(tmp_path):
    app = build_app(tmp_path)
    r = TutorWorkflow(app).ask(ctx(app), "què és la incertesa expandida?")
    d = r["data"]
    assert d["answer"] and d["provenance"] and d["claims"]
    assert d["versions"].get("retrieval") == "retrieval-2.0"


def test_practice_chain(tmp_path):
    app = build_app(tmp_path)
    w = PracticeWorkflow(app)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="p")
    q = w.start(c, s, topic=2, question_type="TRUE_FALSE",
                seed=11)["data"]["question"]
    out = w.submit_answer(c, s, "V", attempt_id="att-p-1")["data"]["result"]
    assert out["attempt_id"] == "att-p-1"
    assert out["mastery"]
    assert out["status"] in ("CORRECT", "PARTIALLY_CORRECT", "INCORRECT",
                             "NO_ANSWER")


def test_adaptive_chain(tmp_path):
    from app.application.adaptive import AdaptivePracticeWorkflow
    app = build_app(tmp_path)
    w = AdaptivePracticeWorkflow(app)
    c = ctx(app, workflow="ADAPTIVE_PRACTICE")
    s = sess(app, workflow="ADAPTIVE_PRACTICE", nonce="a")
    r = w.recommend(c, s, limit=5, seed=7)
    assert r["ok"] and isinstance(r["data"]["recommendations"], list)


def test_exam_chain(tmp_path):
    app = build_app(tmp_path)
    w = ExamWorkflow(app)
    c = ctx(app, workflow="EXAM")
    s = sess(app, workflow="EXAM", nonce="e")
    eid = app.exam_sessions.store_blueprint(BP)["exam_id"]
    app.exam_sessions.prepare_exam(eid)
    xsid = w.create(c, s, eid)["data"]["exam_session"]["session_id"]
    w.prepare(c, s, xsid)
    w.start(c, s, xsid, now=T0)
    w.save_answer(c, s, xsid, 0, "V", now=T0)
    w.submit(c, s, xsid, now=T0)
    g = w.grade(c, s, xsid, now=T0)["data"]["result"]
    assert g["question_count"] == 1 and "percentage" in g
    rev = ReviewWorkflow(app).get_review(
        ctx(app, workflow="REVIEW"), sess(app, workflow="REVIEW",
                                          nonce="e"),
        xsid)["data"]
    assert rev["session_id"] == xsid


def test_review_chain(tmp_path):
    app = build_app(tmp_path)
    w = ExamWorkflow(app)
    c = ctx(app, workflow="EXAM")
    s = sess(app, workflow="EXAM", nonce="r")
    eid = app.exam_sessions.store_blueprint(BP)["exam_id"]
    app.exam_sessions.prepare_exam(eid)
    xsid = w.create(c, s, eid)["data"]["exam_session"]["session_id"]
    w.prepare(c, s, xsid)
    w.start(c, s, xsid, now=T0)
    w.save_answer(c, s, xsid, 0, "V", now=T0)
    w.submit(c, s, xsid, now=T0)
    w.grade(c, s, xsid, now=T0)
    r = ReviewWorkflow(app)
    cr = ctx(app, workflow="REVIEW")
    sr = sess(app, workflow="REVIEW", nonce="r")
    assert r.get_result(cr, sr, xsid)["ok"]
    assert r.get_question_review(cr, sr, xsid, 0)["ok"]
    assert r.get_mastery_view(cr, sr, xsid)["ok"]


def test_submit_x3_practice(tmp_path):
    app = build_app(tmp_path)
    w = PracticeWorkflow(app)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="s3")
    w.start(c, s, topic=2, question_type="TRUE_FALSE", seed=11)
    outs = [w.submit_answer(c, s, "V", attempt_id="att-s3")["data"]["result"]
            for _ in range(3)]
    assert all(o["attempt_id"] == "att-s3" for o in outs)
    assert all(o["replayed"] for o in outs[1:])


def test_grade_x3_exam(tmp_path):
    app = build_app(tmp_path)
    w = ExamWorkflow(app)
    c = ctx(app, workflow="EXAM")
    s = sess(app, workflow="EXAM", nonce="g3")
    eid = app.exam_sessions.store_blueprint(BP)["exam_id"]
    app.exam_sessions.prepare_exam(eid)
    xsid = w.create(c, s, eid)["data"]["exam_session"]["session_id"]
    w.prepare(c, s, xsid)
    w.start(c, s, xsid, now=T0)
    w.save_answer(c, s, xsid, 0, "V", now=T0)
    w.submit(c, s, xsid, now=T0)
    a = w.grade(c, s, xsid, now=T0)["data"]["result"]
    b = w.grade(c, s, xsid, now=T0)["data"]["result"]
    d = w.grade(c, s, xsid, now=T0)["data"]["result"]
    assert a == b == d


def test_review_x3(tmp_path):
    app = build_app(tmp_path)
    w = ExamWorkflow(app)
    c = ctx(app, workflow="EXAM")
    s = sess(app, workflow="EXAM", nonce="r3")
    eid = app.exam_sessions.store_blueprint(BP)["exam_id"]
    app.exam_sessions.prepare_exam(eid)
    xsid = w.create(c, s, eid)["data"]["exam_session"]["session_id"]
    w.prepare(c, s, xsid)
    w.start(c, s, xsid, now=T0)
    w.save_answer(c, s, xsid, 0, "V", now=T0)
    w.submit(c, s, xsid, now=T0)
    w.grade(c, s, xsid, now=T0)
    r = ReviewWorkflow(app)
    cr = ctx(app, workflow="REVIEW")
    sr = sess(app, workflow="REVIEW", nonce="r3")
    assert (r.get_review(cr, sr, xsid) ==
            r.get_review(cr, sr, xsid) ==
            r.get_review(cr, sr, xsid))


def test_answer_x3_exam(tmp_path):
    app = build_app(tmp_path)
    w = ExamWorkflow(app)
    c = ctx(app, workflow="EXAM")
    s = sess(app, workflow="EXAM", nonce="a3")
    eid = app.exam_sessions.store_blueprint(BP)["exam_id"]
    app.exam_sessions.prepare_exam(eid)
    xsid = w.create(c, s, eid)["data"]["exam_session"]["session_id"]
    w.prepare(c, s, xsid)
    w.start(c, s, xsid, now=T0)
    for _ in range(3):
        out = w.save_answer(c, s, xsid, 0, "V", now=T0)
    assert out["data"]["saved"]["version"] == 3


def test_no_provider_imports(tmp_path):
    import re
    root = Path(__file__).resolve().parent.parent.parent / "app" \
        / "application"
    hits = []
    for f in root.glob("*.py"):
        src = f.read_text(encoding="utf-8")
        for tok in ("Gemini", "OpenAI", "Mouse Spark", "gemini", "openai",
                    "API_KEY", "api_key", "provider client",
                    "provider_client"):
            if re.search(r"\b%s\b" % re.escape(tok), src):
                hits.append((f.name, tok))
    assert hits == []


def test_no_sqlite_in_application(tmp_path):
    import re
    root = Path(__file__).resolve().parent.parent.parent / "app" \
        / "application"
    hits = []
    for f in root.glob("*.py"):
        src = f.read_text(encoding="utf-8")
        if re.search(r"sqlite3\.connect|\.execute\(", src):
            hits.append(f.name)
    assert hits == []


def test_no_adaptive_constants(tmp_path):
    src = (Path(__file__).resolve().parent.parent.parent / "app" /
           "application" / "adaptive.py").read_text(encoding="utf-8")
    for tok in ("PriorityCalculator(", "DifficultySelector(",
                "RecommendationBuilder(", "LearningPathSelector(",
                "SpacingPolicy", "PRIORITY_WEIGHTS"):
        assert tok not in src


def test_error_codes_all_reachable():
    from app.application.errors import AppError, map_error
    assert map_error(ValueError("sesion inexistente: x")).code == "NOT_FOUND"
    assert map_error(ValueError("transicion invalida")).code == "STATE_ERROR"
    assert map_error(ValueError("blueprint invalido")).code == \
        "VALIDATION_ERROR"
    assert map_error(ValueError("reasoning_unavailable: t")).code == \
        "GENERATION_ERROR"
