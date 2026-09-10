"""F17 API contract smoke: the response shapes the redesigned UI relies on.

Backend drift in any of these fails loudly here rather than silently
breaking Temari / Progrés / the dashboard. Four tests, deliberately narrow.
"""
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web"))

import server as S  # noqa: E402


@pytest.fixture()
def bridge():
    # Bridge.route(method, path, query=None, body=None, cookie="", headers=None)
    # -> (status, data, set_cookie). Matches tests/web/test_learn_ux.py.
    return S.Bridge(workdir=tempfile.mkdtemp(prefix="sm-f17c-"))


def test_study_topics_shape(bridge):
    st, data, _ = bridge.route("GET", "/api/study/topics")
    assert st == 200
    assert isinstance(data["topics"], list) and data["topics"]
    tp = data["topics"][0]
    for k in ("topic", "documents", "sections", "formulas"):
        assert k in tp, k
    assert "mastery" in tp
    m = tp["mastery"]
    assert m is None or ("score" in m and "attempts" in m)


def test_learn_progress_shape(bridge):
    st, data, _ = bridge.route("GET", "/api/learn/progress")
    assert st == 200
    assert {"attempts", "correct", "units", "last_activity",
            "recent"} <= set(data)


def test_learn_priorities_projection(bridge):
    bridge.route("POST", "/api/practice/start",
                 body={"topic": 2, "question_type": "FORMULA",
                       "formula_id": "eq-02-0034", "seed": 14})
    tok = list(bridge.sessions)[-1]
    bridge.route("POST", "/api/practice/submit",
                 body={"answer": "$U=u_c/k$", "attempt_id": "att-f17c1"},
                 cookie="sm_session=" + tok)
    st, data, _ = bridge.route("GET", "/api/learn/priorities",
                               {"limit": "5"})
    assert st == 200 and data["priorities"]
    for r in data["priorities"]:
        assert "reasons_display" in r
        for leaked in ("priority_score", "policy_id", "seed"):
            assert leaked not in r, leaked


def test_tutor_ask_provider(bridge):
    st, data, _ = bridge.route("POST", "/api/tutor/ask",
                               body={"query": "què és la incertesa?"})
    assert st == 200
    assert "provider" in data["versions"]["provider"]
