"""F11-B6: gates reproducibles de certificación final de UX."""
import json
import re
import subprocess
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_final_benchmark_has_required_distribution():
    path = ROOT / "data/evaluation/phase_11_b6_final_certification_benchmark.jsonl"
    rows = [json.loads(line) for line in path.read_text(
        encoding="utf-8").splitlines() if line.strip()]
    counts = Counter(row["category"] for row in rows)
    # The requested distribution sums to 125 (not 120); preserve every
    # category minimum rather than silently dropping five certification cases.
    assert len(rows) == 125
    assert counts == Counter({
        "APP_SHELL": 20, "STUDY": 15, "TUTOR": 15,
        "PRACTICE": 15, "ADAPTIVE_MASTERY": 10, "EXAM": 15,
        "RESULTS": 10, "REVIEW": 10, "HISTORY": 5,
        "REAL_EXAM_BLIND": 5, "SECURITY_IDOR": 5})


def test_certification_docs_and_runs_exist():
    for name in ("PHASE_11_B6_BASELINE.md", "PHASE_11_B6.md",
                 "PHASE_11_CERTIFICATION.md"):
        assert (ROOT / "docs" / name).is_file()
    for name in ("phase_11_b6_final_certification_run1.json",
                 "phase_11_b6_final_certification_run2.json"):
        payload = json.loads((ROOT / "data/evaluation" / name).read_text(
            encoding="utf-8"))
        assert payload["score"] == "125/125"
        assert payload["deterministic"] is True


def test_all_product_pages_keep_shell_and_honest_navigation():
    pages = ("index.html", "temari.html", "tutor.html", "practice.html",
             "progres.html", "exams.html", "exam.html")
    for name in pages:
        html = (ROOT / "web" / name).read_text(encoding="utf-8")
        assert re.search(r'\blang="(ca|es)"', html), name
        assert 'id="main"' in html, name
        assert 'data-route="%s"' % name in html, name
    # shell + "Principal" landmark now come from the single injected source
    shell = (ROOT / "web/static/js/shell.js").read_text(encoding="utf-8")
    assert '"aria-label", "Principal"' in shell  # nav.setAttribute in shell.js


def test_legacy_urls_are_honest_redirects():
    for name, target in (("study.html", "temari.html"),
                         ("learning.html", "progres.html"),
                         ("history.html", "exams.html#historial")):
        html = (ROOT / "web" / name).read_text(encoding="utf-8")
        assert 'location.replace("%s' % target.split("#")[0] in html, name
        assert ('href="%s"' % target) in html or target.split("#")[0] in html


def test_final_static_audit_has_no_new_direct_db_or_secret_in_new_b5_ui():
    files = (ROOT / "web/static/js/results.js",
             ROOT / "web/static/js/review.js")
    joined = "\n".join(p.read_text(encoding="utf-8") for p in files).lower()
    for forbidden in ("sqlite", "answer_key", "chain_of_thought", "raw_llm",
                      "provider", "secret", "token"):
        assert forbidden not in joined


def test_all_browser_javascript_parses():
    scripts = sorted((ROOT / "web/static/js").glob("*.js"))
    for script in scripts:
        result = subprocess.run(["node", "--check", str(script)],
                                capture_output=True, text=True)
        assert result.returncode == 0, "%s: %s" % (
            script.name, result.stderr)
