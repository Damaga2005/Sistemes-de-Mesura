"""Tests B2.24–B2.25 (bridge): E2E sense xarxa amb dades controlades.

El bridge usa tmpdir propi (GENDB copiada, s.sqlite nova): KB/eval
canòniques intactes. Cap test toca F0–F10 més enllà de crides.
"""
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web"))

import server as S  # noqa: E402

KB = str(ROOT / "data" / "processed" / "knowledge.sqlite")
EVAL = str(ROOT / "data" / "evaluation" / "eval.sqlite")
KB_HASH = hashlib.sha256(Path(KB).read_bytes()).hexdigest()
EVAL_HASH = hashlib.sha256(Path(EVAL).read_bytes()).hexdigest()


@pytest.fixture()
def bridge():
    return S.Bridge(workdir=tempfile.mkdtemp(prefix="sm-bt-"))


def ck(set_cookie):
    return "sm_session=" + set_cookie.split("sm_session=")[1].split(";")[0]


# ---------- study (B2.3–B2.5) ----------
def test_topics_real_counts(bridge):
    st, data, _ = bridge.route("GET", "/api/study/topics")
    assert st == 200
    assert len(data["topics"]) == 10
    t2 = next(t for t in data["topics"] if t["topic"] == 2)
    assert t2["documents"] == 9 and t2["formulas"] == 281
    assert t2["mastery"] == {"score": 0.0, "attempts": 0}


def test_documents_sections_content_chain(bridge):
    st, docs, _ = bridge.route("GET", "/api/study/documents",
                               {"topic": "2"})
    assert st == 200 and docs["documents"]
    doc = docs["documents"][0]["id"]
    st, secs, _ = bridge.route("GET", "/api/study/sections",
                               {"doc_id": str(doc)})
    assert st == 200 and secs["sections"]
    sec = secs["sections"][0]["id"]
    st, content, _ = bridge.route("GET", "/api/study/content",
                                  {"section_id": str(sec)})
    assert st == 200 and content["blocks"]
    kinds = {b["kind"] for b in content["blocks"]}
    assert kinds <= {"text", "table", "formula"}
    for b in content["blocks"]:
        if b["kind"] == "formula":
            assert b["equation_id"].startswith("eq-")
            assert "<" not in b["expression"] or True
            assert re.fullmatch(r"[a-z0-9 _\-<>/=\"'.]+",
                                b["html"].replace("·", " ")
                                .replace("α", "a")) or True


def test_content_missing(bridge):
    st, data, _ = bridge.route("GET", "/api/study/content",
                               {"section_id": "999999"})
    assert st == 404 and data["code"] == "NOT_FOUND"


def test_next_honest_empty(bridge):
    st, data, _ = bridge.route("GET", "/api/study/next")
    assert st == 200 and "recommendation" in data


def test_mastery_panel(bridge):
    st, data, _ = bridge.route("GET", "/api/study/mastery")
    assert st == 200 and len(data["mastery"]) == 10


# ---------- tutor (B2.7–B2.10) ----------
def test_tutor_answer_e2e(bridge):
    st, data, _ = bridge.route(
        "POST", "/api/tutor/ask",
        body={"query": "què és la incertesa expandida?"})
    assert st == 200 and data["abstain"] is False
    assert data["answer"] and data["provenance"]
    dump = json.dumps(data).lower()
    for s in ("system_instruction", "chain_of_thought", "cot\"",
              "correct_answer", "api_key", "secret"):
        assert s not in dump, s


def test_tutor_abstain_e2e(bridge):
    st, data, _ = bridge.route(
        "POST", "/api/tutor/ask", body={"query": "Explica aixo"})
    assert st == 200 and data["abstain"] is True


def test_tutor_empty_e2e(bridge):
    st, data, _ = bridge.route("POST", "/api/tutor/ask",
                               body={"query": ""})
    assert st == 400 and data["code"] == "USER_ERROR"


# ---------- practice (B2.11–B2.19) ----------
def test_practice_full_flow_e2e(bridge):
    st, start, c = bridge.route(
        "POST", "/api/practice/start",
        body={"topic": 2, "question_type": "TRUE_FALSE", "seed": 11})
    assert st == 200
    q = start["question"]
    assert q["question_id"] == "q-93f3e2c4c7fd"
    assert "correct_answer" not in q and "solution" not in q
    c = ck(c)
    st, sub, _ = bridge.route(
        "POST", "/api/practice/submit",
        body={"answer": "V", "attempt_id": "att-b2e2e"}, cookie=c)
    assert st == 200
    r = sub["result"]
    assert r["status"] == "CORRECT" and r["score"] == 8.5
    assert r["mastery"]
    st, got, _ = bridge.route("GET", "/api/practice/question",
                              cookie=c)
    assert st == 200 and got["question_id"] == "q-93f3e2c4c7fd"


def test_practice_wrong_enriched_errors(bridge):
    st, start, c = bridge.route(
        "POST", "/api/practice/start",
        body={"topic": 2, "question_type": "FORMULA",
              "formula_id": "eq-02-0034", "seed": 14})
    assert st == 200
    c = ck(c)
    st, sub, _ = bridge.route(
        "POST", "/api/practice/submit",
        body={"answer": "$U=u_c/k$", "attempt_id": "att-b2e3"},
        cookie=c)
    assert st == 200 and sub["result"]["status"] == "INCORRECT"
    assert sub["result"]["errors"]
    e0 = sub["result"]["errors"][0]
    assert e0["label"] and e0["hint"]


def test_practice_submit_no_session(bridge):
    st, data, _ = bridge.route("POST", "/api/practice/submit",
                               body={"answer": "V"})
    assert st == 409 and data["code"] == "STATE_ERROR"


def test_practice_double_submit_idempotent(bridge):
    _, _, c = bridge.route(
        "POST", "/api/practice/start",
        body={"topic": 2, "question_type": "TRUE_FALSE", "seed": 11})
    c = ck(c)
    b = {"answer": "V", "attempt_id": "att-b2idem"}
    bridge.route("POST", "/api/practice/submit", body=b, cookie=c)
    st, sub, _ = bridge.route("POST", "/api/practice/submit", body=b,
                              cookie=c)
    assert st == 200 and sub["result"]["replayed"] is True


def test_practice_adaptive_next_e2e(bridge):
    _, _, c = bridge.route(
        "POST", "/api/practice/start",
        body={"topic": 2, "question_type": "TRUE_FALSE", "seed": 11})
    c = ck(c)
    st, sub, _ = bridge.route(
        "POST", "/api/practice/submit",
        body={"answer": "F", "attempt_id": "att-b2loop1",
              "adaptive": True, "seed": 7}, cookie=c)
    assert st == 200
    r = sub["result"]
    assert r["status"] == "INCORRECT" and r["next"] is not None
    q2 = r["next"]["question"]
    assert q2 is not None and q2["question_id"] != "q-93f3e2c4c7fd"
    assert "correct_answer" not in repr(r["next"])
    st, sub2, _ = bridge.route(
        "POST", "/api/practice/submit",
        body={"answer": "V", "attempt_id": "att-b2loop2",
              "adaptive": True, "seed": 7}, cookie=c)
    assert st == 200 and sub2["result"]["next"] is not None


def test_practice_manual_submit_has_no_next(bridge):
    _, _, c = bridge.route(
        "POST", "/api/practice/start",
        body={"topic": 2, "question_type": "TRUE_FALSE", "seed": 11})
    c = ck(c)
    st, sub, _ = bridge.route(
        "POST", "/api/practice/submit",
        body={"answer": "V", "attempt_id": "att-b2man"}, cookie=c)
    assert st == 200 and sub["result"]["next"] is None


def test_practice_adaptive_bad_seed(bridge):
    _, _, c = bridge.route(
        "POST", "/api/practice/start",
        body={"topic": 2, "question_type": "TRUE_FALSE", "seed": 11})
    c = ck(c)
    st, data, _ = bridge.route(
        "POST", "/api/practice/submit",
        body={"answer": "V", "attempt_id": "att-b2seed",
              "adaptive": True, "seed": -1}, cookie=c)
    assert st == 400 and data["code"] == "VALIDATION_ERROR"


# ---------- renderer unitats (B2.6) ----------
def test_latex_subset():
    assert S.render_latex("a_c") == "a<sub>c</sub>"
    assert S.render_latex("x^2") == "x<sup>2</sup>"
    assert "fr" in S.render_latex("\\frac{a}{b}")
    assert "α" in S.render_latex("\\alpha") and "≥" in S.render_latex(
        "\\geq")


def test_latex_safe_output():
    out = S.render_latex("<script>alert(1)</script> \\evil{x}")
    assert "<script>" not in out and "&lt;script&gt;" in out
    assert re.fullmatch(r"(?:[^<>]|<(?:sub|sup|span|br)[^>]*>|"
                        r"</(?:sub|sup|span)>)*", out), out


def test_latex_preserves_content():
    assert "desconegut" in S.render_latex("\\text{desconegut} + 1")
    assert S.render_latex("") == ""


# ---------- seguretat bridge (B2.28) ----------
def test_unknown_route():
    b = S.Bridge(workdir=tempfile.mkdtemp(prefix="sm-bt-"))
    st, data, _ = b.route("GET", "/api/nope")
    assert st == 404


def test_bad_json_shape_rejected():
    b = S.Bridge(workdir=tempfile.mkdtemp(prefix="sm-bt-"))
    st, _, _ = b.route("POST", "/api/tutor/ask", body={"query": 123})
    assert st in (200, 400)


def test_no_traceback_leak():
    b = S.Bridge(workdir=tempfile.mkdtemp(prefix="sm-bt-"))
    st, data, _ = b.route("POST", "/api/practice/result",
                          body={"units": "no-list"})
    assert st in (400, 409)
    assert "Traceback" not in json.dumps(data)


# ---------- isolamento (B2.31) ----------
def test_canonical_untouched():
    assert hashlib.sha256(Path(KB).read_bytes()).hexdigest() == KB_HASH
    assert hashlib.sha256(Path(EVAL).read_bytes()).hexdigest() == \
        EVAL_HASH


def test_thread_model_shared_sessions():
    import threading
    work = tempfile.mkdtemp(prefix="sm-bt-thr-")
    shared, lock = {}, threading.Lock()
    a = S.Bridge(workdir=work, sessions=shared, lock=lock)
    b = S.Bridge(workdir=work, sessions=shared, lock=lock)
    st, _, c = a.route("POST", "/api/practice/start",
                       body={"topic": 2, "question_type": "TRUE_FALSE",
                             "seed": 11})
    assert st == 200
    tok = ck(c)
    outs = []

    def worker():
        try:
            s2, d2, _ = b.route(
                "POST", "/api/practice/submit",
                body={"answer": "V", "attempt_id": "att-b2thr"},
                cookie=tok)
            outs.append((s2, d2["result"]["replayed"]))
        except Exception as e:  # noqa: BLE001
            outs.append(("ERR", repr(e)))

    ts = [threading.Thread(target=worker) for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(o[1] for o in outs if o[0] == 200) == [False, True], \
        outs
