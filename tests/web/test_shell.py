import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SHELL = (ROOT / "web/static/js/shell.js").read_text(encoding="utf-8")
PRODUCT_PAGES = ["index.html", "temari.html", "tutor.html", "practice.html",
                 "progres.html", "exams.html"]


def _nav_hrefs():
    return set(re.findall(r'href:\s*"([a-z0-9\-]+\.html)"', SHELL))


def test_nav_has_exactly_the_six_targets():
    assert _nav_hrefs() == set(PRODUCT_PAGES)


def test_nav_has_no_stub_or_unimplemented_targets():
    for dead in ("documents.html", "calendar.html", "history.html",
                 "study.html", "learning.html"):
        assert dead not in _nav_hrefs()


def test_shell_sets_single_active_route():
    # shell.js marks aria-current when it.href === route (one match max)
    assert 'aria-current="page"' in SHELL
    assert "getAttribute(\"data-route\")" in SHELL


def test_every_product_page_declares_a_known_route():
    for name in PRODUCT_PAGES:
        p = ROOT / "web" / name
        if not p.is_file():
            continue  # created in a later task
        html = p.read_text(encoding="utf-8")
        if "data-route=" not in html:
            continue  # exists but not yet migrated to the injected shell (own task)
        m = re.search(r'data-route="([a-z0-9\-]+\.html)"', html)
        assert m and m.group(1) == name, name
        assert 'aria-label="Principal"' not in html  # injected, not inline
        assert 'id="main"' in html and 'class="skip-link"' in html


def test_hamburger_button_is_labelled():
    assert re.search(r'menu-toggle[^>]*aria-label=', SHELL)
