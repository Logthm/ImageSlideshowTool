# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['slideshow_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\14695\\PycharmProjects\\ImageSlideshowTool\\.venv\\Lib\\site-packages\\tkinterdnd2', 'tkinterdnd2/'), ('yahei.ttf', '.')],
    hiddenimports=[],
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
    name='slideshow_gui',
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
    icon=['icon.ico'],
)