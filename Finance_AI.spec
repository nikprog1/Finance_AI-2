# PyInstaller spec: сборка Bank Statement Analyzer
# Запуск: pyinstaller Finance_AI.spec

import runpy

# Спек-файл выполняется из корня проекта, поэтому version.py доступен по относительному пути
_ver_ns = runpy.run_path("version.py")
_app_version = _ver_ns.get("__version__", "0.0.0")
app_name = f"Finance_AI_{_app_version}"

a = Analysis(
    scripts=["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        "database",
        "csv_import",
        "financial_agent",
        "llm_agent",
        "env_loader",
        "logging_config",
        "models_dialog",
        "transaction_dialog",
        "goal_dialog",
        "agent_rules",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
