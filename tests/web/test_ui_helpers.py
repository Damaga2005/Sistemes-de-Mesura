import re, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
JSDIR = ROOT / "web/static/js"
NEW = ["shell.js", "ui.js", "i18n.js", "dashboard.js", "temari.js",
       "tutor.js", "progres.js"]

def _read(n):
    p = JSDIR / n
    return p.read_text(encoding="utf-8") if p.is_file() else ""

def test_new_js_parses():
    for n in NEW:
        if not (JSDIR / n).is_file():
            continue
        r = subprocess.run(["node", "--check", str(JSDIR / n)],
                           capture_output=True, text=True)
        assert r.returncode == 0, (n, r.stderr)

def test_new_js_no_random_no_sort():
    for n in NEW:
        t = _read(n)
        assert "Math.random" not in t, n
        assert ".sort(" not in t, n

def test_new_js_no_domain_logic():
    blob = "".join(_read(n) for n in NEW).lower()
    for s in ("correct_answer", "formula_validation", "calculatescore",
              "math.max(score"):
        assert s not in blob, s
    for var in ("score", "mastery", "grade", "priority"):
        assert not re.search(r"(?<![=!<>])\b%s\s*=\s*(?![=>])" % var, blob), var

def test_localstorage_only_in_i18n():
    for n in NEW:
        if n == "i18n.js":
            continue
        assert "localStorage" not in _read(n), n
    assert "document.cookie" not in "".join(_read(n) for n in NEW)

def test_status_thresholds_frozen():
    t = _read("ui.js")
    # exact boundary literals must appear (frozen contract)
    assert "0.4" in t and "0.75" in t and "0.95" in t
    assert "statusFromMastery" in t
