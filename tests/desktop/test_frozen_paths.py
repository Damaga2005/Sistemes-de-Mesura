"""F19-05: the frozen-layout path contract.

package_dir() (read-only bundle root) must resolve relative to app/paths.py's
own location, so that under PyInstaller it lands inside _MEIPASS; the writable
dirs (data_dir/backup_dir) must never resolve under package_dir().
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web"))


def test_package_dir_is_app_parent_and_holds_bundled_data():
    from app import paths as p
    # (a) documented resolution: <dir containing app/>/..
    assert p.package_dir() == Path(p.__file__).resolve().parent.parent
    # (b) the read-only artefacts the spec bundles live under it
    assert (p.package_dir() / "data" / "processed" / "knowledge.sqlite").is_file()
    assert (p.package_dir() / "data" / "generated" / "questions.sqlite").is_file()
    assert (p.package_dir() / "data" / "index").is_dir()


def test_writable_dirs_never_under_package_dir(monkeypatch, tmp_path):
    from app import paths as p
    monkeypatch.setenv("SM_HOME", str(tmp_path / "home"))
    for var in ("SM_DATA_DIR", "SM_BACKUP_DIR", "SM_INDEX_DIR",
                "SM_LOG_DIR", "SM_CONFIG_DIR"):
        monkeypatch.delenv(var, raising=False)
    pkg = p.package_dir().resolve()
    assert pkg not in p.data_dir().resolve().parents
    assert pkg not in p.backup_dir().resolve().parents
    assert str(pkg) not in str(p.data_dir().resolve())
    assert str(pkg) not in str(p.backup_dir().resolve())


def test_bridge_seed_copy_lands_in_workdir_not_bundle(monkeypatch, tmp_path):
    import server as S
    home = tmp_path / "home"
    monkeypatch.setenv("SM_HOME", str(home))
    monkeypatch.delenv("SM_DATA_DIR", raising=False)
    work = home / "data"
    b = S.Bridge(workdir=str(work))
    # seed DB copied into the writable workdir
    assert (work / "questions.sqlite").is_file()
    assert b.work == work
    # nothing was written under a PyInstaller bundle temp
    assert "_MEI" not in str(b.work)
    pkg = __import__("app.paths", fromlist=["paths"]).package_dir().resolve()
    assert pkg not in b.work.resolve().parents
