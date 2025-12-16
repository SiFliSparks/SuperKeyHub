# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all

datas = [('D:\\program\\SuperKeyHub\\assets', 'assets'), ('D:\\program\\SuperKeyHub\\libs', 'libs'), ('D:\\program\\SuperKeyHub\\tools', 'tools')]
binaries = []
hiddenimports = ['flet', 'flet_core', 'psutil', 'serial', 'serial.tools.list_ports', 'requests', 'PIL', 'pystray', 'clr', 'wmi', 'pythonnet', 'clr_loader', 'clr_loader.ffi']
hiddenimports += collect_submodules('clr')
hiddenimports += collect_submodules('clr_loader')
tmp_ret = collect_all('pythonnet')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'test', 'unittest'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SuperKeyHUB',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['D:\\program\\SuperKeyHub\\assets\\app.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SuperKeyHUB',
)
