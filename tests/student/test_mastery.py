"""Tests de mastery/memory (§140: 21,22,23 + adversarial + metricas §87).

Estudiantes sinteticos (ids 'synth-*'), jamas reales (§85). Determinismo
total: sin LLM, sin randomness.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.student import mastery as MAS  # noqa: E402
from app.student import memory as MEM  # noqa: E402
from app.student import policy  # noqa: E402
from app.student.service import StudentService  # noqa: E402
from app.student.store import StudentStore  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
GENDB = str(ROOT / "data" / "generated" / "questions.sqlite")


@pytest.fixture()
def svc(tmp_path):
    return StudentService(KB, GENDB, str(tmp_path / "student.sqlite"))


def _feed(svc, sid, seq, qid="q-7c52a0995094"):
    """Alimenta respuestas V/F: True=correcta ('V' si la pregunta es V...).

    Para determinismo se usa la respuesta correcta/incorrecta literal.
    """
    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % GENDB, uri=True)
    try:
        correct = con.execute("SELECT body_json FROM questions WHERE question_id=?",
                              (qid,)).fetchone()
    finally:
        con.close()
    import json as _j
    ca = _j.loads(correct[0])["correct_answer"]
    outs = []
    for i, good in enumerate(seq):
        ans = ca if good else ("F" if ca == "V" else "V")
        outs.append(svc.submit(sid, qid, ans, attempt_id="att-%s-%d" % (sid, i)))
    return outs


# Test 21: mastery determinista (misma secuencia, dos estudiantes -> igual).
def test_21_mastery_deterministic(svc):
    _feed(svc, "synth-a", [True, False, True])
    _feed(svc, "synth-b", [True, False, True])
    a = svc.get_mastery("synth-a", "topic:T02")
    b = svc.get_mastery("synth-b", "topic:T02")
    assert a is not None and b is not None
    assert a["score"] == b["score"] and a["attempt_count"] == b["attempt_count"] == 3


# Test 22: replay == estado almacenado (§116).
def test_22_mastery_replay(svc):
    _feed(svc, "synth-r", [True, True, False, True])
    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % svc.store.path, uri=True)
    try:
        rows = con.execute("SELECT * FROM mastery_events WHERE student_id=? "
                           "AND knowledge_unit_id LIKE 'topic:%'",
                           ("synth-r",)).fetchall()
        cols = [d[0] for d in con.execute("SELECT * FROM mastery_events LIMIT 0").description]
    finally:
        con.close()
    from app.student.models import MasteryEvent
    evs = []
    for r in rows:
        d = dict(zip(cols, r))
        d["evidence"] = json.loads(d.pop("evidence_json"))
        evs.append(MasteryEvent(**d))
    rep = MAS.replay(evs)
    stored = svc.get_mastery("synth-r", "topic:T02")
    assert rep is not None and stored is not None
    assert abs(rep.score - stored["score"]) < 1e-9
    assert rep.attempt_count == stored["attempt_count"]


# 1 acierto no da MASTERED ni confianza alta (§51, §124).
def test_single_correct_not_mastered(svc):
    _feed(svc, "synth-1", [True])
    m = svc.get_topic_mastery("synth-1", 2)
    assert m["score"] > 0
    st = svc.get_mastery("synth-1", "topic:T02")
    assert st["status"] != "MASTERED"
    assert st["confidence"] < 0.5


# Alternating + many wrong/correct coherentes con la politica.
@pytest.mark.parametrize("seq,status", [
    ([True, True, True, True], "MASTERED"),
    ([False, False, False], "AT_RISK"),
    ([True, False, True, False], "DEVELOPING"),
])
def test_adversarial_histories(svc, seq, status, request):
    sid = "synth-%s" % request.node.callspec.id.replace("[", "").replace("]", "")
    _feed(svc, sid, seq)
    assert svc.get_mastery(sid, "topic:T02")["status"] == status


def test_repeated_error_profile(svc):
    _feed(svc, "synth-err", [False, False, False])
    prof = svc.get_error_profile("synth-err")
    assert sum(prof.values()) >= 3
    assert svc.get_mastery("synth-err", "topic:T02")["status"] == "AT_RISK"


def test_recency_keeps_history(svc):
    _feed(svc, "synth-rec", [True] * 6 + [False])
    m = svc.get_mastery("synth-rec", "topic:T02")
    assert m["attempt_count"] == 7 and m["score"] < 1.0 and m["score"] > 0.5


def test_correct_formula_wrong_calc_root_cause(svc):
    out = svc.submit("synth-rd", "q-425eb5c03f2a", "999999.0", attempt_id="att-synth-rd-0")
    errs = [e["error_type"] for e in out["correction"]["detected_errors"]]
    assert "ARITHMETIC_ERROR" in errs or "WRONG_FINAL_RESULT" in errs


def test_memory_provenance(svc):
    _feed(svc, "synth-mem", [False, False, False, True])
    mems = svc.get_memory("synth-mem")
    assert mems
    for m in mems:
        assert m["evidence_count"] >= 1 and m["attempt_ids"]
        assert m["kind"] == "PERFORMANCE"


def test_memory_insufficient_evidence(svc):
    _feed(svc, "synth-thin", [True])
    mems = svc.get_memory("synth-thin")
    assert all(m["evidence_count"] >= 1 for m in mems)


def test_manual_memory_rejected():
    ok, _ = MEM.reject_manual_memory()
    assert ok is False


def test_no_psychological_labels(svc):
    _feed(svc, "synth-psy", [False, False])
    for m in svc.get_memory("synth-psy"):
        low = m["text"].lower()
        for bad in ["malo en", "problemas de atención", "inteligencia", "motivación",
                    "vago", "tonto"]:
            assert bad not in low


def test_review_queue_and_override(svc):
    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % GENDB, uri=True)
    try:
        ca = json.loads(con.execute(
            "SELECT body_json FROM questions WHERE question_id=?",
            ("q-7c52a0995094",)).fetchone()[0])["correct_answer"]
    finally:
        con.close()
    svc.submit("synth-rev0", "q-7c52a0995094", ca, attempt_id="att-synth-rev0-0")
    rid = svc.add_review("att-synth-rev0-0", "respuesta ambigua")
    assert rid.startswith("rev-")
    out = svc.submit("synth-rev", "q-7c52a0995094", ca, attempt_id="att-synth-rev-0")
    assert out["correction"]["status"] in ("CORRECT", "PARTIALLY_CORRECT")
    reg = svc.regrade("att-synth-rev-0", reason="manual review", reviewer="tutor")
    assert reg["version"] == 2
    reg2 = svc.regrade("att-synth-rev-0", reason="bug fix", reviewer="tutor")
    assert reg2["version"] == 3


def _correct_answer(qid="q-7c52a0995094"):
    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % GENDB, uri=True)
    try:
        return json.loads(con.execute(
            "SELECT body_json FROM questions WHERE question_id=?", (qid,)).fetchone()[0]
        )["correct_answer"]
    finally:
        con.close()


def test_duplicate_attempt_idempotent(svc):
    ca = _correct_answer()
    a = svc.submit("synth-dup", "q-7c52a0995094", ca, attempt_id="att-dup-1")
    b = svc.submit("synth-dup", "q-7c52a0995094", ca, attempt_id="att-dup-1")
    assert b["replayed"] is True
    assert a["correction"]["correction_id"] == b["correction"]["correction_id"]
    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % svc.store.path, uri=True)
    try:
        n = con.execute("SELECT COUNT(*) FROM mastery_events WHERE attempt_id=?",
                        ("att-dup-1",)).fetchone()[0]
    finally:
        con.close()
    assert n <= 8  # unidades por intento, sin duplicar eventos


def test_transaction_rollback(svc):
    import sqlite3
    try:
        svc.submit("synth-rb", "q-INEXISTENTE", "x", attempt_id="att-rb-1")
        assert False, "deberia fallar"
    except KeyError:
        pass
    con = sqlite3.connect("file:%s?mode=ro" % svc.store.path, uri=True)
    try:
        n = con.execute("SELECT COUNT(*) FROM attempts WHERE attempt_id=?",
                        ("att-rb-1",)).fetchone()[0]
    finally:
        con.close()
    assert n == 0


def test_aggregation_topic(svc):
    _feed(svc, "synth-agg", [True, False])
    agg = svc.get_topic_mastery("synth-agg", 2)
    assert agg["attempt_count"] >= 2 and 0.0 <= agg["score"] <= 1.0


def test_no_orphans(svc):
    _feed(svc, "synth-orp", [True, False])
    import sqlite3
    con = sqlite3.connect("file:%s?mode=ro" % svc.store.path, uri=True)
    try:
        assert con.execute("SELECT COUNT(*) FROM corrections WHERE attempt_id NOT IN "
                           "(SELECT attempt_id FROM attempts)").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM mastery_events WHERE student_id NOT IN "
                           "(SELECT student_id FROM students)").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM memories WHERE student_id NOT IN "
                           "(SELECT student_id FROM students)").fetchone()[0] == 0
    finally:
        con.close()


def test_repetition_stable(svc):
    ca = _correct_answer()
    outs = [svc.submit("synth-rep", "q-7c52a0995094", ca, attempt_id="att-rep-%d" % i)
            for i in range(3)]
    scores = [o["correction"]["score"] for o in outs]
    assert scores[0] == scores[1] == scores[2]


def test_mastery_benchmark_file():
    rows = [json.loads(l) for l in
            (ROOT / "data" / "evaluation" / "mastery_benchmark.jsonl").read_text(
                encoding="utf-8").splitlines()]
    assert len(rows) == 12
    for r in rows:
        assert r["expected_status"] in ("UNKNOWN", "EMERGING", "DEVELOPING",
                                        "PROFICIENT", "MASTERED", "AT_RISK")
