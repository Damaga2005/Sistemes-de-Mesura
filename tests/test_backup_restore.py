import sqlite3
from pathlib import Path

import pytest

from app import backup


@pytest.fixture
def sm_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SM_HOME", str(tmp_path))
    from app import paths
    paths.ensure_dirs()
    d = paths.data_dir()
    con = sqlite3.connect(d / "student.sqlite")
    con.execute("CREATE TABLE t(x)")
    con.execute("INSERT INTO t VALUES (1)")
    con.execute("PRAGMA user_version = 1")
    con.commit()
    con.close()
    return tmp_path


def test_backup_then_restore_round_trips(sm_home):
    from app import paths
    snap = backup.make_backup()
    db = paths.data_dir() / "student.sqlite"
    con = sqlite3.connect(db)
    con.execute("INSERT INTO t VALUES (2)")
    con.commit()
    con.close()
    backup.restore(snap.name)
    con = sqlite3.connect(db)
    rows = con.execute("SELECT x FROM t ORDER BY x").fetchall()
    con.close()
    assert rows == [(1,)]


def test_manifest_records_hash_and_version(sm_home):
    snap = backup.make_backup()
    manifest = snap / "manifest.json"
    assert manifest.is_file()
    listed = backup.list_backups()
    assert listed[0]["timestamp"] == snap.name
    entry = next(f for f in listed[0]["files"] if f["name"] == "student.sqlite")
    assert entry["user_version"] == 1
    assert len(entry["sha256"]) == 64


def test_restore_refuses_newer_user_version(sm_home, monkeypatch):
    snap = backup.make_backup()
    # tamper: bump the snapshot's user_version above target
    con = sqlite3.connect(snap / "student.sqlite")
    con.execute("PRAGMA user_version = 50")
    con.commit()
    con.close()
    with pytest.raises(RuntimeError, match="newer|user_version"):
        backup.restore(snap.name)
