"""Tests B1.22 / F17: Design System + App Shell (estàtics, sense navegador).

Verifiquen fitxers i contingut: tokens, components, landmarks,
navegació, accessibilitat, responsive, no-duplicació de domini,
seguretat i pressupost de pes.

F17 Task 2: shell (header + sidebar) is injected by shell.js around
<main id="main">; only index.html conforms to the injected-shell contract
so far. PAGES grows in later tasks (5 +temari, 7 +practice, 8 +tutor,
9 +progres, 10 +exams, 11 +design-system).
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
WEB = ROOT / "web"
CSS = WEB / "static" / "css"
JSDIR = WEB / "static" / "js"
JS = JSDIR / "app.js"
PAGES = ["index.html", "temari.html", "practice.html", "tutor.html",
         "progres.html", "exams.html", "design-system.html"]
# Each product page links exactly its own page script. Later tasks extend
# this map (tutor.js, progres.js, practice.js, exams.js); design-system.html
# has no page script so it is deliberately absent.
PAGE_JS = {"index.html": "dashboard.js", "temari.html": "temari.js",
           "practice.html": "practice.js", "tutor.html": "tutor.js",
           "progres.html": "progres.js", "exams.html": "exams.js"}

TOKENS = ["--bg", "--surface", "--surface-elevated", "--surface-sunken",
          "--overlay", "--border", "--border-strong", "--text-primary",
          "--text-secondary", "--text-tertiary", "--text-on-accent",
          "--accent", "--accent-hover", "--accent-pressed", "--accent-soft",
          "--accent-border", "--accent-contrast-text", "--success",
          "--warning", "--danger", "--info", "--focus", "--gradient-accent",
          "--gradient-surface", "--shadow-sm", "--shadow-md", "--shadow-lg",
          "--shadow-accent-glow", "--font-sans", "--font-mono", "--fs-display",
          "--fs-h1", "--fs-h2", "--fs-h3", "--fs-body", "--fs-body-lg",
          "--fs-meta", "--fs-overline", "--fs-stat", "--fw-regular",
          "--fw-h1", "--fw-bold", "--lh-tight", "--ls-tight", "--sp-2xs",
          "--sp-xs", "--sp-md", "--sp-3xl", "--radius-xs", "--radius-xl",
          "--radius-full", "--duration-fast", "--ease-standard",
          "--touch-min", "--content-max", "--reading-max", "--sidebar-w",
          "--header-h"]
COMPONENTS = [".button", ".icon-button", ".input", ".select",
              ".textarea", ".check", ".radio", ".toggle", ".card",
              ".badge", ".pill", ".divider", ".avatar", ".progress",
              ".spinner", ".skeleton", ".alert", ".toast", ".modal",
              ".dropdown", ".tab", ".breadcrumbs", ".tooltip",
              ".state-block", ".formula", ".nav-link", ".skip-link",
              ".hero-card", ".topic-card", ".stat-card", ".rec-card",
              ".progress__fill", ".progress-ring", ".chat__msg",
              ".drawer", ".chip-num"]
FORBIDDEN = ["score =", "mastery =", "grade =", "adaptive =",
             "correct_answer =", "formula_validation =",
             "permission =", "provenance =", "SELECT COUNT",
             "FROM exam_", "FROM mastery", "sqlite3",
             "GEMINI_API_KEY", "correct_answer\"", "'correct_answer'"]
# Dark is the primary :root; light is the override.
DARK_ROOT = ["#131118", "#1a1822", "#6f4bff", "#f3f1f9"]
LIGHT_OVERRIDE = ["#f5f4fa", "#6a45f0", "#1c1a29"]


def css():
    return "\n".join((CSS / f).read_text(encoding="utf-8")
                     for f in ("tokens.css", "base.css", "shell.css",
                               "components.css", "pages.css"))


def page(name):
    return (WEB / name).read_text(encoding="utf-8")


def shell_js():
    return (JSDIR / "shell.js").read_text(encoding="utf-8")


# ---------- rendering ----------
def test_pages_exist_and_link_css_js():
    for name in PAGES:
        if not (WEB / name).is_file():
            continue
        t = page(name)
        for cssf in ("tokens.css", "base.css", "shell.css", "components.css",
                     "pages.css"):
            assert cssf in t, (name, cssf)
        assert "static/js/i18n.js" in t, name
        assert "static/js/shell.js" in t, name
        assert "static/js/app.js" in t, name
        assert "static/js/ui.js" in t, name
        if name in PAGE_JS:
            assert ("static/js/%s" % PAGE_JS[name]) in t, name


def test_shell_landmarks_per_page():
    sj = shell_js()
    # header + sidebar nav landmarks are injected by shell.js.
    assert 'className = "header"' in sj
    assert 'className = "sidebar"' in sj and '"aria-label", "Principal"' in sj
    for name in PAGES:
        if not (WEB / name).is_file():
            continue
        t = page(name)
        assert "<main" in t and 'id="main"' in t, name
        assert 'class="skip-link"' in t, name
        assert ('data-route="%s"' % name) in t, name
        # shell is injected, never inline.
        assert 'class="sidebar"' not in t, name
    # Exactly one active nav item (aria-current) is asserted against
    # shell.js in tests/web/test_shell.py (test_shell_sets_single_active_route,
    # test_every_product_page_declares_a_known_route).


def test_nav_points_to_real_pages():
    sj = shell_js()
    targets = re.findall(r'href:\s*"([a-z0-9\-]+\.html)"', sj)
    assert targets, "shell.js NAV has no targets"
    expected = {"index.html", "temari.html", "practice.html",
                "tutor.html", "progres.html", "exams.html"}
    assert set(targets) == expected, targets
    for dead in ("study.html", "learning.html", "documents.html",
                 "calendar.html"):
        assert dead not in targets, dead


def test_active_route_matches_page():
    sj = shell_js()
    assert 'getAttribute("data-route")' in sj
    assert 'aria-current="page"' in sj
    assert "it.href === route" in sj
    for name in PAGES:
        if not (WEB / name).is_file():
            continue
        t = page(name)
        m = re.search(r'data-route="([a-z0-9\-]+\.html)"', t)
        assert m and m.group(1) == name, name


def test_resource_pages_are_implemented_honestly():
    documents = page("documents.html")
    calendar = page("calendar.html")
    assert "NOT_IMPLEMENTED" not in documents
    assert "static/js/documents.js" in documents
    assert "NOT_IMPLEMENTED" not in calendar
    assert "static/js/calendar.js" in calendar
    assert "NOT_IMPLEMENTED" not in page("index.html")


def test_gallery_covers_primitives():
    t = page("design-system.html")
    for word in ("button", "input", "select", "textarea", "card",
                 "badge", "alert", "progress", "spinner", "skeleton",
                 "modal", "dropdown", "tablist", "tooltip", "formula"):
        assert word in t.lower(), word


# ---------- tokens y componentes ----------
def test_semantic_tokens_defined():
    t = (CSS / "tokens.css").read_text(encoding="utf-8")
    blob = css()
    for tok in TOKENS:
        assert tok in t, tok
    assert ":root" in t
    assert "@media (prefers-color-scheme: light)" in t
    assert ':root[data-theme="light"]' in t
    assert ':root[data-theme="dark"]' in t
    for color in DARK_ROOT:
        assert color in blob, color
    for color in LIGHT_OVERRIDE:
        assert color in blob, color


def test_no_hardcoded_colors_in_components():
    t = (CSS / "components.css").read_text(encoding="utf-8")
    bad = re.findall(r"#[0-9a-fA-F]{3,8}", t)
    assert bad == [], bad


def test_component_classes_exist():
    t = css()
    for cls in COMPONENTS:
        assert cls in t, cls


def test_states_covered():
    t = css()
    for sel in (":hover", ":focus-visible", ":active", ":disabled",
                '[aria-selected="true"]', '[aria-invalid="true"',
                "prefers-reduced-motion"):
        assert sel in t, sel


# ---------- accessibility ----------
def test_a11y_basics_per_page():
    for name in PAGES:
        if not (WEB / name).is_file():
            continue
        t = page(name)
        assert re.search(r'\blang="(ca|es)"', t), name
        assert 'name="viewport"' in t, name
        assert "<h1" in t, name
        assert "<title>" in t, name


def test_inputs_have_labels():
    for name in PAGES:
        if not (WEB / name).is_file():
            continue
        t = page(name)
        for m in re.finditer(r'<(input|select|textarea)[^>]*>', t):
            tag = m.group(0)
            if 'type="hidden"' in tag or 'type="checkbox"' in tag \
                    or 'type="radio"' in tag:
                continue
            mid = re.search(r'id="([^"]+)"', tag)
            assert mid and ('for="%s"' % mid.group(1)) in t, (name, tag)


def test_icon_buttons_named():
    for name in PAGES:
        if not (WEB / name).is_file():
            continue
        t = page(name)
        for m in re.finditer(r"<button[^>]*>.*?</button>", t, re.S):
            tag = m.group(0)[:200]
            if "<svg" in m.group(0) and "aria-label" not in tag:
                raise AssertionError((name, tag[:80]))


# ---------- responsive ----------
def test_responsive_foundation():
    t = css()
    assert "48rem" in t and "64rem" in t and "80rem" in t
    assert "overflow-x" in t
    assert "--touch-min" in t


# ---------- no domain duplication / seguridad ----------
def test_no_domain_logic_in_frontend():
    blob = css() + JS.read_text(encoding="utf-8")
    # F17: shared chrome + helpers must stay presentation-only too.
    for n in ("shell.js", "ui.js", "i18n.js", "dashboard.js", "temari.js",
              "tutor.js", "progres.js"):
        if (JSDIR / n).is_file():
            blob += (JSDIR / n).read_text(encoding="utf-8")
    for name in PAGES:
        if not (WEB / name).is_file():
            continue
        blob += page(name)
    low = blob.lower()
    for s in FORBIDDEN:
        assert s.lower() not in low, s


def test_no_secrets_or_paths():
    blob = "".join(p.read_text(encoding="utf-8") for p in WEB.rglob("*")
                   if p.is_file() and p.suffix in
                   (".html", ".css", ".js", ".svg", ".json", ".txt",
                    ".md"))
    assert "C:\\" not in blob and "/home/" not in blob
    assert "Traceback" not in blob


# ---------- performance ----------
def test_perf_budgets():
    # Budgets are ceilings, not targets: minimize assets, do not add code to fill headroom.
    total = 0
    for p in list((CSS).glob("*.css")) + [JS] + [WEB / n for n in PAGES]:
        total += p.stat().st_size
    assert total < 220 * 1024, total
    assert (CSS / "tokens.css").stat().st_size < 14 * 1024
    assert JS.stat().st_size < 8 * 1024
    assert (JSDIR / "shell.js").stat().st_size < 10 * 1024
    # F17 Task 13: budget raised 12->16 KiB for the complete CA+ES chrome
    # dictionary (exam player, results and review pages). Still data-only,
    # single file, no logic added.
    assert (JSDIR / "i18n.js").stat().st_size < 16 * 1024
