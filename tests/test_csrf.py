import web.server as server


def _bridge(tmp_path):
    return server.Bridge(workdir=str(tmp_path))


def test_get_needs_no_csrf(tmp_path):
    b = _bridge(tmp_path)
    status, _, _ = b.route("GET", "/api/study/topics", {}, {}, "")
    assert status == 200


def test_post_without_token_is_rejected(tmp_path):
    b = _bridge(tmp_path)
    status, payload, _ = b.route(
        "POST", "/api/practice/start", {}, {"topic": 2}, "", headers={})
    assert status == 403 and payload["code"] == "CSRF"


def test_post_with_matching_token_passes_csrf(tmp_path):
    b = _bridge(tmp_path)
    # first GET to mint the session + csrf cookie
    _, _, set_cookie = b.route("GET", "/api/session", {}, {}, "")
    tok = [c for c in set_cookie.split("\n") if c.startswith("sm_csrf=")][0]
    csrf = tok.split("=", 1)[1].split(";", 1)[0]
    sess = [c for c in set_cookie.split("\n") if c.startswith("sm_session=")][0]
    cookie = "%s; %s" % (sess.split(";", 1)[0], tok.split(";", 1)[0])
    status, payload, _ = b.route(
        "POST", "/api/practice/start", {}, {"topic": 2}, cookie,
        headers={"X-CSRF-Token": csrf})
    assert status != 403  # may be 200 or a domain error, but not CSRF
