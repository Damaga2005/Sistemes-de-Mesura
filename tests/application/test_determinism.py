"""Tests determinismo B5.13: misma entrada, mismo resultado logico."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from app.application.adaptive import AdaptivePracticeWorkflow  # noqa: E402
from app.application.exam import ExamWorkflow  # noqa: E402
from app.application.practice import PracticeWorkflow  # noqa: E402
from app.application.tutor import TutorWorkflow  # noqa: E402
from harness import build_app, ctx, sess  # noqa: E402

BP = {"title": "t", "version": "1", "seed": 7, "duration_seconds": 600,
      "question_count": 1, "topics": [2], "types": {"TRUE_FALSE": 1},
      "difficulty": {"EASY": 1.0}, "exam_kind": "MOCK_EXAM"}
T0 = "2026-09-05T10:00:00+00:00"
Q = "qu\u00e8 \u00e9s la incertesa expandida?"


def test_practice_qid_pinned(tmp_path):
    app = build_app(tmp_path)
    p = PracticeWorkflow(app)
    q = p.start(ctx(app, workflow="PRACTICE"),
                sess(app, workflow="PRACTICE", nonce="d"),
                topic=2, question_type="TRUE_FALSE",
                seed=11)["data"]["question"]
    assert q["question_id"] == "q-93f3e2c4c7fd"


def test_exam_grade_equal_across_instances(tmp_path_factory):
    pcts = []
    for n, d in enumerate(["a", "b"]):
        tmp = tmp_path_factory.mktemp(d)
        app = build_app(tmp)
        ex = ExamWorkflow(app)
        c = ctx(app, workflow="EXAM")
        s = sess(app, workflow="EXAM", nonce="d")
        eid = app.exam_sessions.store_blueprint(dict(BP))["exam_id"]
        app.exam_sessions.prepare_exam(eid)
        xsid = ex.create(c, s, eid)["data"]["exam_session"]["session_id"]
        ex.prepare(c, s, xsid)
        ex.start(c, s, xsid, now=T0)
        ex.save_answer(c, s, xsid, 0, "F",
                       now="2026-09-05T10:01:00+00:00")
        ex.submit(c, s, xsid, now="2026-09-05T10:04:00+00:00")
        g = ex.grade(c, s, xsid,
                     now="2026-09-05T10:05:00+00:00")["data"]["result"]
        pcts.append((g["percentage"], g["correct_count"],
                     g["partial_count"],
                     [q["question_id"] for q in g["questions"]]))
    assert pcts[0] == pcts[1] == ("85.00", 1, 0, pcts[0][3])


def test_adaptive_recommend_equal_across_instances(tmp_path_factory):
    recs = []
    for n, d in enumerate(["a", "b"]):
        tmp = tmp_path_factory.mktemp(d)
        app = build_app(tmp)
        p = PracticeWorkflow(app)
        a = AdaptivePracticeWorkflow(app)
        c = ctx(app, workflow="PRACTICE")
        s = sess(app, workflow="PRACTICE", nonce="d")
        p.start(c, s, topic=2, question_type="SHORT_ANSWER", seed=13)
        p.submit_answer(c, s, "basura total",
                        attempt_id="att-d-%d" % n)
        r = a.recommend(ctx(app, workflow="ADAPTIVE_PRACTICE"),
                        sess(app, workflow="ADAPTIVE_PRACTICE",
                             nonce="d"),
                        limit=5, seed=7)["data"]["recommendations"]
        recs.append([(x["knowledge_unit_id"], x["action"],
                      x["difficulty"]) for x in r])
    assert recs[0] == recs[1]


def test_tutor_answer_equal_across_instances(tmp_path_factory):
    ans = []
    for d in ["a", "b"]:
        tmp = tmp_path_factory.mktemp(d)
        app = build_app(tmp)
        r = TutorWorkflow(app).ask(ctx(app, workflow="TUTOR"), Q)["data"]
        ans.append((r["answer"], r["status"]))
    assert ans[0] == ans[1]
