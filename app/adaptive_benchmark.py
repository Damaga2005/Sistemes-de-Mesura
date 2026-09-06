"""Benchmark Adaptive Core Bloque A (determinista, sin LLM).

Lee data/evaluation/adaptive_core_benchmark.jsonl, reconstruye cada caso en
DBs temporales (student + questions), ejecuta y compara con lo esperado.
No toca KB, ni eval.sqlite, ni generated/questions.sqlite: solo lecturas.

Uso: python3 app/adaptive_benchmark.py [--write]  (--write actualiza
data/evaluation/adaptive_core_results.json con el detalle verificado).
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.adaptive.difficulty import DifficultySelector  # noqa: E402
from app.adaptive.path import LearningPathSelector  # noqa: E402
from app.adaptive.priority import PriorityCalculator  # noqa: E402
from app.examiner.store import QuestionStore  # noqa: E402
from app.student.service import StudentService  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
CASES = ROOT / "data" / "evaluation" / "adaptive_core_benchmark.jsonl"
RESULTS = ROOT / "data" / "evaluation" / "adaptive_core_results.json"
NOW_DEFAULT = "2026-06-01T12:00:00+00:00"


def load_cases() -> list[dict]:
    out = []
    for line in CASES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _seed(case: dict, tmp: Path) -> StudentService:
    sid = case["student"]
    qdb = str(tmp / "q.sqlite")
    sdb = str(tmp / "s.sqlite")
    QuestionStore(qdb)
    svc = StudentService(KB, qdb, sdb)
    con = svc.store.connect()
    try:
        con.execute("INSERT INTO students(student_id, created_at) VALUES(?,?)",
                    (sid, "2026-01-01T00:00:00+00:00"))
        for q in case.get("questions", []):
            body = {"question_id": q["question_id"], "topic": q["topic"],
                    "section": q.get("section", ""),
                    "type": q.get("type", "NUMERICAL"),
                    "difficulty": q.get("difficulty", "EASY"),
                    "formula_ids": q.get("formulas", []),
                    "concept_terms": q.get("concepts", []),
                    "prompt": "benchmark", "origin": "GENERATED"}
            _insert_question(qdb, q, body)
        for i, e in enumerate(case.get("events", [])):
            att = "att-%s-%d" % (sid, i)
            con.execute(
                "INSERT INTO attempts(attempt_id,student_id,question_id,"
                "question_version,exam_id,answer,created_at)"
                " VALUES(?,?,?,?,?,?,?)",
                (att, sid, e["question_id"], "qt-v1", "", "x",
                 e["created_at"]))
        for st in case.get("states", []):
            uid = st["unit"]
            kind = uid.split(":")[0]
            con.execute(
                "INSERT INTO mastery_states(mastery_id,student_id,"
                "knowledge_unit_id,unit_kind,score,confidence,attempt_count,"
                "correct_count,incorrect_count,last_attempt,last_correct,"
                "error_counts_json,status,policy_version)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("ms-%s-%s" % (sid, uid.replace(":", "-")), sid, uid, kind,
                 st["score"], st.get("confidence", 0.0), st.get("n", 0),
                 st.get("ok", 0), st.get("bad", 0),
                 st.get("last_attempt", ""), st.get("last_correct", ""),
                 json.dumps(st.get("errors", {}), sort_keys=True),
                 st.get("status", "UNKNOWN"), "mastery-policy-v1"))
        for i, e in enumerate(case.get("events", [])):
            att = "att-%s-%d" % (sid, i)
            ev = {"signal": e["signal"], "root_errors": e.get("roots", [])}
            con.execute(
                "INSERT INTO mastery_events(event_id,student_id,question_id,"
                "attempt_id,correction_id,knowledge_unit_id,unit_kind,"
                "old_score,new_score,old_confidence,new_confidence,reason,"
                "evidence_json,policy_version,created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("ev-%s-%d" % (sid, i), sid, e["question_id"], att,
                 "corr-%s-%d" % (sid, i), e["unit"], e["unit"].split(":")[0],
                 0.0, e.get("new_score", 0.0), 0.0,
                 e.get("new_confidence", 0.0), "seed", json.dumps(ev),
                 "mastery-policy-v1", e["created_at"]))
        con.commit()
    finally:
        con.close()
    return svc


def _insert_question(qdb: str, q: dict, body: dict) -> None:
    con = sqlite3.connect(qdb)
    try:
        con.execute(
            "INSERT INTO questions(question_id,fingerprint,topic,section,type,"
            "difficulty,status,prompt,body_json,seed,generator_version,"
            "prompt_version) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (q["question_id"], "fp-" + q["question_id"], q["topic"],
             q.get("section", ""), q.get("type", "NUMERICAL"),
             q.get("difficulty", "EASY"), "VALID", "benchmark",
             json.dumps(body, ensure_ascii=False, sort_keys=True), 7,
             "examiner-4.0", "pv-test"))
        con.commit()
    finally:
        con.close()


def run_case(case: dict, tmp: Path) -> tuple[bool, dict]:
    """Ejecuta un caso. Devuelve (ok, detalle). Lanza AssertionError con
    mensaje explicito ante la primera discrepancia."""
    method = case["method"]
    fails: list[str] = []
    detail: dict = {"case_id": case["case_id"]}
    if method == "difficulty":
        d = DifficultySelector().select(**case["inputs"])
        detail["result"] = d
        _check(d["difficulty"] == case["expect"]["difficulty"],
               "difficulty %r != %r" % (d["difficulty"],
                                        case["expect"]["difficulty"]), fails)
        for r in case["expect"].get("reasons_contain", []):
            _check(any(r in x for x in d["reasons"]),
                   "reason %r ausente en %r" % (r, d["reasons"]), fails)
        return (not fails, {**detail, "fails": fails})
    svc = _seed(case, tmp)
    call = case.get("call", {})
    now = call.get("now", NOW_DEFAULT)
    if method == "calculate":
        prios = PriorityCalculator(svc).calculate(
            case["student"], limit=call.get("limit", 100),
            unit_kind=call.get("unit_kind"), seed=call.get("seed", 7), now=now)
        detail["result"] = [p.to_dict() for p in prios]
        _expect_priorities(prios, case["expect"], fails)
    elif method == "select":
        sel = LearningPathSelector(svc)
        items = sel.select(case["student"], limit=call.get("limit", 5),
                           unit_kind=call.get("unit_kind"),
                           seed=call.get("seed", 7), now=now)
        detail["result"] = [i.to_dict() for i in items]
        _expect_path(sel, items, case["expect"], call.get("seed", 7), fails)
    elif method == "determinism":
        sel = LearningPathSelector(svc)
        a = [i.to_dict() for i in sel.select(
            case["student"], limit=call.get("limit", 8),
            seed=call["seeds"][0], now=now)]
        b = [i.to_dict() for i in sel.select(
            case["student"], limit=call.get("limit", 8),
            seed=call["seeds"][0], now=now)]
        c = [i.to_dict() for i in sel.select(
            case["student"], limit=call.get("limit", 8),
            seed=call["seeds"][1], now=now)]
        _check(a == b, "doble ejecucion difiere", fails)
        _check([x["knowledge_unit_id"] for x in a]
               == [x["knowledge_unit_id"] for x in c],
               "seed altera el orden: %r vs %r" % (
                   [x["knowledge_unit_id"] for x in a],
                   [x["knowledge_unit_id"] for x in c]), fails)
        detail["result"] = a
    else:
        raise ValueError("metodo desconocido: %r" % method)
    return (not fails, {**detail, "fails": fails})


def _check(cond: bool, msg: str, fails: list[str]) -> None:
    if not cond:
        fails.append(msg)


def _expect_priorities(prios, expect: dict, fails: list[str]) -> None:
    got_ids = [p.knowledge_unit_id for p in prios]
    if "order" in expect:
        _check(got_ids[:len(expect["order"])] == expect["order"],
               "orden %r != %r" % (got_ids, expect["order"]), fails)
    if "top" in expect:
        _check(bool(got_ids) and got_ids[0] == expect["top"],
               "top %r != %r" % (got_ids[:1], expect["top"]), fails)
    by_id = {p.knowledge_unit_id: p for p in prios}
    for uid, score in expect.get("scores", {}).items():
        _check(uid in by_id and by_id[uid].priority_score == score,
               "score %s=%r != %r" % (
                   uid, by_id[uid].priority_score if uid in by_id else None,
                   score), fails)
    for uid, act in expect.get("actions", {}).items():
        _check(uid in by_id and by_id[uid].recommended_action == act,
               "accion %s=%r != %r" % (
                   uid, by_id[uid].recommended_action if uid in by_id else None,
                   act), fails)
    for uid, lvl in expect.get("evidence", {}).items():
        _check(uid in by_id and by_id[uid].evidence_level == lvl,
               "evidencia %s=%r != %r" % (
                   uid, by_id[uid].evidence_level if uid in by_id else None,
                   lvl), fails)
    for uid, sigs in expect.get("signals", {}).items():
        _check(uid in by_id and list(by_id[uid].error_signals) == sigs,
               "signals %s=%r != %r" % (
                   uid, list(by_id[uid].error_signals) if uid in by_id else None,
                   sigs), fails)
    for uid, subs in expect.get("reasons_contain", {}).items():
        for s in subs:
            _check(uid in by_id and any(s in r for r in by_id[uid].reasons),
                   "reason %r ausente en %s=%r" % (
                       s, uid, list(by_id[uid].reasons) if uid in by_id else None),
                   fails)
    for uid, subs in expect.get("reasons_absent", {}).items():
        for s in subs:
            _check(uid in by_id and not any(s in r for r in by_id[uid].reasons),
                   "reason %r debio estar ausente en %s" % (s, uid), fails)


def _expect_path(sel, items, expect: dict, seed: int, fails: list[str]) -> None:
    got_ids = [i.knowledge_unit_id for i in items]
    if "ids" in expect:
        _check(got_ids == expect["ids"],
               "ruta %r != %r" % (got_ids, expect["ids"]), fails)
    by_id = {i.knowledge_unit_id: i for i in items}
    for uid, act in expect.get("actions", {}).items():
        _check(uid in by_id and by_id[uid].action == act,
               "accion %s=%r != %r" % (
                   uid, by_id[uid].action if uid in by_id else None, act), fails)
    for uid, df in expect.get("difficulties", {}).items():
        _check(uid in by_id and by_id[uid].difficulty == df,
               "dificultad %s=%r != %r" % (
                   uid, by_id[uid].difficulty if uid in by_id else None, df),
               fails)
    for uid, subs in expect.get("reasons_contain", {}).items():
        for s in subs:
            _check(uid in by_id and any(s in r for r in by_id[uid].reasons),
                   "reason %r ausente en %s" % (s, uid), fails)
    for uid in expect.get("exploration", []):
        _check(uid in by_id and "exploracion_unseen" in by_id[uid].reasons,
               "%s debio ser exploracion" % uid, fails)
    for uid, spec in expect.get("specs", {}).items():
        try:
            got = sel.to_spec(by_id[uid], seed=seed).to_dict()
        except Exception as e:  # noqa: BLE001
            fails.append("to_spec(%s) lanzo %r" % (uid, e))
            continue
        for k, v in spec.items():
            _check(got.get(k) == v,
                   "spec %s.%s=%r != %r" % (uid, k, got.get(k), v), fails)
    if "spec_error_origin" in expect:
        try:
            sel.to_spec(items[0], seed=seed,
                        origin=expect["spec_error_origin"])
            fails.append("origin %r debio rechazarse"
                         % expect["spec_error_origin"])
        except ValueError:
            pass


def main() -> int:
    write = "--write" in sys.argv
    cases = load_cases()
    print("casos: %d" % len(cases))
    all_ok, details = True, []
    for case in cases:
        with tempfile.TemporaryDirectory(prefix="adaptive-bench-") as td:
            ok, detail = run_case(case, Path(td))
        details.append(detail)
        print(("PASS " if ok else "FAIL ") + case["case_id"] + " "
              + case.get("title", ""))
        for f in detail.get("fails", []):
            print("     - " + f)
        all_ok = all_ok and ok
    if write:
        RESULTS.write_text(json.dumps(
            {"policy": "priority-policy@v1+difficulty-policy@v1",
             "cases": details}, ensure_ascii=False, indent=1, sort_keys=True),
            encoding="utf-8")
        print("resultados en %s" % RESULTS)
    print("OK" if all_ok else "FALLOS")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
