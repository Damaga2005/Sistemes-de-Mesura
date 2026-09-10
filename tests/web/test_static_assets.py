import http.client
import sys
import tempfile
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web"))
import server as S  # noqa: E402


@pytest.fixture()
def bridge():
    return S.Bridge(workdir=tempfile.mkdtemp(prefix="sm-assets-"))


@pytest.fixture()
def static_srv(tmp_path, free_tcp_port):
    """Real socket serving `web/` via Handler._static (same pattern as
    tests/test_csrf_http.py). Exercises the actual HTTP static path, not
    just the _MIME dict."""
    srv = S.ThreadingHTTPServer(("127.0.0.1", free_tcp_port), S.Handler)
    _MISSING = object()
    _orig_config = S.Handler.__dict__.get("config", _MISSING)
    _orig_local = S.Handler.__dict__.get("_local", _MISSING)
    S.Handler.config = {"kw": {"workdir": str(tmp_path)},
                        "sessions": {}, "lock": threading.Lock()}
    S.Handler._local = None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield free_tcp_port
    finally:
        srv.shutdown()
        for attr, orig in (("config", _orig_config), ("_local", _orig_local)):
            if orig is _MISSING:
                if attr in S.Handler.__dict__:
                    delattr(S.Handler, attr)
            else:
                setattr(S.Handler, attr, orig)


def _get(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path)
    r = conn.getresponse()
    body = r.read()
    conn.close()
    return r.status, r.getheader("Content-Type"), body


def test_woff2_is_in_mime_map():
    assert S._MIME.get(".woff2") == "font/woff2"


def test_font_file_present_and_valid():
    f = ROOT / "web/static/fonts/InterVariable.woff2"
    assert f.is_file()
    assert f.read_bytes()[:4] == b"wOF2"
    assert 150_000 < f.stat().st_size < 500_000


def test_ofl_license_present():
    assert (ROOT / "web/static/fonts/OFL.txt").is_file()


def test_icons_sprite_present_and_symbol_shaped():
    s = (ROOT / "web/static/icons.svg").read_text(encoding="utf-8")
    for sym in ("home", "book", "target", "sparkles", "chart",
                "clipboard-check", "menu"):
        assert 'id="%s"' % sym in s


def _sprite_symbol_ids():
    import re
    s = (ROOT / "web/static/icons.svg").read_text(encoding="utf-8")
    return set(re.findall(r'<symbol id="([a-z0-9\-]+)"', s))


def test_sprite_keeps_every_known_symbol():
    # F18-04: hardening must not drop any icon the sprite already ships.
    known = {"home", "book", "target", "sparkles", "chart", "clipboard-check",
             "menu", "chevron-right", "close", "check", "x", "alert-triangle",
             "info", "external-link", "arrow-right", "dot"}
    assert known <= _sprite_symbol_ids()


def test_every_use_reference_resolves_to_a_symbol():
    # F18-04: no broken <use> targets anywhere in the shipped JS.
    import re
    ids = _sprite_symbol_ids()
    shell = (ROOT / "web/static/js/shell.js").read_text(encoding="utf-8")
    ui = (ROOT / "web/static/js/ui.js").read_text(encoding="utf-8")
    # static string refs
    for ref in re.findall(r'icons\.svg#([a-z0-9\-]+)', shell + "\n" + ui):
        assert ref in ids, ref
    # shell.js builds names dynamically from NAV + the "menu" button
    nav_icons = set(re.findall(r'icon:\s*"([a-z0-9\-]+)"', shell)) | {"menu"}
    assert nav_icons <= ids, nav_icons - ids


def test_use_elements_carry_href_and_xlink_href():
    # F18-04: both attributes, same target, for modern + legacy engines.
    shell = (ROOT / "web/static/js/shell.js").read_text(encoding="utf-8")
    ui = (ROOT / "web/static/js/ui.js").read_text(encoding="utf-8")
    # shell.js icon(): <use href="..." xlink:href="...">
    assert '<use href="' in shell and 'xlink:href="' in shell
    assert 'xmlns:xlink="http://www.w3.org/1999/xlink"' in shell
    # ui.js svgEl("use", {...}) passes both keys and routes xlink through NS
    assert '"xlink:href": "static/icons.svg#alert-triangle"' in ui
    assert 'setAttributeNS(XLINKNS' in ui


# ---------- HTTP serving (F17 Task 14, Step 2) ----------
def test_http_serves_woff2(static_srv):
    st, ctype, body = _get(static_srv, "/static/fonts/InterVariable.woff2")
    assert st == 200
    assert ctype == "font/woff2"
    assert body[:4] == b"wOF2"


def test_http_serves_icons_sprite(static_srv):
    st, ctype, body = _get(static_srv, "/static/icons.svg")
    assert st == 200
    assert ctype == "image/svg+xml"
    assert b"<symbol" in body


@pytest.mark.parametrize("name", ["temari.html", "tutor.html", "progres.html"])
def test_http_serves_product_pages(static_srv, name):
    st, ctype, body = _get(static_srv, "/" + name)
    assert st == 200
    assert ctype == "text/html; charset=utf-8"
    assert b"<main" in body and b'id="main"' in body


@pytest.mark.parametrize("name,target", [
    ("study.html", b"temari.html"),
    ("learning.html", b"progres.html"),
    ("history.html", b"exams.html"),
])
def test_http_serves_redirect_stubs(static_srv, name, target):
    st, ctype, body = _get(static_srv, "/" + name)
    assert st == 200
    assert ctype == "text/html; charset=utf-8"
    assert b"http-equiv=\"refresh\"" in body and target in body
