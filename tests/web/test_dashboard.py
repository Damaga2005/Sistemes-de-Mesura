from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
def _r(p): return (ROOT / p).read_text(encoding="utf-8")

def test_index_has_dashboard_regions():
    h = _r("web/index.html")
    for i in ("hero-continue", "stat-domini", "stat-precisio", "stat-preguntes",
              "reinforce-cards", "recent-activity"):
        assert 'id="%s"' % i in h, i
    assert 'data-route="index.html"' in h
    assert "NOT_IMPLEMENTED" not in h

def test_dashboard_js_wiring():
    t = _r("web/static/js/dashboard.js")
    for ep in ("/api/study/next", "/api/study/mastery", "/api/learn/progress",
               "/api/learn/priorities"):
        assert ep in t, ep
    assert "Math.random" not in t and ".sort(" not in t
