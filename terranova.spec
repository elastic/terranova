# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['bin/terranova'],
    pathex=[],
    binaries=[],
    datas=[('terranova/schemas/', 'terranova/schemas/'), ('terranova/templates/', 'terranova/templates/')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['setuptools', 'setuptools._vendor', 'setuptools._vendor.importlib_metadata'],
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
    name='terranova',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
