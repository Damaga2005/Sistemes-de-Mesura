"""Tests AdaptivePracticeWorkflow (B4.3/B4.6): F6 decide, app orquesta."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from app.application.adaptive import AdaptivePracticeWorkflow  # noqa: E402
from app.application.errors import AppError  # noqa: E402
from harness import build_app, ctx, sess  # noqa: E402


def wf(tmp_path):
    app = build_app(tmp_path)
    return app, AdaptivePracticeWorkflow(app)


def rec1(app, w, c, s, **kw):
    args = {"limit": 5, "seed": 7}
    args.update(kw)
    return w.recommend(c, s, **args)


def seed_weak(app, student="alu-1"):
    q1, _ = app.examiner.generate(topic=2, question_type="TRUE_FALSE",
                                   seed=11)
    app.students.submit(student, q1.question_id, q1.correct_answer or "V",
                        attempt_id="att-seed-tf-%s" % student)
    q2, _ = app.examiner.generate(topic=2, question_type="FORMULA",
                                   formula_id="eq-02-0034", seed=14)
    app.students.submit(student, q2.question_id, "$U=u_c/k$",
                        attempt_id="att-seed-%s" % student)
    q3, _ = app.examiner.generate(topic=2, question_type="TRUE_FALSE",
                                   seed=22)
    wrong = "F" if (q3.correct_answer or "V") == "V" else "V"
    app.students.submit(student, q3.question_id, wrong,
                        attempt_id="att-seed-tf2-%s" % student)
    q4, _ = app.examiner.generate(topic=2, question_type="SHORT_ANSWER",
                                   seed=13)
    app.students.submit(student, q4.question_id, "basura total",
                        attempt_id="att-seed-sh-%s" % student)
    return q1, q2, q3, q4


def first_generable(app, w, c, s, limit=10, seed=7):
    from app.application.errors import AppError as _AE
    r = w.recommend(c, s, limit=limit, seed=seed)
    assert r["ok"] and r["data"]["recommendations"]
    for item in r["data"]["recommendations"]:
        try:
            g = w.generate(c, r["data"]["session"], item, seed=seed)
            return r, g, item
        except _AE as e:
            if e.code != "GENERATION_ERROR":
                raise
            continue
    raise AssertionError("ningún item generable")


def test_01_weak_topic(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="ADAPTIVE_PRACTICE"), sess(
        app, workflow="ADAPTIVE_PRACTICE")
    seed_weak(app)
    r = rec1(app, w, c, s)
    assert r["ok"] and len(r["data"]["recommendations"]) >= 1
    assert all("knowledge_unit_id" in x for x in
               r["data"]["recommendations"])


def test_02_mastered_topic(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="ADAPTIVE_PRACTICE"), sess(
        app, workflow="ADAPTIVE_PRACTICE")
    r = rec1(app, w, c, s, limit=8)
    kinds = {x["action"] for x in r["data"]["recommendations"]}
    assert kinds <= {"REVIEW", "PRACTICE", "REINFORCE", "CHALLENGE",
                     "MAINTAIN"}


def test_03_formula(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="ADAPTIVE_PRACTICE"), sess(
        app, workflow="ADAPTIVE_PRACTICE")
    seed_weak(app)
    r = rec1(app, w, c, s, limit=10)
    assert any(x["unit_kind"] == "formula"
               for x in r["data"]["recommendations"])


def test_04_concept(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="ADAPTIVE_PRACTICE"), sess(
        app, workflow="ADAPTIVE_PRACTICE")
    r = rec1(app, w, c, s, limit=10)
    kinds = {x["unit_kind"] for x in r["data"]["recommendations"]}
    assert kinds <= {"topic", "section", "concept", "formula"}


def test_05_error_driven(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="ADAPTIVE_PRACTICE"), sess(
        app, workflow="ADAPTIVE_PRACTICE")
    seed_weak(app)
    r, g, first = first_generable(app, w, c, s)
    qid = g["data"]["question"]["question_id"]
    a = w.answer(c, g["data"]["session"], qid, "resposta dolenta",
                 attempt_id="att-err-1")
    assert a["data"]["result"]["status"] in ("INCORRECT",
                                             "PARTIALLY_CORRECT")
    r2 = w.next(c, a["data"]["session"])
    assert r2["ok"] and r2["data"]["recommendations"]


def test_06_repeated_recommendation(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="ADAPTIVE_PRACTICE"), sess(
        app, workflow="ADAPTIVE_PRACTICE")
    seed_weak(app)
    a = rec1(app, w, c, s)
    seed_weak(app)
    b = rec1(app, w, c, s)
    assert ([x["knowledge_unit_id"] for x in a["data"]["recommendations"]] ==
            [x["knowledge_unit_id"] for x in b["data"]["recommendations"]])


def test_07_blank_answer(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="ADAPTIVE_PRACTICE"), sess(
        app, workflow="ADAPTIVE_PRACTICE")
    seed_weak(app)
    r, g, first = first_generable(app, w, c, s)
    qid = g["data"]["question"]["question_id"]
    out = w.answer(c, g["data"]["session"], qid, "")
    assert out["data"]["result"]["status"] == "NO_ANSWER"


def test_08_correction_recorded(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="ADAPTIVE_PRACTICE"), sess(
        app, workflow="ADAPTIVE_PRACTICE")
    seed_weak(app)
    r, g, first = first_generable(app, w, c, s)
    qid = g["data"]["question"]["question_id"]
    out = w.answer(c, g["data"]["session"], qid, "V",
                   attempt_id="att-c8-1")
    assert out["data"]["result"]["attempt_id"] == "att-c8-1"
    assert out["data"]["result"]["status"] in (
        "CORRECT", "PARTIALLY_CORRECT", "INCORRECT", "NO_ANSWER")


def test_09_mastery_recorded(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="ADAPTIVE_PRACTICE"), sess(
        app, workflow="ADAPTIVE_PRACTICE")
    seed_weak(app)
    r, g, first = first_generable(app, w, c, s)
    qid = g["data"]["question"]["question_id"]
    out = w.answer(c, g["data"]["session"], qid, "V",
                   attempt_id="att-c9-1")
    assert out["data"]["result"]["mastery"]
    units = [u["unit"] for u in out["data"]["result"]["mastery"]]
    got = w.result(c, out["data"]["session"], units)
    assert got["data"]["mastery"]


def test_10_next_recommendation(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="ADAPTIVE_PRACTICE"), sess(
        app, workflow="ADAPTIVE_PRACTICE")
    seed_weak(app)
    r1 = [x["knowledge_unit_id"] for x in
          rec1(app, w, c, s)["data"]["recommendations"]]
    r2 = [x["knowledge_unit_id"] for x in
          w.next(c, s)["data"]["recommendations"]]
    assert r1 == r2


def test_11_deterministic_repeat(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="ADAPTIVE_PRACTICE"), sess(
        app, workflow="ADAPTIVE_PRACTICE")
    seed_weak(app)
    r, a, first = first_generable(app, w, c, s)
    b = w.generate(c, a["data"]["session"], first, seed=7)
    assert (a["data"]["question"]["question_id"] ==
            b["data"]["question"]["question_id"])


def test_12_restart(tmp_path):
    import json
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="ADAPTIVE_PRACTICE"), sess(
        app, workflow="ADAPTIVE_PRACTICE", nonce="rr")
    seed_weak(app)
    r = rec1(app, w, c, s)
    from app.application.session import ApplicationSession
    s2 = ApplicationSession.from_dict(json.loads(json.dumps(s.to_dict())))
    seed_weak(app)
    r2 = rec1(app, w, c, s2)
    assert ([x["knowledge_unit_id"] for x in r["data"]["recommendations"]] ==
            [x["knowledge_unit_id"] for x in r2["data"]["recommendations"]])


def test_13_no_adaptive_decisions_in_app(tmp_path):
    import re
    src = (Path(__file__).parent.parent.parent / "app" / "application"
           / "adaptive.py").read_text(encoding="utf-8")
    for bad in ("PriorityCalculator(", "DifficultySelector(",
                "RecommendationBuilder(", "LearningPathSelector(",
                "spacing.", "priority =", "difficulty ="):
        assert bad not in src, bad


def test_14_cross_student_denied(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="ADAPTIVE_PRACTICE"), sess(
        app, workflow="ADAPTIVE_PRACTICE")
    seed_weak(app)
    r = rec1(app, w, c, s)
    c2 = ctx(app, student="alu-2", workflow="ADAPTIVE_PRACTICE")
    with pytest.raises(AppError) as e:
        w.generate(c2, r["data"]["session"],
                   r["data"]["recommendations"][0])
    assert e.value.code == "NOT_FOUND"


def test_15_invalid_item(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="ADAPTIVE_PRACTICE"), sess(
        app, workflow="ADAPTIVE_PRACTICE")
    with pytest.raises(AppError):
        w.generate(c, s, {"nope": True})


def test_16_ungeneratable_fails_loud(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="ADAPTIVE_PRACTICE"), sess(
        app, workflow="ADAPTIVE_PRACTICE")
    seed_weak(app)
    r = rec1(app, w, c, s)
    forms = [x for x in r["data"]["recommendations"]
             if x["unit_kind"] == "formula"]
    assert forms
    with pytest.raises(AppError) as e:
        w.generate(c, r["data"]["session"], forms[0], seed=7)
    assert e.value.code == "GENERATION_ERROR"

def test_17_mode_study_practice_recovery(tmp_path):
    from app.adaptive.modes import MODES
    assert MODES == ("STUDY", "PRACTICE", "RECOVERY", "EXAM")
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="ADAPTIVE_PRACTICE"), sess(
        app, workflow="ADAPTIVE_PRACTICE")
    seed_weak(app)
    for mode, code in (("STUDY", "mode_study"),
                       ("PRACTICE", "mode_practice"),
                       ("RECOVERY", "mode_recovery")):
        r = rec1(app, w, c, s, mode=mode)
        assert r["ok"] and r["data"]["recommendations"]
        assert all(code in x.get("reasons", [])
                   for x in r["data"]["recommendations"]), mode


def test_18_mode_invalid_rejected(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="ADAPTIVE_PRACTICE"), sess(
        app, workflow="ADAPTIVE_PRACTICE")
    with pytest.raises(AppError) as e:
        rec1(app, w, c, s, mode="NOPE")
    assert e.value.code == "VALIDATION_ERROR"
    with pytest.raises(AppError) as e:
        w.next(c, s, mode="EXAM")
    assert e.value.code == "VALIDATION_ERROR"


def test_19_mode_next_passthrough(tmp_path):
    app, w = wf(tmp_path)
    c, s = ctx(app, workflow="ADAPTIVE_PRACTICE"), sess(
        app, workflow="ADAPTIVE_PRACTICE")
    seed_weak(app)
    a = w.next(c, s, mode="STUDY")
    b = w.next(c, s, mode="PRACTICE")
    assert a["ok"] and b["ok"]
    assert all("mode_study" in x.get("reasons", [])
               for x in a["data"]["recommendations"])
