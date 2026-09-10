# -*- mode: python ; coding: utf-8 -*-
# Build:  pyinstaller escritorio.spec --noconfirm --clean
import os

PROJECT_DIR = os.path.abspath(os.path.dirname(os.path.abspath(SPEC)))


def _d(rel, dest=None):
    return (os.path.join(PROJECT_DIR, rel), dest if dest is not None else os.path.dirname(rel) or ".")


datas = [
    _d("web", "web"),
    _d("data/processed/knowledge.sqlite", "data/processed"),
    _d("data/generated/questions.sqlite", "data/generated"),
    _d("data/index", "data/index"),
    _d("data/source_manifest.json", "data"),
    _d("data/evaluation/eval.sqlite", "data/evaluation"),
    _d("data/ARTIFACT-MANIFEST.json", "data"),
    _d(".env.example", "."),
    _d("app/llm/prompts", "app/llm/prompts"),
    _d("app/examiner/prompts", "app/examiner/prompts"),
    _d("app/correction/prompts", "app/correction/prompts"),
    _d("app/migrations", "app/migrations"),
]

a = Analysis(
    ["escritorio.py"],
    pathex=[PROJECT_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "webview.platforms.edgechromium",
        "webview.platforms.winforms",
        "webview.platforms.mshtml",
        "clr_loader",
        # extend ONLY with imports a real build proves missing (F19 gate).
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="SistemesDeMesura",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=os.path.join(PROJECT_DIR, "icono.ico"),
)
