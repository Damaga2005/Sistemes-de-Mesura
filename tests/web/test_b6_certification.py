"""F11-B6: gates reproducibles de certificación final de UX."""
import json
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
    # F17 Task 2: index.html now receives its shell + nav from shell.js
    # (injected around <main>), so it is checked against the injected-shell
    # contract; pre-F17 pages keep their inline chrome and are unchanged.
    inline_pages = ("study.html", "learning.html", "practice.html",
                    "exams.html", "exam.html", "history.html", "results.html",
                    "review.html")
    for name in inline_pages:
        html = (ROOT / "web" / name).read_text(encoding="utf-8")
        assert 'lang="ca"' in html
        assert 'id="main"' in html
        assert 'aria-label="Principal"' in html
        assert 'href="calendar.html"' in html or name in (
            "history.html", "results.html", "review.html")
    shell_js = (ROOT / "web/static/js/shell.js").read_text(encoding="utf-8")
    assert '"aria-label", "Principal"' in shell_js  # nav landmark, injected
    for name in ("index.html",):
        html = (ROOT / "web" / name).read_text(encoding="utf-8")
        assert 'lang="ca"' in html
        assert 'id="main"' in html
        assert ('data-route="%s"' % name) in html
        assert 'static/js/shell.js' in html


def test_final_static_audit_has_no_new_direct_db_or_secret_in_new_b5_ui():
    files = (ROOT / "web/static/js/history.js",
             ROOT / "web/static/js/results.js",
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
