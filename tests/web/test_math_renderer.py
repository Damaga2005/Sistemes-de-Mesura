"""MathJax integration: math-renderer.js + mathjax-config.js + wiring into
the page scripts that show LaTeX-bearing free text (tutor/practice/exam/
topic/review). No DOM test runner in this repo (only `node --check`), so
renderMath()'s own logic is proven with a Node harness that stubs `window`,
mirroring tests/web/test_lang_switch.py. Wiring into each page script is
proven with source-text assertions, mirroring tests/web/test_ui_helpers.py.
"""
import re
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
JS = ROOT / "web/static/js"
WEB = ROOT / "web"
RENDERER = (JS / "math-renderer.js").read_text(encoding="utf-8")
CONFIG = (JS / "mathjax-config.js").read_text(encoding="utf-8")


def _run_node(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(["node", "-e", script], capture_output=True, text=True,
                          cwd=str(ROOT))


# --------------------------------------------------------------- source hygiene

def test_math_renderer_js_parses():
    r = subprocess.run(["node", "--check", str(JS / "math-renderer.js")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_mathjax_config_js_parses():
    r = subprocess.run(["node", "--check", str(JS / "mathjax-config.js")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_math_renderer_never_touches_innerHTML():
    # Task's core security invariant (mirrors test_innerHTML_only_renderer_output):
    # the renderer must never build HTML from strings. MathJax mutates the DOM
    # internally via typesetPromise(); this module must not assign innerHTML.
    # (The word may appear in comments documenting the invariant itself.)
    assert not re.search(r"\.innerHTML\s*=", RENDERER)


def test_math_renderer_hygiene():
    for s in ("eval(", "Function(", "localStorage", "document.cookie",
              "Math.random", ".sort(", "sessionStorage"):
        assert s not in RENDERER, s


def test_math_renderer_exports_single_function():
    assert "window.smMath" in RENDERER
    assert "renderMath" in RENDERER


# ------------------------------------------------------------- behaviour (Node)

def test_renderMath_calls_typesetPromise_when_ready():
    harness = textwrap.dedent(r"""
        const fs = require('fs');
        const src = fs.readFileSync('web/static/js/math-renderer.js', 'utf8');
        function ok(c, m) { if (!c) { console.error('FAIL: ' + m); process.exit(1); } }

        let calls = [];
        const window = { MathJax: { typesetPromise: (roots) => { calls.push(roots); return Promise.resolve(); } } };
        new Function('window', src)(window);
        const root = { id: 'r1' };
        window.smMath.renderMath(root).then(() => {
          ok(calls.length === 1, 'typesetPromise called once');
          ok(calls[0].length === 1 && calls[0][0] === root, 'called with [root]');
          console.log('OK');
        }).catch(e => { console.error('FAIL: rejected ' + e); process.exit(1); });
    """)
    r = _run_node(harness)
    assert r.returncode == 0 and "OK" in r.stdout, (r.stdout, r.stderr)


def test_renderMath_noop_when_mathjax_absent():
    harness = textwrap.dedent(r"""
        const fs = require('fs');
        const src = fs.readFileSync('web/static/js/math-renderer.js', 'utf8');
        const window = {};
        new Function('window', src)(window);
        window.smMath.renderMath({ id: 'r1' }).then(() => {
          console.log('OK');
        }).catch(e => { console.error('FAIL: threw ' + e); process.exit(1); });
    """)
    r = _run_node(harness)
    assert r.returncode == 0 and "OK" in r.stdout, (r.stdout, r.stderr)


def test_renderMath_noop_on_null_root():
    harness = textwrap.dedent(r"""
        const fs = require('fs');
        const src = fs.readFileSync('web/static/js/math-renderer.js', 'utf8');
        const window = { MathJax: { typesetPromise: () => { throw new Error('should not be called'); } } };
        new Function('window', src)(window);
        Promise.all([window.smMath.renderMath(null), window.smMath.renderMath(undefined)]).then(() => {
          console.log('OK');
        }).catch(e => { console.error('FAIL: ' + e); process.exit(1); });
    """)
    r = _run_node(harness)
    assert r.returncode == 0 and "OK" in r.stdout, (r.stdout, r.stderr)


def test_renderMath_waits_for_startup_promise_before_first_typeset():
    # Combined MathJax components boot async: typesetPromise is only added
    # to the MathJax object once startup.promise resolves. Simulate that race.
    harness = textwrap.dedent(r"""
        const fs = require('fs');
        const src = fs.readFileSync('web/static/js/math-renderer.js', 'utf8');
        function ok(c, m) { if (!c) { console.error('FAIL: ' + m); process.exit(1); } }

        let calls = 0;
        let resolveStartup;
        const startupPromise = new Promise(res => { resolveStartup = res; });
        const window = { MathJax: { startup: { promise: startupPromise } } };
        new Function('window', src)(window);
        const p = window.smMath.renderMath({ id: 'r1' }).then(() => {
          ok(calls === 1, 'typesetPromise called exactly once, after startup');
          console.log('OK');
        }).catch(e => { console.error('FAIL: ' + e); process.exit(1); });
        // typesetPromise only becomes available once MathJax finishes booting
        window.MathJax.typesetPromise = (roots) => { calls++; return Promise.resolve(); };
        resolveStartup();
    """)
    r = _run_node(harness)
    assert r.returncode == 0 and "OK" in r.stdout, (r.stdout, r.stderr)


def test_renderMath_swallows_typeset_rejection():
    # A malformed formula or a MathJax-internal error must not break the
    # calling UI (task acceptance: "fórmula malformada no rompe UI").
    harness = textwrap.dedent(r"""
        const fs = require('fs');
        const src = fs.readFileSync('web/static/js/math-renderer.js', 'utf8');
        const window = { MathJax: { typesetPromise: () => Promise.reject(new Error('bad tex')) } };
        new Function('window', src)(window);
        window.smMath.renderMath({ id: 'r1' }).then(() => {
          console.log('OK');
        }).catch(e => { console.error('FAIL: rejection leaked: ' + e); process.exit(1); });
    """)
    r = _run_node(harness)
    assert r.returncode == 0 and "OK" in r.stdout, (r.stdout, r.stderr)


# ---------------------------------------------------------------- config shape

def test_mathjax_config_declares_real_delimiters():
    # $...$ is the ONLY delimiter that actually appears in the corpus today
    # (verified: 505 KB chunks + real question stems use it; zero `\(`, `\[`
    # or `$$` occurrences exist anywhere in the KB). \( \) and \[ \] are the
    # task's mandated minimum and cost nothing to also support.
    assert re.search(r"inlineMath\s*:\s*\[\s*\[\s*['\"]\$['\"]\s*,\s*['\"]\$['\"]\s*\]", CONFIG), \
        "single-dollar inline math must be configured (the corpus' real delimiter)"
    assert r"\\(" in CONFIG and r"\\)" in CONFIG
    assert r"\\[" in CONFIG and r"\\]" in CONFIG
    assert "displayMath" in CONFIG
    assert "processEscapes" in CONFIG and "true" in CONFIG


def test_mathjax_config_does_not_touch_innerHTML():
    assert "innerHTML" not in CONFIG


# ------------------------------------------------------------- page wiring

TEMPLATES_WITH_MATH = ("tutor.html", "practice.html", "exam.html",
                       "topic.html", "content.html", "review.html")


def test_templates_load_config_then_vendor_then_renderer():
    for name in TEMPLATES_WITH_MATH:
        html = (WEB / name).read_text(encoding="utf-8")
        cfg = html.find("mathjax-config.js")
        vendor = html.find("vendor/mathjax/")
        renderer = html.find("math-renderer.js")
        assert cfg != -1, "%s: missing mathjax-config.js" % name
        assert vendor != -1, "%s: missing vendored MathJax" % name
        assert renderer != -1, "%s: missing math-renderer.js" % name
        assert cfg < vendor < renderer, \
            "%s: scripts must load config -> vendor -> renderer, in that order" % name
        # MathJax's own install docs: the config script and the combined
        # component must NOT be deferred/async relative to each other.
        vendor_line_start = html.rfind("<script", 0, vendor)
        vendor_line_end = html.find(">", vendor)
        vendor_tag = html[vendor_line_start:vendor_line_end]
        assert "defer" not in vendor_tag and "async" not in vendor_tag, \
            "%s: MathJax combined component must load synchronously" % name


def test_js_files_call_render_math_after_freetext_insertion():
    targets = {
        "tutor.js": "smMath.renderMath",
        "practice.js": "smMath.renderMath",
        "exam.js": "smMath.renderMath",
        "topic.js": "smMath.renderMath",
        "review.js": "smMath.renderMath",
    }
    for name, needle in targets.items():
        src = (JS / name).read_text(encoding="utf-8")
        assert needle in src, "%s: does not call %s" % (name, needle)


def test_css_scopes_overflow_to_mathjax_display_containers_only():
    css = (ROOT / "web/static/css/base.css").read_text(encoding="utf-8")
    assert "mjx-container" in css
    assert re.search(r"mjx-container\[display=.true.\]\s*\{[^}]*overflow-x:\s*auto", css)
    # never widen this to the whole chat/page (task's explicit CSS guardrail)
    assert not re.search(r"^\s*(body|\.chat|\.chat__thread)\s*\{[^}]*overflow-x:\s*auto",
                         css, re.MULTILINE)


def test_no_new_innerHTML_sites_introduced():
    # The touched files must keep passing the existing whole-app invariant
    # (tests/web/test_study_ux.py::test_innerHTML_only_renderer_output):
    # every `.innerHTML =` RHS is one of the pre-existing whitelisted sites.
    # topic.js and review.js drop their render_latex()-fed innerHTML sites
    # entirely in favour of textContent + renderMath, per the approved scope.
    allowed = ('""', "''", "fhtml")
    for name in ("tutor.js", "practice.js", "exam.js", "topic.js", "review.js"):
        src = (JS / name).read_text(encoding="utf-8")
        for m in re.finditer(r"\.innerHTML\s*=\s*([^;]+);", src):
            rhs = m.group(1).strip()
            assert rhs in allowed, (name, rhs[:80])
