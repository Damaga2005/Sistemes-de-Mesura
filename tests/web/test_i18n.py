import re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
I18N = (ROOT / "web/static/js/i18n.js").read_text(encoding="utf-8")

def test_localstorage_key_is_only_sm_lang():
    hits = re.findall(r'localStorage\.\w+\(\s*"([^"]+)"', I18N)
    assert hits and set(hits) == {"sm-lang"}

def test_ca_and_es_have_identical_key_sets():
    # crude but effective: every "x.y": in the ca block appears in the es block
    ca = I18N.split('ca:')[1].split('es:')[0]
    es = I18N.split('es:')[1]
    keys_ca = set(re.findall(r'"([a-z0-9_.]+)":', ca))
    keys_es = set(re.findall(r'"([a-z0-9_.]+)":', es))
    assert keys_ca and keys_ca == keys_es, keys_ca ^ keys_es

def test_no_academic_content_keys():
    # i18n is chrome only — no formula/section/definition bodies
    for bad in ("formula", "equation", "def.", "theorem"):
        assert ('"%s' % bad) not in I18N.lower()

def test_default_is_ca():
    assert 'var lang = "ca"' in I18N
