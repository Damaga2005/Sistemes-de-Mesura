"""Tests recovery B5.12: reinicio sin perdida de estado persistido."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from app.application.adaptive import AdaptivePracticeWorkflow  # noqa: E402
from app.application.errors import AppError  # noqa: E402
from app.application.exam import ExamWorkflow  # noqa: E402
from app.application.practice import PracticeWorkflow  # noqa: E402
from app.application.review import ReviewWorkflow  # noqa: E402
from harness import build_app, ctx, reopen_app, sess  # noqa: E402

BP = {"title": "t", "version": "1", "seed": 7, "duration_seconds": 600,
      "question_count": 1, "topics": [2], "types": {"TRUE_FALSE": 1},
      "difficulty": {"EASY": 1.0}, "exam_kind": "MOCK_EXAM"}
T0 = "2026-09-05T10:00:00+00:00"


def full_exam_to_grade(app, student="alu-1", answer="F"):
    ex = ExamWorkflow(app)
    c = ctx(app, student=student, workflow="EXAM")
    s = sess(app, student=student, workflow="EXAM", nonce="rc")
    eid = app.exam_sessions.store_blueprint(dict(BP))["exam_id"]
    app.exam_sessions.prepare_exam(eid)
    xsid = ex.create(c, s, eid)["data"]["exam_session"]["session_id"]
    ex.prepare(c, s, xsid)
    return ex, c, s, xsid


def test_exam_restart_continue(tmp_path):
    app = build_app(tmp_path)
    ex, c, s, xsid = full_exam_to_grade(app)
    del app, ex, c, s
    app2 = reopen_app(tmp_path)
    ex2 = ExamWorkflow(app2)
    c2 = ctx(app2, workflow="EXAM")
    s2 = sess(app2, workflow="EXAM", nonce="rc2")
    out = ex2.start(c2, s2, xsid, now=T0)
    assert out["data"]["started"]["status"] == "IN_PROGRESS"
    ex2.save_answer(c2, s2, xsid, 0, "F",
                    now="2026-09-05T10:01:00+00:00")
    ex2.submit(c2, s2, xsid, now="2026-09-05T10:04:00+00:00")
    g = ex2.grade(c2, s2, xsid, now="2026-09-05T10:05:00+00:00")
    assert g["data"]["result"]["percentage"] == "85.00"


def test_practice_restart_submit(tmp_path):
    app = build_app(tmp_path)
    p = PracticeWorkflow(app)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="rc")
    ps = p.start(c, s, topic=2, question_type="TRUE_FALSE",
                 seed=11)["data"]["session"]
    del app, p, c, s
    app2 = reopen_app(tmp_path)
    p2 = PracticeWorkflow(app2)
    out = p2.submit_answer(ctx(app2, workflow="PRACTICE"), ps, "V",
                           attempt_id="att-rc-p")
    assert out["data"]["result"]["status"] == "CORRECT"
    m = p2.get_result(ctx(app2, workflow="PRACTICE"),
                      sess(app2, workflow="PRACTICE", nonce="rcm"),
                      ["topic:T02"])
    assert m["data"]["mastery"][0]["score"] == 1.0


def test_adaptive_restart_recommend(tmp_path):
    app = build_app(tmp_path)
    p = PracticeWorkflow(app)
    a = AdaptivePracticeWorkflow(app)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="rc")
    p.start(c, s, topic=2, question_type="SHORT_ANSWER", seed=13)
    p.submit_answer(c, s, "basura total", attempt_id="att-rc-a")
    ca = ctx(app, workflow="ADAPTIVE_PRACTICE")
    first = a.recommend(ca, sess(app, workflow="ADAPTIVE_PRACTICE",
                                 nonce="rc"),
                        limit=5, seed=7)["data"]["recommendations"]
    del app, p, a
    app2 = reopen_app(tmp_path)
    a2 = AdaptivePracticeWorkflow(app2)
    again = a2.recommend(ctx(app2, workflow="ADAPTIVE_PRACTICE"),
                         sess(app2, workflow="ADAPTIVE_PRACTICE",
                              nonce="rc2"),
                         limit=5, seed=7)["data"]["recommendations"]
    assert [x["knowledge_unit_id"] for x in again] == \
        [x["knowledge_unit_id"] for x in first]


def test_review_restart(tmp_path):
    app = build_app(tmp_path)
    ex, c, s, xsid = full_exam_to_grade(app)
    ex.start(c, s, xsid, now=T0)
    ex.save_answer(c, s, xsid, 0, "F",
                   now="2026-09-05T10:01:00+00:00")
    ex.submit(c, s, xsid, now="2026-09-05T10:04:00+00:00")
    ex.grade(c, s, xsid, now="2026-09-05T10:05:00+00:00")
    r1 = ReviewWorkflow(app).get_review(
        ctx(app, workflow="REVIEW"),
        sess(app, workflow="REVIEW", nonce="rc"),
        xsid)["data"]
    del app
    app2 = reopen_app(tmp_path)
    r2 = ReviewWorkflow(app2).get_review(
        ctx(app2, workflow="REVIEW"),
        sess(app2, workflow="REVIEW", nonce="rc2"),
        xsid)["data"]
    assert r2 == r1


def test_subprocess_practice_submit(tmp_path):
    app = build_app(tmp_path)
    p = PracticeWorkflow(app)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="rc")
    ps = p.start(c, s, topic=2, question_type="TRUE_FALSE",
                 seed=11)["data"]["session"]
    del app, p, c, s
    code = (
        "import json, sys; "
        "sys.path.insert(0, %r); sys.path.insert(0, %r); "
        "from pathlib import Path; "
        "from harness import reopen_app, ctx; "
        "from app.application.practice import PracticeWorkflow; "
        "from app.application.session import ApplicationSession; "
        "app = reopen_app(Path(%r)); "
        "ps = ApplicationSession.from_dict(json.loads(%r)); "
        "out = PracticeWorkflow(app).submit_answer("
        "ctx(app, workflow='PRACTICE'), ps, 'V', "
        "attempt_id='att-rc-sub'); "
        "print(json.dumps(out['data']['result']))"
        % (str(Path(__file__).resolve().parent.parent.parent),
           str(Path(__file__).parent), str(tmp_path),
           json.dumps(ps)))
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr[-500:]
    res = json.loads(proc.stdout.strip().splitlines()[-1])
    assert res["status"] == "CORRECT" and res["replayed"] is False
