"""Tests B3.31–B3.33: Learn UX estàtica + E2E sense xarxa."""
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web"))

import server as S  # noqa: E402

WEB = ROOT / "web"


def page(name):
    return (WEB / name).read_text(encoding="utf-8")


def js(name):
    return (WEB / "static" / "js" / name).read_text(encoding="utf-8")


@pytest.fixture()
def bridge():
    return S.Bridge(workdir=tempfile.mkdtemp(prefix="sm-lt-"))


# ---------- estructura progrés ----------
def test_progres_overview_structure():
    t = page("progres.html")
    for i in ("prog-summary", "prog-mastery", "prog-recommend", "prog-unit"):
        assert 'id="%s"' % i in t, i
    assert "progres.js" in t and t.count("aria-live") >= 3


def test_progres_js_wiring():
    t = js("progres.js")
    for ep in ("/api/learn/progress", "/api/study/mastery",
               "/api/learn/priorities", "/api/learn/unit", "/api/learn/start"):
        assert ep in t, ep
    assert "practice.html?from=adaptive" in t and "sessionStorage" in t
    assert "reasons_display" in t
    for s in ("priority_score", "policy_id", "seed", "weights"):
        assert s not in t, s


def test_learn_no_adaptive_duplication():
    t = js("progres.js")
    for s in ("priority_score", "epsilon", "spacing:", "categoria:",
              "criticality", "threshold", "MASTERED", "attempts >=",
              "correct >=", "Math.random", ".sort("):
        assert s not in t, s
    assert "reasons_display" in t


def test_learn_a11y():
    t = page("progres.html")
    assert t.count("aria-live") >= 3
    t2 = js("progres.js")
    assert "role" in t2 and "status" in t2


# ---------- E2E priorities (B3.3–B3.8) ----------
def test_priorities_empty_honest(bridge):
    st, data, _ = bridge.route("GET", "/api/learn/priorities",
                               {"limit": "5"})
    assert st == 200 and isinstance(data["priorities"], list)


def test_priorities_after_weakness(bridge):
    bridge.route("POST", "/api/practice/start",
                 body={"topic": 2, "question_type": "FORMULA",
                       "formula_id": "eq-02-0034", "seed": 14})
    tok = list(bridge.sessions)[-1]
    bridge.route("POST", "/api/practice/submit",
                 body={"answer": "$U=u_c/k$",
                       "attempt_id": "att-lrn1"},
                 cookie="sm_session=" + tok)
    st, data, _ = bridge.route("GET", "/api/learn/priorities",
                               {"limit": "5"})
    assert st == 200 and data["priorities"]
    r = data["priorities"][0]
    assert r["unit"] == "formula:eq-02-0034"
    assert r["action"] in ("REVIEW", "PRACTICE", "REINFORCE",
                           "CHALLENGE", "MAINTAIN")
    assert r["action_label"] and r["action_hint"]
    assert "priority_score" not in r and "priority" in r
    assert r["mastery"]["status"] == "EMERGING"
    assert r["mastery"]["status_label"] == "Inicial"
    assert r["mastery"]["confidence"] == 0.125
    disp = {d["label"] for d in r["reasons_display"]}
    assert "Mastery" in disp and "Error principal" in disp
    assert not any("spacing" in c or "categoria" in c
                   for c in [d["label"] for d in r["reasons_display"]])
    assert r["errors"] and r["errors"][0]["label"]


def test_progress_counts(bridge):
    st, data, _ = bridge.route("GET", "/api/learn/progress")
    assert st == 200
    for k in ("attempts", "correct", "units", "last_activity",
              "recent"):
        assert k in data, k


def test_unit_detail_and_locate(bridge):
    bridge.route("POST", "/api/practice/start",
                 body={"topic": 2, "question_type": "FORMULA",
                       "formula_id": "eq-02-0034", "seed": 14})
    tok = list(bridge.sessions)[-1]
    bridge.route("POST", "/api/practice/submit",
                 body={"answer": "$U=u_c/k$", "attempt_id": "att-lrn2"},
                 cookie="sm_session=" + tok)
    st, data, _ = bridge.route("GET", "/api/learn/unit",
                               {"unit": "formula:eq-02-0034"})
    assert st == 200 and data["state"]["status"] == "EMERGING"
    assert data["locate"]["url"] == "topic.html?topic=2"
    st, data, _ = bridge.route("GET", "/api/learn/unit",
                               {"unit": "topic:T02"})
    assert st == 200
    st, data, _ = bridge.route("GET", "/api/learn/unit",
                               {"unit": "no:existeix"})
    assert st == 200 and data["state"] is None


def test_locate_variants(bridge):
    st, data, _ = bridge.route("GET", "/api/learn/locate",
                               {"unit": "topic:T02"})
    assert data["locate"]["url"] == "topic.html?topic=2"
    st, data, _ = bridge.route("GET", "/api/learn/locate",
                               {"unit": "concept:entrada"})
    # 'entrada' no és terme KB: sense ruta (url null), sense ruta falsa.
    assert st == 200 and data["locate"]["url"] is None
    st, data, _ = bridge.route("GET", "/api/learn/locate",
                               {"unit": "concept:Objectius"})
    assert st == 200 and data["locate"]["url"] == "topic.html?topic=1"
    st, data, _ = bridge.route("GET", "/api/learn/locate",
                               {"unit": "xxx"})
    assert data["locate"] is None


# ---------- E2E loop (B3.18/B3.20/B3.32) ----------
def test_learn_start_roundtrip(bridge):
    bridge.route("POST", "/api/practice/start",
                 body={"topic": 2, "question_type": "SHORT_ANSWER",
                       "seed": 13})
    tok = list(bridge.sessions)[-1]
    bridge.route("POST", "/api/practice/submit",
                 body={"answer": "basura", "attempt_id": "att-lrn3"},
                 cookie="sm_session=" + tok)
    st, data, _ = bridge.route("GET", "/api/learn/priorities",
                               {"limit": "3"})
    rec = data["priorities"][0]
    item = {"knowledge_unit_id": rec["unit"], "unit_kind": rec["kind"],
            "priority": rec["priority"], "action": rec["action"],
            "difficulty": rec["difficulty"],
            "target_topic": rec["targets"]["topic"],
            "target_section": rec["targets"]["section"],
            "target_concepts": rec["targets"]["concepts"],
            "target_formulas": rec["targets"]["formulas"],
            "reasons": rec["reasons"]}
    st, gen, c = bridge.route("POST", "/api/learn/start",
                              body={"item": item})
    assert st == 200, gen
    assert gen["question"]["type"] == "CONCEPTUAL"
    cookie = "sm_session=" + c.split("sm_session=")[1].split(";")[0]
    st, sub, _ = bridge.route(
        "POST", "/api/practice/submit",
        body={"answer": "una resposta", "attempt_id": "att-lrn4"},
        cookie=cookie)
    assert st == 200 and "status" in sub["result"]


def test_learn_start_invalid(bridge):
    st, data, _ = bridge.route("POST", "/api/learn/start",
                               body={"item": {}})
    assert st == 400
    st, data, _ = bridge.route("POST", "/api/learn/start",
                               body={"item": {
                                   "knowledge_unit_id": "formula:xxx",
                                   "unit_kind": "formula", "priority": 1,
                                   "action": "PRACTICE",
                                   "difficulty": "EASY",
                                   "target_topic": 2,
                                   "target_section": None,
                                   "target_concepts": [],
                                   "target_formulas": [],
                                   "reasons": []}})
    assert st == 502 and data["code"] == "GENERATION_ERROR"

def test_priorities_mode_param(bridge):
    st, data, _ = bridge.route("GET", "/api/learn/priorities",
                               {"limit": "5", "mode": "study"})
    assert st == 200 and isinstance(data["priorities"], list)
    st, data, _ = bridge.route("GET", "/api/learn/priorities",
                               {"limit": "5", "mode": "NOPE"})
    assert st == 400
    st, data, _ = bridge.route("GET", "/api/learn/priorities",
                               {"limit": "5", "mode": "exam"})
    assert st == 400


def test_e2e_study_mode_flow(bridge):
    bridge.route("POST", "/api/practice/start",
                 body={"topic": 2, "question_type": "FORMULA",
                       "formula_id": "eq-02-0034", "seed": 14})
    tok = list(bridge.sessions)[-1]
    bridge.route("POST", "/api/practice/submit",
                 body={"answer": "$U=u_c/k$",
                       "attempt_id": "att-mode1"},
                 cookie="sm_session=" + tok)
    st, data, _ = bridge.route("GET", "/api/learn/priorities",
                               {"limit": "5", "mode": "recovery"})
    assert st == 200
    for rec in data["priorities"]:
        assert "mode_recovery" in rec["reasons"]
