import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web"))
import server as S  # noqa: E402


@pytest.fixture()
def bridge():
    return S.Bridge(workdir=tempfile.mkdtemp(prefix="sm-assets-"))


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
