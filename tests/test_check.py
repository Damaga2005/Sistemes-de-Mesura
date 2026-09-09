import json
import sqlite3
from pathlib import Path

import pytest

from app import artifacts


@pytest.fixture
def staged(tmp_path, monkeypatch):
    """A minimal fake package dir with one artifact + manifest."""
    pkg = tmp_path / "pkg"
    (pkg / "data" / "processed").mkdir(parents=True)
    db = pkg / "data" / "processed" / "knowledge.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE formulas(x)")
    con.executemany("INSERT INTO formulas VALUES (?)", [(i,) for i in range(3)])
    con.execute("PRAGMA user_version = 1")
    con.commit(); con.close()
    monkeypatch.setattr(artifacts._paths, "package_dir", lambda: pkg)
    monkeypatch.setenv("SM_HOME", str(tmp_path / "home"))
    from app import paths
    paths.ensure_dirs()
    monkeypatch.setattr(artifacts, "PACKAGED_ARTIFACTS",
                        ("data/processed/knowledge.sqlite",))
    monkeypatch.setattr(artifacts, "SENTINELS",
                        {"formulas": ("data/processed/knowledge.sqlite",
                                      "SELECT COUNT(*) FROM formulas", 3)})
    return pkg


def test_clean_check_passes(staged):
    artifacts.write_manifest()
    assert artifacts.check() == []


def test_altered_artifact_is_detected(staged):
    artifacts.write_manifest()
    db = staged / "data" / "processed" / "knowledge.sqlite"
    con = sqlite3.connect(db); con.execute("INSERT INTO formulas VALUES (99)")
    con.commit(); con.close()
    problems = artifacts.check()
    assert any("sha256" in p or "hash" in p for p in problems)


def test_stale_user_version_is_detected(staged, monkeypatch):
    artifacts.write_manifest()
    monkeypatch.setitem(artifacts._migrate.TARGETS, "knowledge", 2)
    assert any("user_version" in p for p in artifacts.check(fast=True))


def test_broken_sentinel_is_detected(staged, monkeypatch):
    artifacts.write_manifest()
    monkeypatch.setattr(artifacts, "SENTINELS",
                        {"formulas": ("data/processed/knowledge.sqlite",
                                      "SELECT COUNT(*) FROM formulas", 999)})
    assert any("formulas" in p for p in artifacts.check())


def test_fast_is_a_subset_of_full(staged):
    artifacts.write_manifest()
    assert artifacts.check(fast=True) == []
