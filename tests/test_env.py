import os
from pathlib import Path

from app.env import load_env, parse_env


def test_parse_handles_comments_blanks_and_quotes():
    text = "\n".join([
        "# comment",
        "",
        "SM_PORT=8901",
        'SM_HOME="C:\\Users\\me\\sm"',
        "SM_STUDENT='me'",
        "  SM_LOG_LEVEL = INFO  ",
    ])
    got = parse_env(text)
    assert got == {
        "SM_PORT": "8901",
        "SM_HOME": "C:\\Users\\me\\sm",
        "SM_STUDENT": "me",
        "SM_LOG_LEVEL": "INFO",
    }


def test_parse_ignores_malformed_lines():
    assert parse_env("NOEQUALS\n=nokey\nOK=1") == {"OK": "1"}


def test_load_env_does_not_override_real_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("SM_PORT", "9999")
    f = tmp_path / ".env"
    f.write_text("SM_PORT=8901\nSM_STUDENT=me\n", encoding="utf-8")
    parsed = load_env(f)
    assert parsed["SM_PORT"] == "8901"          # returned as parsed
    assert os.environ["SM_PORT"] == "9999"      # real env wins
    assert os.environ["SM_STUDENT"] == "me"     # absent key is set


def test_load_env_missing_file_is_ok(tmp_path):
    assert load_env(tmp_path / "nope.env") == {}
