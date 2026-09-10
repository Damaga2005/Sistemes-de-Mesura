# tests/desktop/test_launcher.py
import importlib
import socket
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


def _load(monkeypatch, fake_webview):
    monkeypatch.setitem(sys.modules, "webview", fake_webview)
    mod = importlib.import_module("escritorio")
    return importlib.reload(mod)


def test_imports_without_starting_gui(monkeypatch):
    fake = types.SimpleNamespace(create_window=lambda *a, **k: None, start=lambda *a, **k: None)
    mod = _load(monkeypatch, fake)
    assert hasattr(mod, "main")


def test_server_argv_is_localhost_dynamic_port(monkeypatch):
    fake = types.SimpleNamespace(create_window=lambda *a, **k: None, start=lambda *a, **k: None)
    mod = _load(monkeypatch, fake)
    captured = {}
    monkeypatch.setattr(mod, "_server_thread",
                        lambda argv, errbox: captured.setdefault("argv", argv))
    # make wait_for_port publish a real, listening port so main() proceeds to webview
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
    monkeypatch.setattr(mod, "wait_for_port", lambda *a, **k: port)
    monkeypatch.setattr(mod, "wait_for_socket", lambda *a, **k: True)
    win = {}
    fake.create_window = lambda title, url, **k: win.update(title=title, url=url, **k)
    fake.start = lambda *a, **k: win.update(started=k)
    mod.main()
    assert captured["argv"][:4] == ["--host", "127.0.0.1", "--port", "0"]
    assert win["url"] == "http://127.0.0.1:%d/index.html" % port
    assert win["width"] == 1280 and win["height"] == 850
    assert win["min_size"] == (900, 600)
    assert win["text_select"] is True
    assert win["started"].get("debug") is False
    assert "js_api" not in win


def test_timeout_when_port_never_published(monkeypatch):
    fake = types.SimpleNamespace(create_window=lambda *a, **k: None, start=lambda *a, **k: None)
    mod = _load(monkeypatch, fake)
    monkeypatch.setattr(mod, "_server_thread", lambda argv, errbox: None)
    monkeypatch.setattr(mod, "WAIT_TIMEOUT", 0.5)
    import pytest
    with pytest.raises(RuntimeError):
        mod.main()


def test_error_when_server_thread_dies(monkeypatch):
    fake = types.SimpleNamespace(create_window=lambda *a, **k: None, start=lambda *a, **k: None)
    mod = _load(monkeypatch, fake)

    def dead(argv, errbox):
        errbox.append(OSError("port in use"))
    monkeypatch.setattr(mod, "_server_thread", dead)
    monkeypatch.setattr(mod, "WAIT_TIMEOUT", 0.5)
    import pytest
    with pytest.raises(RuntimeError) as ei:
        mod.main()
    assert "port in use" in str(ei.value)


def test_no_toctou_probe_in_source():
    src = (ROOT / "escritorio.py").read_text(encoding="utf-8")
    # the launcher must not probe a port then hand it off
    assert "bind((" not in src or "getsockname" not in src, \
        "launcher must not do bind->getsockname->close port selection"
