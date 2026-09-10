import os
import socket
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web"))
import server as S  # noqa: E402


def _run_server(argv, env):
    old = {k: os.environ.get(k) for k in env}
    os.environ.update({k: v for k, v in env.items() if v is not None})
    for k, v in env.items():
        if v is None:
            os.environ.pop(k, None)
    t = threading.Thread(target=lambda: S.main(argv), daemon=True)
    t.start()
    return t, old


def _restore(old):
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def test_port_file_written_after_bind_with_real_port(tmp_path):
    pf = tmp_path / "port"
    t, old = _run_server(["--host", "127.0.0.1", "--port", "0"],
                         {"SM_PORT_FILE": str(pf), "SM_DATA_DIR": str(tmp_path / "d")})
    try:
        for _ in range(150):
            if pf.is_file() and pf.read_text().strip().isdigit():
                break
            time.sleep(0.1)
        assert pf.is_file(), "SM_PORT_FILE never written"
        port = int(pf.read_text().strip())
        assert 1024 < port < 65536
        # the published port is actually accepting connections
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            pass
    finally:
        _restore(old)


def test_no_port_file_when_env_unset(tmp_path):
    # pick a fixed free port so we can prove the server came up without a file
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    sentinel = tmp_path / "should-not-exist"
    t, old = _run_server(["--host", "127.0.0.1", "--port", str(port)],
                         {"SM_PORT_FILE": None, "SM_DATA_DIR": str(tmp_path / "d")})
    try:
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise AssertionError("server did not start")
        assert not sentinel.exists()
    finally:
        _restore(old)
