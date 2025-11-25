# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/logo_484x74.png', 'assets'), ('libs', 'libs')],
    hiddenimports=['pythonnet', 'clr', 'System', 'psutil', 'wmi', 'requests', 'requests.adapters', 'urllib3', 'serial', 'serial.tools', 'serial.tools.list_ports', 'flet', 'flet.core', 'flet_core', 'threading', 'queue', 'datetime', 'enum'],
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
    name='SuperKeyHUB',
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
    version='C:\\Users\\xiebo\\AppData\\Local\\Temp\\2643a753-457d-4b40-bdbf-bbe506e01953',
    icon=['assets\\app.ico'],
)
