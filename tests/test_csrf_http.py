"""CSRF enforcement over a real socket (no in-process shortcut).

Complementa `tests/test_csrf.py` (que crida `Bridge.route` directament):
aquí el `X-CSRF-Token` viatja pel fil amb el nom en minúscules, tal com
l'envia el `fetch()` d'un navegador real. Sense la normalitzacio
case-insensitive a `route()`, tota peticio mutant de la UI rebia 403.
"""
import http.client
import json
import threading

import web.server as server


def _serve(port, tmp_path):
    srv = server.ThreadingHTTPServer(("127.0.0.1", port), server.Handler)
    server.Handler.config = {"kw": {"workdir": str(tmp_path)},
                             "sessions": {}, "lock": threading.Lock()}
    server.Handler._local = None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _cookie_header(resp):
    return "; ".join(sc.split(";", 1)[0]
                     for sc in resp.msg.get_all("Set-Cookie", []))


def test_csrf_enforced_over_real_socket(tmp_path, free_tcp_port):
    srv = _serve(free_tcp_port, tmp_path)
    try:
        conn = http.client.HTTPConnection("127.0.0.1", free_tcp_port, timeout=5)

        # GET /api/session mints sm_session + sm_csrf cookies.
        conn.request("GET", "/api/session")
        r = conn.getresponse()
        csrf = json.loads(r.read())["csrf"]
        cookie = _cookie_header(r)
        assert "sm_csrf=" in cookie and "sm_session=" in cookie

        # POST with NO X-CSRF-Token -> 403 CSRF.
        conn.request("POST", "/api/practice/start",
                     body=json.dumps({"topic": 2}),
                     headers={"Content-Type": "application/json",
                              "Cookie": cookie})
        r = conn.getresponse()
        payload = json.loads(r.read())
        assert r.status == 403 and payload["code"] == "CSRF"

        # POST with LOWERCASE header name + correct token -> not CSRF.
        # (Fails pre-fix: dict(self.headers).get("X-CSRF-Token") is None.)
        conn.request("POST", "/api/practice/start",
                     body=json.dumps({"topic": 2}),
                     headers={"Content-Type": "application/json",
                              "Cookie": cookie,
                              "x-csrf-token": csrf})
        r = conn.getresponse()
        r.read()
        assert r.status != 403
    finally:
        srv.shutdown()
