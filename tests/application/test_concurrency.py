"""Tests concurrencia B6.15: modelo certificado (lecturas + races seguras).

No incluye grade concurrente: P0 documentado (CC02 del benchmark
final + docs/PHASE_10_B6.md). Solo patrones con resultado contractual.
"""
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from app.application.adaptive import AdaptivePracticeWorkflow  # noqa: E402
from app.application.exam import ExamWorkflow  # noqa: E402
from app.application.practice import PracticeWorkflow  # noqa: E402
from app.application.tutor import TutorWorkflow  # noqa: E402
from harness import build_app, ctx, reopen_app, sess  # noqa: E402

Q = "qu\u00e8 \u00e9s la incertesa expandida?"


def run(n, fn):
    errs = []

    def w():
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            errs.append(repr(e))

    ts = [threading.Thread(target=w) for _ in range(n)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    return errs


def test_submit_same_attempt_race(tmp_path):
    app = build_app(tmp_path)
    p = PracticeWorkflow(app)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="cc")
    p.start(c, s, topic=2, question_type="TRUE_FALSE", seed=11)
    outs = []
    errs = run(2, lambda: outs.append(
        p.submit_answer(c, s, "V",
                        attempt_id="att-cc-t")["data"]["result"]))
    assert not errs
    assert sorted(o["replayed"] for o in outs) == [False, True]
    m = p.get_result(c, sess(app, workflow="PRACTICE", nonce="ccm"),
                     ["topic:T02"])
    assert m["data"]["mastery"][0]["score"] == 1.0


def test_recommend_race_equal(tmp_path):
    app = build_app(tmp_path)
    p = PracticeWorkflow(app)
    a = AdaptivePracticeWorkflow(app)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="cc")
    p.start(c, s, topic=2, question_type="SHORT_ANSWER", seed=13)
    p.submit_answer(c, s, "basura total", attempt_id="att-cc-r")
    ca = ctx(app, workflow="ADAPTIVE_PRACTICE")
    outs = []
    errs = run(2, lambda: outs.append(
        a.recommend(ca, sess(app, workflow="ADAPTIVE_PRACTICE",
                             nonce="cc%d" % len(outs)),
                    limit=5, seed=7)["data"]["recommendations"]))
    assert not errs
    assert outs[0] == outs[1]


def test_ask_isolated_race_equal(tmp_path):
    outs = []

    def one(n):
        app = reopen_app(tmp_path, fresh_retriever=True)
        outs.append(TutorWorkflow(app).ask(
            ctx(app, workflow="TUTOR"), Q)["data"]["answer"])

    build_app(tmp_path)
    assert not run(2, lambda: one(len(outs)))
    assert len(outs) == 2 and outs[0] == outs[1]
