"""Benchmark Adaptive Loop Bloque B (determinista, sin LLM en decisiones).

24 casos (L01-L24): spacing, RecommendationBuilder, adaptador a Examiner,
closed-loop con submit real, replay/idempotencia F5, aislamientos.
Las DBs reales (KB, generadas, eval, chunks, manifest) solo se leen:
los hashes lo demuestran. Preguntas generadas y mastery van a DBs
temporales, salvo submits que leen questions generadas reales.

Uso: python3 app/adaptive_loop_benchmark.py [--write] [--out P] [--only M,..]
"""
from __future__ import annotations

import inspect
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.adaptive import exam_adapter as AD  # noqa: E402
from app.adaptive.loop import AdaptiveLoop  # noqa: E402
from app.adaptive.path import LearningPathSelector  # noqa: E402
from app.adaptive.priority import PriorityCalculator  # noqa: E402
from app.adaptive.recommendations import RecommendationBuilder  # noqa: E402
from app.adaptive.spacing import evaluate  # noqa: E402
from app.examiner.store import QuestionStore  # noqa: E402
from app.retrieval.service import RetrievalService  # noqa: E402
from app.student import mastery as MAS  # noqa: E402
from app.student.models import MasteryEvent  # noqa: E402
from app.student.service import StudentService  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
INDEX = str(ROOT / "data" / "index")
GENDB = str(ROOT / "data" / "generated" / "questions.sqlite")
EVALDB = str(ROOT / "data" / "evaluation" / "eval.sqlite")
CHUNKS = str(ROOT / "data" / "processed" / "chunks.jsonl")
MANIFEST = str(ROOT / "data" / "source_manifest.json")
CASES = ROOT / "data" / "evaluation" / "adaptive_loop_benchmark.jsonl"
RESULTS = ROOT / "data" / "evaluation" / "adaptive_loop_results.json"
NOW_DEFAULT = "2026-06-01T12:00:00+00:00"
ADAPTIVE_DIR = ROOT / "app" / "adaptive"

_retriever = None


def load_cases() -> list[dict]:
    out = []
    for line in CASES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _sha(p: str) -> str:
    import hashlib
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _seed(case: dict, tmp: Path, qdb: str = "") -> StudentService:
    sid = case["student"]
    qdb = qdb or str(tmp / "q.sqlite")
    if case.get("questions") and Path(qdb).resolve() == Path(GENDB).resolve():
        raise RuntimeError("las preguntas temporales jamas van a GENDB real")
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
            con.execute(
                "INSERT INTO mastery_states(mastery_id,student_id,"
                "knowledge_unit_id,unit_kind,score,confidence,attempt_count,"
                "correct_count,incorrect_count,last_attempt,last_correct,"
                "error_counts_json,status,policy_version)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("ms-%s-%s" % (sid, uid.replace(":", "-")), sid, uid,
                 uid.split(":")[0], st["score"], st.get("confidence", 0.0),
                 st.get("n", 0), st.get("ok", 0), st.get("bad", 0),
                 st.get("last_attempt", ""), st.get("last_correct", ""),
                 json.dumps(st.get("errors", {}), sort_keys=True),
                 st.get("status", "UNKNOWN"), "mastery-policy-v1"))
        for i, e in enumerate(case.get("events", [])):
            att = "att-%s-%d" % (sid, i)
            ev = {"signal": e["signal"], "root_errors": e.get("roots", []),
                  "all_errors": e.get("all_errors",
                                      e.get("roots", []))}
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


def _engine_for(tmp: Path, store_name: str = "gen.sqlite"):
    global _retriever
    from app.examiner.service import ExaminerEngine
    if _retriever is None:
        _retriever = RetrievalService(KB, INDEX)
    return ExaminerEngine(_retriever, KB, str(tmp / store_name))


def _build(loop: AdaptiveLoop, sid: str, call: dict):
    prios = loop.calc.calculate(sid, limit=10000,
                                unit_kind=call.get("unit_kind"),
                                seed=call.get("seed", 7),
                                now=call.get("now", NOW_DEFAULT))
    path = loop.selector.select(sid, limit=call.get("path_limit",
                                                    call.get("limit", 5)),
                                unit_kind=call.get("unit_kind"),
                                seed=call.get("seed", 7),
                                now=call.get("now", NOW_DEFAULT))
    recs = loop.builder.build(sid, prios, path, limit=call.get("limit", 5),
                              now=call.get("now", NOW_DEFAULT))
    return prios, path, recs


def run_case(case: dict, tmp: Path) -> tuple[bool, dict]:
    method = case["method"]
    fails: list[str] = []
    detail: dict = {"case_id": case["case_id"]}
    if method == "static":
        detail["result"] = _static_check()
        _check(detail["result"]["llm_hits"] == 0,
               "tokens LLM en adaptativo: %r"
               % detail["result"]["hits"], fails)
        _check(not detail["result"]["provider_params"],
               "params proveedor: %r"
               % detail["result"]["provider_params"], fails)
        return (not fails, {**detail, "fails": fails})
    if method in ("isolation_kb", "isolation_eval"):
        return _run_isolation(case, tmp)
    if method == "isolation_students":
        return _run_student_isolation(case, tmp)
    if method == "idempotency":
        return _run_idempotency(case, tmp)
    if method == "replay":
        return _run_replay(case, tmp)
    if method == "idempotency":
        return _run_idempotency(case, tmp)
    if method == "replay":
        return _run_replay(case, tmp)
    if method in ("loop_submit", "idempotency", "isolation_students"):
        # Copia de GENDB: los submits leen preguntas reales pero las filas
        # temporales (qm-*) jamas tocan la DB generada real.
        import shutil
        gcopy = str(tmp / "g.sqlite")
        shutil.copyfile(GENDB, gcopy)
        svc = _seed(case, tmp, gcopy)
    else:
        svc = _seed(case, tmp, "")
    loop = AdaptiveLoop(svc)
    call = case.get("call", {})
    if method in ("build", "blueprint", "determinism"):
        return _run_build(case, tmp, loop, call, fails, detail)
    if method == "generate":
        return _run_generate(case, tmp, loop, call, fails, detail)
    if method == "loop_submit":
        return _run_loop_submit(case, tmp, loop, call, fails, detail)
    raise ValueError("metodo desconocido: %r" % method)


def _check(cond: bool, msg: str, fails: list[str]) -> None:
    if not cond:
        fails.append(msg)


def _static_check() -> dict:
    import re
    tokens = ("LLMProvider", "Gemini", "gemini", "openai", "OpenAI",
              "anthropic", "llm_client", "EmbeddingProvider")
    hits: list[str] = []
    for f in sorted(ADAPTIVE_DIR.glob("*.py")):
        src = f.read_text(encoding="utf-8")
        for t in tokens:
            if re.search(r"\b%s\b" % re.escape(t), src):
                hits.append("%s:%s" % (f.name, t))
    params: list[str] = []
    import app.adaptive.difficulty as _d
    import app.adaptive.loop as _l
    import app.adaptive.path as _p
    import app.adaptive.priority as _pr
    import app.adaptive.recommendations as _r
    import app.adaptive.spacing as _s
    for mod in (_d, _l, _p, _pr, _r, _s):
        for name, obj in vars(mod).items():
            if inspect.isclass(obj) and obj.__module__ == mod.__name__:
                ps = set(inspect.signature(obj.__init__).parameters)
                bad = ps & {"llm", "provider", "model"}
                if bad:
                    params.append("%s.%s:%s" % (mod.__name__, name, sorted(bad)))
    return {"llm_hits": len(hits), "hits": hits, "provider_params": params}


def _run_build(case, tmp, loop, call, fails, detail):
    from app.adaptive.loop import AdaptiveLoop as _AL
    _ = _AL
    if case["method"] == "determinism":
        recs_a = _recs_for(loop, case, call, call["seeds"][0])
        recs_b = _recs_for(loop, case, call, call["seeds"][0])
        recs_c = _recs_for(loop, case, call, call["seeds"][1])
        _check(recs_a == recs_b, "doble ejecucion difiere", fails)
        _check([r["knowledge_unit_id"] for r in recs_a]
               == [r["knowledge_unit_id"] for r in recs_c],
               "seed altera el orden", fails)
        detail["result"] = recs_a
        return (not fails, {**detail, "fails": fails})
    _, _, recs = _build(loop, case["student"], call)
    detail["result"] = [r.to_dict() for r in recs]
    by_id = {r.knowledge_unit_id: r for r in recs}
    expect = case["expect"]
    if "ids" in expect:
        _check([r.knowledge_unit_id for r in recs] == expect["ids"],
               "ruta %r != %r" % ([r.knowledge_unit_id for r in recs],
                                  expect["ids"]), fails)
    for uid, cat in expect.get("categories", {}).items():
        _check(uid in by_id and by_id[uid].spacing_state and
               by_id[uid].reason_codes and
               ("categoria:%d:" % cat) in ";".join(by_id[uid].reason_codes),
               "categoria %s != %d" % (uid, cat), fails)
    for uid, act in expect.get("actions", {}).items():
        _check(uid in by_id and by_id[uid].action == act,
               "accion %s=%r != %r" % (
                   uid, by_id[uid].action if uid in by_id else None, act),
               fails)
    for uid, df in expect.get("difficulties", {}).items():
        _check(uid in by_id and by_id[uid].difficulty == df,
               "dificultad %s=%r != %r" % (
                   uid, by_id[uid].difficulty if uid in by_id else None, df),
               fails)
    for uid, score in expect.get("priorities", {}).items():
        _check(uid in by_id and by_id[uid].priority_score == score,
               "priority %s=%r != %r" % (
                   uid, by_id[uid].priority_score if uid in by_id else None,
                   score), fails)
    if "spacing" in expect:
        svc2 = loop.svc
        for uid, sp in expect["spacing"].items():
            got = evaluate(svc2.get_unit_history(case["student"], uid),
                           now=call.get("now", NOW_DEFAULT)).to_dict()
            for k, v in sp.items():
                _check(got.get(k) == v,
                       "spacing %s.%s=%r != %r" % (uid, k, got.get(k), v),
                       fails)
    for uid, subs in expect.get("reasons_contain", {}).items():
        for s in subs:
            _check(uid in by_id and any(s in r for r in by_id[uid].reason_codes),
                   "reason %r ausente en %s" % (s, uid), fails)
    if "blueprint" in expect:
        for uid, bp_exp in expect["blueprint"].items():
            try:
                bp = AD.to_blueprint(by_id[uid], seed=call.get("seed", 7))
                kw = AD.to_generate_kwargs(by_id[uid],
                                           seed=call.get("seed", 7))
            except Exception as e:  # noqa: BLE001
                fails.append("adapter(%s) lanzo %r" % (uid, e))
                continue
            for k, v in bp_exp.get("kwargs", {}).items():
                _check(kw.get(k) == v,
                       "kwarg %s.%s=%r != %r" % (uid, k, kw.get(k), v), fails)
            for k, v in bp_exp.get("fields", {}).items():
                _check(getattr(bp, k, None) == v,
                       "blueprint %s.%s=%r != %r"
                       % (uid, k, getattr(bp, k, None), v), fails)
    return (not fails, {**detail, "fails": fails})


def _recs_for(loop, case, call, seed):
    c2 = dict(call, seed=seed)
    _, _, recs = _build(loop, case["student"], c2)
    return [r.to_dict() for r in recs]


def _run_generate(case, tmp, loop, call, fails, detail):
    _, _, recs = _build(loop, case["student"], call)
    by_id = {r.knowledge_unit_id: r for r in recs}
    expect = case["expect"]
    _check([r.knowledge_unit_id for r in recs] == expect["ids"],
           "ruta %r != %r" % ([r.knowledge_unit_id for r in recs],
                              expect["ids"]), fails)
    eng = _engine_for(tmp)
    for uid, g in expect.get("generated", {}).items():
        kw = AD.to_generate_kwargs(by_id[uid], seed=call.get("seed", 7))
        for k, v in expect.get("kwargs", {}).get(uid, {}).items():
            _check(kw.get(k) == v,
                   "kwarg %s.%s=%r != %r" % (uid, k, kw.get(k), v), fails)
        q, log = eng.generate(**kw)
        _check(q is not None, "Examiner rechazo %s: %r" % (uid, log), fails)
        if q is None:
            continue
        detail.setdefault("generated", {})[uid] = {
            "question_id": q.question_id,
            "validation": q.validation.status,
            "difficulty": q.difficulty,
            "formula_ids": list(q.formula_ids),
            "section": q.section,
            "correct_answer": q.correct_answer}
        for k, v in g.items():
            if k == "section_prefix":
                got = detail["generated"][uid].get("section")
                _check(isinstance(got, str) and got.startswith(v),
                       "section %r no empieza por %r" % (got, v), fails)
            else:
                got = detail["generated"][uid].get(k)
                _check(got == v, "generated %s.%s=%r != %r"
                       % (uid, k, got, v), fails)
    return (not fails, {**detail, "fails": fails})


def _run_loop_submit(case, tmp, loop, call, fails, detail):
    svc = loop.svc
    sid = case["student"]
    sub = case["submit"]
    unit = case["unit"]
    before = svc.get_mastery(sid, unit)
    out = svc.submit(sid, sub["qid"], sub["answer"],
                     attempt_id=sub["attempt_id"])
    detail["correction_status"] = out["correction"]["status"]
    _check(detail["correction_status"] == case["expect"]["correction_status"],
           "correction %r != %r" % (detail["correction_status"],
                                    case["expect"]["correction_status"]),
           fails)
    after = svc.get_mastery(sid, unit)
    post = {"score": after["score"], "n": after["attempt_count"],
            "ok": after["correct_count"], "bad": after["incorrect_count"],
            "status": after["status"],
            "last_correct_eq_last_attempt": (
                bool(after["last_correct"]) and
                after["last_correct"] == after["last_attempt"])}
    detail["pre_score"] = before["score"] if before else None
    detail["post"] = post
    for k, v in case["expect"].get("post", {}).items():
        _check(post.get(k) == v, "post %s=%r != %r" % (k, post.get(k), v),
               fails)
    if "pre_score" in case["expect"]:
        _check(detail["pre_score"] == case["expect"]["pre_score"],
               "pre_score %r != %r" % (detail["pre_score"],
                                       case["expect"]["pre_score"]), fails)
    now = after["last_attempt"]
    prios = loop.calc.calculate(sid, limit=10000, seed=call.get("seed", 7),
                                now=now)
    path = loop.selector.select(sid, limit=call.get("limit", 3),
                                seed=call.get("seed", 7), now=now)
    recs = loop.builder.build(sid, prios, path, limit=call.get("limit", 3),
                              now=now)
    by_id = {r.knowledge_unit_id: r for r in recs}
    detail["post_ids"] = [r.knowledge_unit_id for r in recs]
    pb = case["expect"].get("post_build", {})
    if "ids" in pb:
        _check(detail["post_ids"] == pb["ids"],
               "post ruta %r != %r" % (detail["post_ids"], pb["ids"]), fails)
    for uid, score in pb.get("priorities", {}).items():
        hit = [p for p in prios if p.knowledge_unit_id == uid]
        _check(hit and hit[0].priority_score == score,
               "post priority %s=%r != %r" % (
                   uid, hit[0].priority_score if hit else None, score), fails)
    for uid, sigs in pb.get("signals", {}).items():
        hit = [p for p in prios if p.knowledge_unit_id == uid]
        _check(hit and list(hit[0].error_signals) == sigs,
               "post signals %s=%r != %r" % (
                   uid, list(hit[0].error_signals) if hit else None, sigs),
               fails)
    for uid, df in pb.get("difficulties", {}).items():
        _check(uid in by_id and by_id[uid].difficulty == df,
               "post dificultad %s=%r != %r" % (
                   uid, by_id[uid].difficulty if uid in by_id else None, df),
               fails)
    for uid, act in pb.get("actions", {}).items():
        _check(uid in by_id and by_id[uid].action == act,
               "post accion %s=%r != %r" % (
                   uid, by_id[uid].action if uid in by_id else None, act),
               fails)
    for uid, sp in pb.get("spacing", {}).items():
        got = evaluate(svc.get_unit_history(sid, uid), now=now).to_dict()
        for k, v in sp.items():
            _check(got.get(k) == v,
                   "post spacing %s.%s=%r != %r" % (uid, k, got.get(k), v),
                   fails)
    return (not fails, {**detail, "fails": fails})


def _run_replay(case, tmp):
    fails: list[str] = []
    svc = _seed(case, tmp)
    sid, unit = case["student"], case["unit"]
    con = sqlite3.connect("file:%s?mode=ro" % svc.store.path, uri=True)
    try:
        cols = [d[0] for d in
                con.execute("SELECT * FROM mastery_events LIMIT 0").description]
        rows = con.execute("SELECT * FROM mastery_events WHERE student_id=? "
                           "AND knowledge_unit_id=?", (sid, unit)).fetchall()
    finally:
        con.close()
    evs = []
    for r in rows:
        d = dict(zip(cols, r))
        d["evidence"] = json.loads(d.pop("evidence_json"))
        evs.append(MasteryEvent(**d))
    rep = MAS.replay(evs)
    stored = svc.get_mastery(sid, unit)
    detail = {"replay": {"score": rep.score,
                         "attempt_count": rep.attempt_count,
                         "correct": rep.correct_count,
                         "incorrect": rep.incorrect_count}}
    for k, v in case["expect"].items():
        _check(detail["replay"].get(k) == v,
               "replay %s=%r != %r" % (k, detail["replay"].get(k), v), fails)
    _check(abs(rep.score - stored["score"]) < 1e-9, "replay != almacenado",
           fails)
    _check(rep.attempt_count == stored["attempt_count"], "n != almacenado",
           fails)
    return (not fails, {"case_id": case["case_id"], **detail, "fails": fails})


def _event_count(svc, sid) -> int:
    con = sqlite3.connect("file:%s?mode=ro" % svc.store.path, uri=True)
    try:
        return con.execute("SELECT COUNT(*) FROM mastery_events WHERE "
                           "student_id=?", (sid,)).fetchone()[0]
    finally:
        con.close()


def _run_idempotency(case, tmp):
    fails: list[str] = []
    import shutil
    gcopy = str(tmp / "g.sqlite")
    shutil.copyfile(GENDB, gcopy)
    svc = _seed(case, tmp, gcopy)
    sid = case["student"]
    sub = case["submit"]
    a = svc.submit(sid, sub["qid"], sub["answer"],
                   attempt_id=sub["attempt_id"])
    n1 = _event_count(svc, sid)
    s1 = svc.get_mastery(sid, case["unit"])["score"]
    b = svc.submit(sid, sub["qid"], sub["answer"],
                   attempt_id=sub["attempt_id"])
    n2 = _event_count(svc, sid)
    s2 = svc.get_mastery(sid, case["unit"])["score"]
    detail = {"replayed": b.get("replayed"),
              "same_correction": a["correction"]["correction_id"]
              == b["correction"]["correction_id"],
              "events_stable": n1 == n2, "score_stable": s1 == s2}
    for k, v in case["expect"].items():
        _check(detail.get(k) == v, "idempotencia %s=%r != %r"
               % (k, detail.get(k), v), fails)
    return (not fails, {"case_id": case["case_id"], **detail, "fails": fails})


def _run_isolation(case, tmp):
    fails: list[str] = []
    targets = ([KB, CHUNKS, MANIFEST] if case["method"] == "isolation_kb"
               else [EVALDB])
    before = {t: _sha(t) for t in targets}
    svc = _seed(case, tmp)
    loop = AdaptiveLoop(svc)
    call = case.get("call", {})
    _, _, recs = _build(loop, case["student"], call)
    if case.get("generate"):
        eng = _engine_for(tmp, "q.sqlite")  # misma qdb del servicio
        kw = AD.to_generate_kwargs(recs[0], seed=call.get("seed", 7))
        q, _ = eng.generate(**kw)
        if q is not None and case.get("submit_generated"):
            svc.submit(case["student"], q.question_id,
                       q.correct_answer or "V",
                       attempt_id="att-%s-iso" % case["student"])
    after = {t: _sha(t) for t in targets}
    detail = {"matches": all(before[t] == after[t] for t in targets),
              "checked": [Path(t).name for t in targets]}
    _check(detail["matches"], "hash cambio: %r" % (
        {Path(t).name: (before[t][:8], after[t][:8]) for t in targets
         if before[t] != after[t]}), fails)
    if case["method"] == "isolation_eval":
        import app.adaptive as _pkg
        bad = [f.name for f in Path(_pkg.__file__).parent.glob("*.py")
               if "eval.sqlite" in f.read_text(encoding="utf-8")]
        detail["no_eval_refs"] = not bad
        _check(detail["no_eval_refs"], "refs a eval.sqlite: %r" % bad, fails)
    return (not fails, {"case_id": case["case_id"], **detail, "fails": fails})


def _run_student_isolation(case, tmp):
    fails: list[str] = []
    import shutil
    gcopy = str(tmp / "g.sqlite")
    shutil.copyfile(GENDB, gcopy)
    svc = _seed(case, tmp, gcopy)
    sub = case["submit"]
    a1 = svc.submit("alu-a", sub["qid"], sub["answer_a"],
                    attempt_id="att-iso-a1")
    b1 = svc.submit("alu-b", sub["qid"], sub["answer_b"],
                    attempt_id="att-iso-b1")
    sa = svc.get_mastery("alu-a", case["unit"])["score"]
    sb = svc.get_mastery("alu-b", case["unit"])["score"]
    a2 = svc.submit("alu-a", sub["qid"], sub["answer_b"],
                    attempt_id="att-iso-a2")
    sb2 = svc.get_mastery("alu-b", case["unit"])["score"]
    nb = len(svc.get_recent_attempts("alu-b", limit=50))
    detail = {"a_score": sa, "b_score": sb, "a_final": svc.get_mastery(
        "alu-a", case["unit"])["score"], "b_stable": sb == sb2,
        "b_attempts": nb}
    _ = (a1, b1, a2)
    for k, v in case["expect"].items():
        _check(detail.get(k) == v, "aislamiento %s=%r != %r"
               % (k, detail.get(k), v), fails)
    return (not fails, {"case_id": case["case_id"], **detail, "fails": fails})


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    only = {m.strip() for m in args.only.split(",") if m.strip()}
    cases = [c for c in load_cases()
             if not only or c["method"] in only]
    print("casos: %d" % len(cases))
    all_ok, details = True, []
    for case in cases:
        with tempfile.TemporaryDirectory(prefix="adaptive-loop-") as td:
            ok, detail = run_case(case, Path(td))
        details.append(detail)
        print(("PASS " if ok else "FAIL ") + case["case_id"] + " "
              + case.get("title", ""))
        for f in detail.get("fails", []):
            print("     - " + f)
        all_ok = all_ok and ok
    out = Path(args.out) if args.out else RESULTS
    if args.write or args.out:
        out.write_text(json.dumps(
            {"policies": ["priority-policy@v1", "difficulty-policy@v1",
                          "spacing-policy@v1"], "cases": details},
            ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        print("resultados en %s" % out)
    print("OK" if all_ok else "FALLOS")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
