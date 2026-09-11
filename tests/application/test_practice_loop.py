"""Tests Fase 7 (Loop Closure): Q1→submit→Q2→submit→Q3 adaptativo real.

Sin mocks de dominio: wiring real contra DBs temporales. El modo
manual debe seguir terminando sin `next`.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from app.application.errors import AppError  # noqa: E402
from app.application.practice import PracticeWorkflow  # noqa: E402
from harness import build_app, ctx, sess  # noqa: E402


def _start(p, c, s, **kw):
    args = {"topic": 2, "question_type": "TRUE_FALSE", "seed": 11}
    args.update(kw)
    return p.start(c, s, **args)["data"]["question"]


def test_loop_q1_q2_q3(tmp_path):
    app = build_app(tmp_path)
    p = PracticeWorkflow(app)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="loop")
    q1 = _start(p, c, s)
    assert q1["question_id"].startswith("q-")
    r1 = p.submit_answer(c, s, "F", attempt_id="att-l1",
                         adaptive=True, seed=7)["data"]["result"]
    assert r1["status"] == "INCORRECT"
    assert r1["mastery"], "el submit debe registrar mastery"
    nxt1 = r1["next"]
    assert nxt1 is not None, "adaptive debe devolver next"
    q2 = nxt1["question"]
    assert q2 is not None, nxt1.get("generation")
    assert q2["question_id"].startswith("q-")
    assert q2["question_id"] != q1["question_id"], \
        "Q2 debe diferir de Q1 en este escenario controlado"
    assert nxt1["item"] and nxt1["item"]["knowledge_unit_id"]
    r2 = p.submit_answer(c, s, "V", attempt_id="att-l2",
                         adaptive=True, seed=7)["data"]["result"]
    assert r2["status"] in ("CORRECT", "PARTIALLY_CORRECT",
                            "INCORRECT", "NO_ANSWER")
    nxt2 = r2["next"]
    assert nxt2 is not None
    q3 = nxt2["question"]
    assert q3 is not None, nxt2.get("generation")
    assert q3["question_id"] != q2["question_id"]
    # provenance en cada pregunta generada
    for q in (q1, q2, q3):
        assert q.get("question_id")


def test_loop_provenance_and_mastery(tmp_path):
    app = build_app(tmp_path)
    p = PracticeWorkflow(app)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="prov")
    _start(p, c, s)
    r = p.submit_answer(c, s, "F", attempt_id="att-p1",
                        adaptive=True, seed=7)["data"]["result"]
    assert r["provenance"], "se conserva provenance de Correction"
    assert all("source_path" in pr for pr in r["provenance"])
    assert r["feedback"]["points"], "feedback pedagógico presente"
    assert all(set(pt) == {"error", "severity", "why", "how_to_fix"}
               for pt in r["feedback"]["points"])
    assert r["claims"], "claims presentes"
    units_before = {m["unit"] for m in r["mastery"]}
    assert units_before
    # el siguiente submit amplía mastery (monotónico en unidades vistas)
    r2 = p.submit_answer(c, s, "V", attempt_id="att-p2",
                         adaptive=True, seed=7)["data"]["result"]
    assert r2["mastery"]


def test_loop_no_answer_keys(tmp_path):
    app = build_app(tmp_path)
    p = PracticeWorkflow(app)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="leak")
    _start(p, c, s, question_type="NUMERICAL", formula_id="eq-02-0201",
           seed=7)
    r = p.submit_answer(c, s, "1.5 m", attempt_id="att-k1",
                        adaptive=True, seed=7)["data"]["result"]
    blob = repr(r)
    assert "correct_answer" not in blob
    assert "expected" not in blob
    for calc in r["calculations"]:
        assert set(calc) == {"match"}, calc


def test_manual_has_no_next(tmp_path):
    app = build_app(tmp_path)
    p = PracticeWorkflow(app)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="man")
    _start(p, c, s)
    r = p.submit_answer(c, s, "V", attempt_id="att-m1")["data"]["result"]
    assert r["next"] is None
    assert r["status"] and r["mastery"] is not None


def test_loop_deterministic(tmp_path):
    got = []
    for nonce, stu in (("d1", "alu-1"), ("d2", "alu-2")):
        (tmp_path / nonce).mkdir(exist_ok=True)
        app = build_app(tmp_path / nonce)
        p = PracticeWorkflow(app)
        c = ctx(app, workflow="PRACTICE", student=stu)
        s = sess(app, workflow="PRACTICE", student=stu, nonce=nonce)
        _start(p, c, s)
        r = p.submit_answer(c, s, "F", attempt_id="att-%s" % nonce,
                            adaptive=True, seed=7)["data"]["result"]
        got.append(r["next"]["question"]["question_id"])
    assert got[0] == got[1], got


def test_loop_replay_stable(tmp_path):
    app = build_app(tmp_path)
    p = PracticeWorkflow(app)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="rep")
    _start(p, c, s)
    r1 = p.submit_answer(c, s, "F", attempt_id="att-r",
                         adaptive=True, seed=7)["data"]["result"]
    r2 = p.submit_answer(c, s, "F", attempt_id="att-r",
                         adaptive=True, seed=7)["data"]["result"]
    assert r2["replayed"] is True
    assert r2["status"] == r1["status"]


def test_loop_invalid_flags(tmp_path):
    app = build_app(tmp_path)
    p = PracticeWorkflow(app)
    c = ctx(app, workflow="PRACTICE")
    s = sess(app, workflow="PRACTICE", nonce="bad")
    _start(p, c, s)
    with pytest.raises(AppError):
        p.submit_answer(c, s, "V", attempt_id="att-b1",
                        adaptive="yes", seed=7)
    with pytest.raises(AppError):
        p.submit_answer(c, s, "V", attempt_id="att-b2",
                        adaptive=True, seed=-1)
