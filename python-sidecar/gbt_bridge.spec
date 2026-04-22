# PyInstaller 规范文件：把 bridge.py 冻结为独立 EXE，供 Tauri externalBin 使用。
# 运行方式：
#   pip install -r requirements.txt -r requirements-build.txt
#   pyinstaller python-sidecar/gbt_bridge.spec --noconfirm --clean
#
# 产物：
#   python-sidecar/dist/gbt-bridge.exe

# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# 把 Agilebot SDK 整包（data/submodules）捕获进来，避免运行时动态导入失败。
datas, binaries, hiddenimports = [], [], []
for pkg in ("Agilebot", "openpyxl", "websockets", "aenum", "requests"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        # 缺失时不阻断打包（开发期可能暂无 SDK），运行期会给出清晰报错。
        pass


a = Analysis(
    ['bridge.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'PyQt5', 'PySide2', 'PySide6', 'IPython'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='gbt-bridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,           # sidecar 需要 stdout/stderr 通讯；Rust 端用 CREATE_NO_WINDOW 隐藏黑框
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
