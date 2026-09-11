import sqlite3
import pytest

from app import migrate


def _v(con):
    return con.execute("PRAGMA user_version").fetchone()[0]


def test_fresh_db_reaches_target(tmp_path):
    con = sqlite3.connect(tmp_path / "s.sqlite")
    assert _v(con) == 0
    new = migrate.migrate(con, "student")
    assert new == migrate.TARGETS["student"] == 4
    assert _v(con) == 4


def test_migrate_is_idempotent(tmp_path):
    con = sqlite3.connect(tmp_path / "s.sqlite")
    migrate.migrate(con, "student")
    assert migrate.migrate(con, "student") == 4
    assert _v(con) == 4


def test_newer_snapshot_is_rejected(tmp_path):
    con = sqlite3.connect(tmp_path / "s.sqlite")
    con.execute("PRAGMA user_version = 99")
    with pytest.raises(RuntimeError, match="newer"):
        migrate.migrate(con, "student")


def test_unknown_db_name_raises(tmp_path):
    con = sqlite3.connect(tmp_path / "s.sqlite")
    with pytest.raises(KeyError):
        migrate.migrate(con, "does_not_exist")


def test_out_of_order_or_duplicate_script_is_caught(tmp_path, monkeypatch):
    d = tmp_path / "student"
    d.mkdir()
    (d / "001_baseline.sql").write_text("-- baseline\n", encoding="utf-8")
    (d / "003_gap.sql").write_text("SELECT 1;\n", encoding="utf-8")
    monkeypatch.setattr(migrate, "MIGRATIONS_DIR", tmp_path)
    monkeypatch.setitem(migrate.TARGETS, "student", 3)
    con = sqlite3.connect(tmp_path / "s.sqlite")
    with pytest.raises(RuntimeError, match="gap|secuencia"):
        migrate.migrate(con, "student")


def test_failed_script_rolls_back_atomically(tmp_path, monkeypatch):
    d = tmp_path / "student"
    d.mkdir()
    (d / "001_baseline.sql").write_text("-- baseline\n", encoding="utf-8")
    (d / "002_bad.sql").write_text(
        "CREATE TABLE atomic_probe (x);\nTHIS IS NOT VALID SQL;\n", encoding="utf-8")
    monkeypatch.setattr(migrate, "MIGRATIONS_DIR", tmp_path)
    monkeypatch.setitem(migrate.TARGETS, "student", 2)
    con = sqlite3.connect(tmp_path / "s.sqlite")
    with pytest.raises(sqlite3.OperationalError):
        migrate.migrate(con, "student")
    # el fallo en la 2a sentencia revierte la 1a y deja user_version intacto
    assert _v(con) == 1
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]
    assert "atomic_probe" not in tables
