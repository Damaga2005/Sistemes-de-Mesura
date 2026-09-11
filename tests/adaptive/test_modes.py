"""Tests Fase 11 Bloque A-D: LearningMode + filtros STUDY/PRACTICE/RECOVERY.

Un solo AdaptiveLoop; los modos son filtros deterministas con fallback.
Sin LLM, DBs temporales.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.adaptive.loop import AdaptiveLoop  # noqa: E402
from app.adaptive.modes import (  # noqa: E402
    MODES,
    apply_mode_filter,
    mode_code,
    validate,
)
from app.student.service import StudentService  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
GENDB = str(ROOT / "data" / "generated" / "questions.sqlite")


def _svc(tmp_path, name="s.sqlite"):
    return StudentService(KB, GENDB, str(tmp_path / name))


def _seed_row(svc, sid, uid, score, n, status, last="", lcorrect="",
              conf=0.5, ok=1, bad=1, errors="{}"):
    con = svc.store.connect()
    try:
        con.execute("INSERT OR IGNORE INTO students(student_id, created_at)"
                    " VALUES(?,?)", (sid, "2026-01-01T00:00:00+00:00"))
        con.execute(
            "INSERT INTO mastery_states(mastery_id,student_id,"
            "knowledge_unit_id,unit_kind,score,confidence,attempt_count,"
            "correct_count,incorrect_count,last_attempt,last_correct,"
            "error_counts_json,status,policy_version)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("ms-" + sid + "-" + uid.replace(":", "-"), sid, uid,
             uid.split(":")[0], score, conf, n, ok, bad, last, lcorrect,
             errors, status, "mastery-policy-v1"))
        con.commit()
    finally:
        con.close()


def _seed_error(svc, sid, key, count=2, severity="MODERATE"):
    con = svc.store.connect()
    try:
        con.execute("INSERT OR IGNORE INTO students(student_id, created_at)"
                    " VALUES(?,?)", (sid, "2026-01-01T00:00:00+00:00"))
        con.execute(
            "INSERT INTO error_memory(student_id,error_key,first_seen,"
            "last_seen,error_count,severity,last_status,last_question_id,"
            "last_attempt_id) VALUES(?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(student_id,error_key) DO UPDATE SET "
            "error_count=excluded.error_count",
            (sid, key, "2026-01-01T00:00:00+00:00",
             "2026-01-02T00:00:00+00:00", count, severity, "INCORRECT",
             "q-seed", "att-seed"))
        con.commit()
    finally:
        con.close()


def _seed_demo(svc, sid):
    _seed_row(svc, sid, "formula:eq-02-0034", 0.2, 3, "EMERGING",
              last="2026-05-01T09:00:00+00:00")
    _seed_row(svc, sid, "topic:T02", 0.1, 2, "EMERGING",
              last="2026-05-01T09:00:00+00:00")


def _recs(tmp_path, sid, mode, seed=7, limit=5):
    svc = _svc(tmp_path)
    loop = AdaptiveLoop(svc)
    return loop.recommend(sid, limit=limit, seed=seed, mode=mode)


def _demo(tmp_path, sid):
    svc = _svc(tmp_path)
    _seed_demo(svc, sid)
    return AdaptiveLoop(svc)


# ---------- Bloque J-1: validación ----------
def test_modes_known():
    assert MODES == ("STUDY", "PRACTICE", "RECOVERY", "EXAM")


def test_validate_ok():
    assert validate("study") == "STUDY"
    assert validate(" PRACTICE ") == "PRACTICE"
    assert validate("Recovery") == "RECOVERY"
    assert validate("EXAM") == "EXAM"


@pytest.mark.parametrize("bad", ["", "NOPE", "123", "STUDY " * 0 + "STUD",
                                 None, 42])
def test_validate_rejects(bad):
    with pytest.raises(ValueError):
        validate(bad)


def test_mode_code():
    assert mode_code("study") == "mode_study"
    assert mode_code("EXAM") == "mode_exam"


# ---------- Bloque J-2: study ----------
def test_study_keeps_only_unseen_or_fallback(tmp_path):
    loop = _demo(tmp_path, "s-study")
    recs = loop.recommend("s-study", limit=5, seed=7, mode="STUDY")
    base = loop.recommend("s-study", limit=5, seed=7, mode="PRACTICE")
    assert recs, "fallback: nunca vacío si practice no lo está"
    assert [r.knowledge_unit_id for r in recs] == \
        [r.knowledge_unit_id for r in base] or all(
            r.knowledge_unit_id not in ("formula:eq-02-0034", "topic:T02")
            for r in recs)
    assert all("mode_study" in r.reason_codes for r in recs)


def test_study_unseen_unit_kept(tmp_path):
    svc = _svc(tmp_path)
    _seed_demo(svc, "s")
    loop = AdaptiveLoop(svc)
    items = loop.recommend("s", limit=10, seed=7, mode="PRACTICE")
    unseen = [i for i in items
              if svc.get_mastery("s", i.knowledge_unit_id) is None]
    if unseen:
        got = loop.recommend("s", limit=10, seed=7, mode="STUDY")
        assert got
        assert all(svc.get_mastery(
            "s", i.knowledge_unit_id) is None for i in got)


# ---------- Bloque J-3: practice intacto ----------
def test_practice_is_default_unchanged(tmp_path):
    loop = _demo(tmp_path, "s-p")
    a = loop.recommend("s-p", limit=5, seed=7, mode="PRACTICE")
    b = loop.recommend("s-p", limit=5, seed=7)
    c = loop.recommend("s-p", limit=5, seed=7, mode="PRACTICE")
    assert [r.knowledge_unit_id for r in a] == \
        [r.knowledge_unit_id for r in b] == \
        [r.knowledge_unit_id for r in c]
    assert all("mode_practice" in r.reason_codes for r in a)


# ---------- Bloque J-4: recovery ----------
def test_recovery_keeps_recurrent_or_fallback(tmp_path):
    svc = _svc(tmp_path)
    _seed_row(svc, "s-r", "formula:eq-02-0034", 0.2, 3, "EMERGING",
              last="2026-05-01T09:00:00+00:00",
              errors='{"UNIT_ERROR": 3}')
    _seed_row(svc, "s-r", "topic:T02", 0.1, 2, "EMERGING",
              last="2026-05-01T09:00:00+00:00")
    _seed_error(svc, "s-r", "UNIT_ERROR", count=2)
    loop = AdaptiveLoop(svc)
    recs = loop.recommend("s-r", limit=5, seed=7, mode="RECOVERY")
    base = loop.recommend("s-r", limit=5, seed=7, mode="PRACTICE")
    assert recs
    if [r.knowledge_unit_id for r in recs] != \
            [r.knowledge_unit_id for r in base]:
        for r in recs:
            m = svc.get_mastery("s-r", r.knowledge_unit_id)
            assert m is not None and "UNIT_ERROR" in (
                m.get("error_counts") or {})
    assert all("mode_recovery" in r.reason_codes for r in recs)


def test_recovery_no_errors_means_fallback(tmp_path):
    loop = _demo(tmp_path, "s-r0")
    recs = loop.recommend("s-r0", limit=5, seed=7, mode="RECOVERY")
    base = loop.recommend("s-r0", limit=5, seed=7, mode="PRACTICE")
    assert [r.knowledge_unit_id for r in recs] == \
        [r.knowledge_unit_id for r in base]


# ---------- Bloque J-5: exam rechazado ----------
def test_exam_mode_rejected_in_recommend(tmp_path):
    svc = _svc(tmp_path)
    with pytest.raises(ValueError, match="closed blueprint"):
        AdaptiveLoop(svc).recommend("s", mode="EXAM")


def test_exam_mode_rejected_in_step(tmp_path):
    svc = _svc(tmp_path)
    with pytest.raises(ValueError, match="closed blueprint"):
        AdaptiveLoop(svc).step("s", object(), mode="EXAM")


# ---------- determinismo / orden ----------
def test_mode_filter_preserves_order_and_limit(tmp_path):
    loop = _demo(tmp_path, "s-o")
    recs = loop.recommend("s-o", limit=3, seed=7, mode="STUDY")
    base = loop.recommend("s-o", limit=3, seed=7, mode="PRACTICE")
    assert len(recs) <= 3
    ids = [r.knowledge_unit_id for r in base]
    assert [r.knowledge_unit_id for r in recs] == \
        [i for i in ids if i in {r.knowledge_unit_id for r in recs}]
    again = loop.recommend("s-o", limit=3, seed=7, mode="STUDY")
    assert [r.knowledge_unit_id for r in again] == \
        [r.knowledge_unit_id for r in recs]


def test_apply_mode_filter_practice_passthrough(tmp_path):
    svc = _svc(tmp_path)
    items = AdaptiveLoop(svc).recommend("s", limit=3, seed=7)
    assert apply_mode_filter(items, svc, "s", "PRACTICE") == items
