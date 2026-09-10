"""Tests B2.24–B2.29 (part estàtica): pàgines, fetching, a11y, audits."""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
WEB = ROOT / "web"
JS = WEB / "static" / "js"


def page(name):
    return (WEB / name).read_text(encoding="utf-8")


def js(name):
    return (JS / name).read_text(encoding="utf-8")


# ---------- study ----------
def test_study_pages_exist():
    for name in ("study.html", "practice.html", "topic.html",
                 "content.html"):
        assert (WEB / name).is_file(), name


def test_study_html_is_redirect_stub():
    t = page("study.html")
    assert 'location.replace("temari.html' in t
    assert 'topics-grid' not in t and 'tutor-form' not in t


def test_practice_player_structure():
    t = page("practice.html")
    for i in ("cfg-topic", "cfg-type", "cfg-diff", "cfg-seed", "cfg-go",
              "q-box", "a-box", "c-box"):
        assert 'id="%s"' % i in t, i


def test_topic_content_params():
    assert "topic-root" in page("topic.html")
    assert "content-root" in page("content.html")
    assert "section_id" in js("topic.js") and "topic" in js("topic.js")


def test_temari_structure():
    t = page("temari.html")
    assert 'id="topic-cards"' in t and 'data-route="temari.html"' in t
    assert 'aria-live="polite"' in t
    j = js("temari.js")
    assert "/api/study/topics" in j
    assert "statusFromMastery" in j  # reuses the frozen helper
    assert "Math.random" not in j and ".sort(" not in j


# ---------- tutor/practice JS ----------
def test_tutor_structure():
    t = page("tutor.html")
    assert 'id="tutor-thread"' in t and 'id="tutor-input"' in t
    assert 'data-route="tutor.html"' in t and 'aria-live="polite"' in t


def test_tutor_flow_wiring():
    j = js("tutor.js")
    assert "/api/tutor/ask" in j
    assert "abstain" in j and "ABSTAIN" in j
    assert "Math.random" not in j and ".sort(" not in j


def test_practice_flow_wiring():
    t = js("practice.js")
    assert "/api/practice/start" in t and "/api/practice/submit" in t
    for typ in ("TRUE_FALSE", "MULTIPLE_CHOICE", "NUMERICAL",
                "SHORT_ANSWER", "OPEN", "MULTI_STEP"):
        assert typ in t, typ
    assert "fieldset" in t and "legend" in t


def test_no_single_textarea_for_all():
    t = js("practice.js")
    assert 'type = "radio"' in t or "type='radio'" in t or \
        'inp.type = "radio"' in t


# ---------- B2.26 determinisme / B2.28 seguretat JS ----------
def test_js_no_random_no_sort():
    for name in ("app.js", "practice.js", "topic.js", "tutor.js"):
        t = js(name)
        assert "Math.random" not in t, name
        assert ".sort(" not in t, name


def test_js_no_eval_no_storage_no_cookie():
    for name in ("app.js", "practice.js", "topic.js",
                 "progres.js", "tutor.js"):
        t = js(name)
        for s in ("eval(", "Function(", "localStorage",
                  "document.cookie"):
            assert s not in t, (name, s)
    # sessionStorage: només context transitori de navegació
    # (pregunta adaptativa), mai persistència (regla B3.14/B3.15).
    for name in ("app.js", "topic.js", "tutor.js"):
        assert "sessionStorage" not in js(name), name


def test_innerHTML_only_renderer_output():
    # Permès: buidar ("") i HTML del renderer llista-blanca (fhtml).
    for name in ("practice.js", "topic.js", "tutor.js"):
        t = js(name)
        for m in re.finditer(r"\.innerHTML\s*=\s*([^;]+);", t):
            rhs = m.group(1).strip()
            assert rhs in ('""', "''", "fhtml", "b.html"), (name, rhs[:80])


def test_no_domain_logic_js():
    blob = "".join(js(n) for n in
                   ("app.js", "practice.js", "topic.js", "tutor.js"))
    low = blob.lower()
    for s in ("correct_answer", "formula_validation", "Math.max(score",
              "calculateScore"):
        assert s.lower() not in low, s
    for var in ("score", "mastery"):
        assert not re.search(r"(?<![=!<>])\b%s\s*=\s*(?![=>])" % var,
                             low), var
