import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SPEC = (ROOT / "escritorio.spec").read_text(encoding="utf-8")

REQUIRED = [
    '_d("web", "web")',
    '"data/processed/knowledge.sqlite"',
    '"data/generated/questions.sqlite"',
    '_d("data/index"',
    '"data/source_manifest.json"',
    '"data/evaluation/eval.sqlite"',
    '"data/ARTIFACT-MANIFEST.json"',
    '".env.example"',
]
FORBIDDEN = ["chunks.jsonl", "formulas.jsonl", "students.sqlite",
             "data/metadata", "ingestion_report", "data/student"]


def test_spec_entry_and_exe_flags():
    assert 'Analysis(\n    ["escritorio.py"]' in SPEC or '["escritorio.py"]' in SPEC
    assert 'name="SistemesDeMesura"' in SPEC
    assert "console=False" in SPEC
    assert re.search(r'icon=.*icono\.ico', SPEC)
    assert (ROOT / "icono.ico").is_file()
    assert (ROOT / "icono.ico").read_bytes()[:4] == b"\x00\x00\x01\x00"


def test_spec_bundles_exactly_the_audited_resources():
    for token in REQUIRED:
        assert token in SPEC, "missing bundled resource: %s" % token
    for token in FORBIDDEN:
        assert token not in SPEC, "runtime junk in bundle: %s" % token


def test_spec_has_webview_hidden_imports():
    for h in ("webview.platforms.edgechromium", "webview.platforms.winforms",
              "webview.platforms.mshtml", "clr_loader"):
        assert h in SPEC
