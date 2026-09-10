"""Windows desktop entrypoint for Sistemes de Mesura.

Runs the existing web/server.py in a daemon thread bound to 127.0.0.1 on an
OS-assigned port, learns that port via SM_PORT_FILE (F19-00), waits for the
socket, then shows a pywebview window. No server logic lives here.
"""
import os
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

import webview

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PREFERRED_TITLE = "Sistemes de Mesura"
WIN_W, WIN_H = 1280, 850
WIN_MIN = (900, 600)
WAIT_TIMEOUT = 15.0
POLL = 0.1


def _server_thread(argv, errbox):
    """Target for the daemon thread; records startup errors instead of raising."""
    try:
        from web import server as _web
        _web.main(argv)
    except Exception as exc:  # noqa: BLE001  (surface to the launcher)
        errbox.append(exc)


def wait_for_port(port_file, deadline, thread, errbox):
    while time.time() < deadline:
        if errbox:
            raise RuntimeError("server failed to start: %r" % errbox[0])
        if not thread.is_alive() and not port_file.is_file():
            raise RuntimeError("server thread exited before publishing a port")
        if port_file.is_file():
            txt = port_file.read_text(encoding="utf-8").strip()
            if txt.isdigit():
                p = int(txt)
                if 0 < p < 65536:
                    return p
        time.sleep(POLL)
    raise RuntimeError("server did not publish its port within %.0fs" % WAIT_TIMEOUT)


def wait_for_socket(host, port, deadline):
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(POLL)
    return False


def main():
    ext = os.environ.get("SM_PORT_FILE")
    if ext:
        # External caller (operator/CI) owns this path and its cleanup; honor it
        # verbatim so the exe's bound port stays observable from outside.
        tmpdir = None
        port_file = Path(ext)
    else:
        tmpdir = tempfile.mkdtemp(prefix="sm-desktop-")
        port_file = Path(tmpdir) / "port"
    errbox = []
    try:
        if tmpdir is not None:
            os.environ["SM_PORT_FILE"] = str(port_file)
        argv = ["--host", "127.0.0.1", "--port", "0"]
        if tmpdir is None:
            # An externally-supplied path may still hold a port from a previous
            # run; drop it so wait_for_port can't return that stale value.
            try:
                port_file.unlink()
            except OSError:
                pass
        th = threading.Thread(target=_server_thread, args=(argv, errbox), daemon=True)
        th.start()

        deadline = time.time() + WAIT_TIMEOUT
        port = wait_for_port(port_file, deadline, th, errbox)
        sock_deadline = time.time() + WAIT_TIMEOUT
        if not wait_for_socket("127.0.0.1", port, sock_deadline):
            raise RuntimeError("server port %d never accepted a connection" % port)

        webview.create_window(
            PREFERRED_TITLE,
            "http://127.0.0.1:%d/index.html" % port,
            width=WIN_W, height=WIN_H, min_size=WIN_MIN, text_select=True,
        )
        webview.start(debug=False)
        return 0
    finally:
        if tmpdir is not None:
            os.environ.pop("SM_PORT_FILE", None)
            try:
                if port_file.is_file():
                    port_file.unlink()
                os.rmdir(tmpdir)
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
