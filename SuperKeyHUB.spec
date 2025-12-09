# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/logo_484x74.png', 'assets'), ('assets/app.ico', 'assets'), ('libs', 'libs')],
    hiddenimports=['psutil', 'requests', 'requests.adapters', 'urllib3', 'serial', 'serial.tools', 'serial.tools.list_ports', 'flet', 'flet.core', 'flet_core', 'threading', 'queue', 'datetime', 'enum', 'json', 'pathlib', 'pystray', 'PIL', 'PIL.Image', 'pythonnet', 'clr', 'System', 'wmi', 'pystray._win32', 'winreg', 'ctypes', 'ctypes.wintypes'],
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
    version='C:\\Users\\xiebo\\AppData\\Local\\Temp\\54dd1866-2804-424e-89eb-8b8c9c199448',
    uac_admin=True,
    icon=['assets\\app.ico'],
)
