"""Tests B1.22: Design System + App Shell (estàtics, sense navegador).

Verifiquen fitxers i contingut: tokens, components, landmarks,
navegació, accessibilitat, responsive, no-duplicació de domini,
seguretat i pressupost de pes.
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
WEB = ROOT / "web"
CSS = WEB / "static" / "css"
JS = WEB / "static" / "js" / "app.js"
PAGES = ["index.html", "study.html", "learning.html", "exams.html",
         "documents.html", "calendar.html", "design-system.html"]

TOKENS = ["--background", "--surface", "--surface-elevated",
          "--text-primary", "--text-secondary", "--text-tertiary",
          "--border", "--accent", "--success", "--warning", "--danger",
          "--info", "--focus", "--font-family", "--fs-display",
          "--fs-h1", "--fs-body", "--fs-caption", "--fs-button",
          "--sp-xs", "--sp-md", "--sp-3xl", "--radius-sm",
          "--radius-xl", "--shadow-sm", "--shadow-lg",
          "--duration-fast", "--ease-standard", "--touch-min",
          "--content-max"]
COMPONENTS = [".button", ".icon-button", ".input", ".select",
              ".textarea", ".check", ".radio", ".toggle", ".card",
              ".badge", ".pill", ".divider", ".avatar", ".progress",
              ".spinner", ".skeleton", ".alert", ".toast", ".modal",
              ".dropdown", ".tab", ".breadcrumbs", ".tooltip",
              ".state-block", ".formula", ".nav-link", ".skip-link"]
FORBIDDEN = ["score =", "mastery =", "grade =", "adaptive =",
             "correct_answer =", "formula_validation =",
             "permission =", "provenance =", "SELECT COUNT",
             "FROM exam_", "FROM mastery", "sqlite3",
             "GEMINI_API_KEY", "correct_answer\"", "'correct_answer'"]
LIGHT = ["#f5f5f7", "#ffffff", "#1d1d1f", "#0071e3"]
DARK = ["#000000", "#1c1c1e", "#f5f5f7", "#0a84ff"]


def css():
    return "\n".join((CSS / f).read_text(encoding="utf-8")
                     for f in ("tokens.css", "base.css", "layout.css",
                               "components.css"))


def page(name):
    return (WEB / name).read_text(encoding="utf-8")


# ---------- rendering ----------
def test_pages_exist_and_link_css_js():
    for name in PAGES:
        t = page(name)
        for cssf in ("tokens.css", "base.css", "layout.css",
                     "components.css"):
            assert cssf in t, (name, cssf)
        assert "static/js/app.js" in t, name


def test_shell_landmarks_per_page():
    for name in PAGES:
        t = page(name)
        assert "<header" in t and "<nav" in t and "<main" in t, name
        assert 'id="main"' in t and 'class="skip-link"' in t, name
    # Les 6 pàgines de producte marquen la ruta activa al nav; la
    # galeria interna queda exempta (no és navegació de producte).
    for name in PAGES:
        if name == "design-system.html":
            continue
        t = page(name)
        nav = t.split('<nav class="sidebar"')[1].split("</nav>")[0]
        assert nav.count('aria-current="page"') == 1, name


def test_nav_points_to_real_pages():
    for name in PAGES:
        for target in ("index.html", "study.html", "learning.html",
                       "exams.html", "documents.html", "calendar.html"):
            assert 'href="%s"' % target in page(name), (name, target)


def test_active_route_matches_page():
    mapping = {"index.html": "index.html", "study.html": "study.html",
               "learning.html": "learning.html",
               "exams.html": "exams.html",
               "documents.html": "documents.html",
               "calendar.html": "calendar.html"}
    for name, href in mapping.items():
        t = page(name)
        m = re.search(r'aria-current="page"[^>]*>|<a[^>]*aria-current'
                      r'="page"[^>]*href="([^"]+)"', t)
        assert m, name
        assert ('href="%s"' % href) in t.split("aria-current")[0][-200:] \
            or 'href="%s" aria-current' % href in t \
            or 'href="%s"' % href in t[max(0, t.find("aria-current") - 200):], \
            name


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
    for tok in TOKENS:
        assert tok in t, tok
    assert "prefers-color-scheme: dark" in t
    for color in LIGHT + DARK:
        assert color in t, color


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
        t = page(name)
        assert 'lang="ca"' in t, name
        assert 'name="viewport"' in t, name
        assert "<h1" in t, name
        assert "<title>" in t, name


def test_inputs_have_labels():
    for name in PAGES:
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
    for name in PAGES:
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
    total = 0
    for p in list((CSS).glob("*.css")) + [JS] + [WEB / n for n in PAGES]:
        total += p.stat().st_size
    assert total < 120 * 1024, total
    assert (CSS / "tokens.css").stat().st_size < 8 * 1024
    assert JS.stat().st_size < 8 * 1024
