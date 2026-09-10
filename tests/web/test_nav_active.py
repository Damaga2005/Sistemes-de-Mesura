"""F18-03: the shared sidebar marks exactly one active nav item with
aria-current="page", including for sub-pages that belong to a section.
"""
import re
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SHELL = (ROOT / "web/static/js/shell.js").read_text(encoding="utf-8")


def test_section_map_present_and_single_emit_point():
    assert "SECTION_OF" in SHELL
    # sub-pages resolve to their section
    for sub, section in (("topic.html", "temari.html"),
                         ("content.html", "temari.html"),
                         ("exam.html", "exams.html"),
                         ("results.html", "exams.html"),
                         ("review.html", "exams.html")):
        assert re.search(r'"%s":\s*"%s"' % (sub, section), SHELL), sub
    # unchanged single emit point + direct-match branch
    assert "it.href === route" in SHELL
    assert SHELL.count('aria-current="page"') == 1
    # documents/calendar deliberately unmapped
    assert '"documents.html":' not in SHELL and '"calendar.html":' not in SHELL


def _render(route):
    """Run shell.js build() against a DOM stub for one data-route, return the
    rendered sidebar innerHTML."""
    harness = textwrap.dedent(r"""
        const fs = require('fs');
        const src = fs.readFileSync('web/static/js/shell.js', 'utf8');
        const ROUTE = process.argv[1];
        function elem(tag) {
          const e = { tagName: tag, className: '', _id: '', _html: '', _attr: {},
            _l: {}, parentNode: null, style: {},
            get id() { return this._id; }, set id(v) { this._id = v; },
            get innerHTML() { return this._html; }, set innerHTML(v) { this._html = v; },
            appendChild(c) { c.parentNode = e; return c; },
            insertBefore(c) { c.parentNode = e; return c; },
            setAttribute(k, v) { this._attr[k] = String(v); },
            getAttribute(k) { return this._attr[k]; },
            addEventListener(ev, fn) { (this._l[ev] = this._l[ev] || []).push(fn); },
            querySelector() { return elem('stub'); },
          };
          return e;
        }
        const created = [];
        const main = elem('main'); main.id = 'main';
        main.parentNode = elem('div');
        const body = elem('body');
        body._attr['data-route'] = ROUTE;
        const document = {
          readyState: 'complete', body: body,
          getElementById: id => (id === 'main' ? main : null),
          createElement: t => { const n = elem(t); created.push(n); return n; },
          createTextNode: v => ({ nodeValue: v }),
        };
        const window = { smI18n: { t: k => k, lang: 'ca', onChange() {} } };
        window.document = document;
        new Function('window', 'document', src)(window, document);
        const nav = created.find(n => n.className === 'sidebar');
        process.stdout.write(nav ? nav.innerHTML : '');
    """)
    r = subprocess.run(["node", "-e", harness, route], capture_output=True,
                       text=True, cwd=str(ROOT))
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_exactly_one_active_item_per_route():
    # section landing pages -> their own item active
    for route in ("index.html", "temari.html", "practice.html", "tutor.html",
                  "progres.html", "exams.html"):
        html = _render(route)
        assert html.count('aria-current="page"') == 1, route
        assert ('href="%s" aria-current="page"' % route) in html, route

    # sub-pages -> the section item active (exactly one)
    for sub, section in (("topic.html", "temari.html"),
                         ("content.html", "temari.html"),
                         ("exam.html", "exams.html"),
                         ("results.html", "exams.html"),
                         ("review.html", "exams.html")):
        html = _render(sub)
        assert html.count('aria-current="page"') == 1, sub
        assert ('href="%s" aria-current="page"' % section) in html, (sub, section)

    # pages outside every section -> no active item, nav still renders
    for route in ("documents.html", "calendar.html"):
        html = _render(route)
        assert html.count('aria-current="page"') == 0, route
        assert 'class="nav-link"' in html, route


def test_legacy_stub_pages_stay_honest_redirects():
    for name, target in (("study.html", "temari.html"),
                         ("learning.html", "progres.html"),
                         ("history.html", "exams.html#historial")):
        html = (ROOT / "web" / name).read_text(encoding="utf-8")
        assert ('location.replace("%s' % target.split("#")[0]) in html, name
        assert 'class="sidebar"' not in html and 'id="site-nav"' not in html, name
