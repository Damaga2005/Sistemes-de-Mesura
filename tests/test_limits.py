import http.client
import threading

import web.server as server


def test_oversize_body_is_rejected(monkeypatch, tmp_path, free_tcp_port):
    monkeypatch.setenv("SM_MAX_BODY_BYTES", "16")
    monkeypatch.setenv("SM_DATA_DIR", str(tmp_path))
    srv = server.ThreadingHTTPServer(("127.0.0.1", free_tcp_port), server.Handler)
    server.Handler.config = {"kw": {"workdir": str(tmp_path)},
                             "sessions": {}, "lock": threading.Lock()}
    t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", free_tcp_port, timeout=5)
        conn.request("POST", "/api/practice/start", body=b"x" * 100,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        assert resp.status == 413
    finally:
        srv.shutdown()
