# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build.

    python tools/build_engine.py      # the engine
    pyinstaller WhistlerStudio.spec

Produces `dist/WhistlerStudio/`, a folder to zip and send. On Windows it holds
two executables: WhistlerStudio, which is the editor, and whistler, which is
the same program with a console so that a script can run it and read what it
said. Both take the same arguments; see app/cli.py.

The singing is Microsoft Sam, Mike and Mary rebuilt in portable C (the
`engine` submodule), loaded as a shared library. It has to be built first;
this refuses to package a program that cannot make a sound.

Microsoft's voice files are never packaged. They are Microsoft's, and the
program reads them from where Windows installs them, from a `voices` folder
beside it, or from wherever it is pointed.
"""
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.abspath('.'))
from whistler import paths                                   # noqa: E402

block_cipher = None

# The engine. Everything the program does with sound goes through it, so a
# build without it is not worth making. Whichever way it was built -- make
# leaves libsam.dll, Visual Studio sam.dll -- it goes in under the name the
# program looks for.
built = paths.library()
if built is None:
    raise SystemExit('the engine is not built: python tools/build_engine.py '
                     '(git submodule update --init first, if engine/ is empty)')
os.makedirs('build', exist_ok=True)
lib = os.path.join('build', paths.LIBRARY)
shutil.copyfile(built, lib)

# Which commit this build is, so that a bug report can name one. From a
# checkout that is git; a source tarball leaves it out and the program says
# so rather than guessing.
stamp = os.path.join('build', 'build.txt')
try:
    said = subprocess.run(['git', 'log', '-1', '--format=%h %cd',
                           '--date=format:%Y-%m-%d'],
                          capture_output=True, text=True, timeout=10)
    text = said.stdout.strip() if said.returncode == 0 else ''
except Exception:
    text = ''
with open(stamp, 'w', encoding='utf-8') as fh:
    fh.write(text + chr(10))

a = Analysis(
    ['launch.py'],
    pathex=[os.path.abspath('.')],
    binaries=[(lib, '.')],
    datas=[(stamp, '.')],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'PIL', 'tkinter', 'pytest',
              'setuptools'],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WhistlerStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # a window, not a terminal
    disable_windowed_traceback=False,
)
# The same program again, built as a console program, so that a script can
# run it and wait for it: `whistler song.wst -o song.wav`. Windows decides
# whether a program has a console when it is built rather than when it is run,
# so one executable cannot be both -- a windowed program hands the shell its
# prompt back immediately and prints into nothing. Both start launch.py and
# the arguments decide what happens, so this is the same program under another
# name. Only on Windows: elsewhere a program prints to the terminal that
# started it whether it has a window or not, and the one executable does both.
cli = None
if sys.platform == 'win32':
    cli = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='whistler',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=True,
        disable_windowed_traceback=False,
    )

coll = COLLECT(
    exe,
    *([cli] if cli else []),
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='WhistlerStudio',
)

# On macOS, wrap it as a bundle so it is an application rather than a folder
# with a unix executable in it: double-clickable, its own Dock entry and menu
# bar. A `voices` folder beside the .app is looked in, so the voice files can
# be dropped next to it.
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='Whistler Studio.app',
        icon=None,
        bundle_identifier='com.github.retrobunn.whistler-studio',
        info_plist={
            'CFBundleName': 'Whistler Studio',
            'CFBundleDisplayName': 'Whistler Studio',
            'CFBundleShortVersionString': '0.1',
            'CFBundleVersion': '0.1',
            'NSHighResolutionCapable': True,
            # It only ever plays audio it has rendered itself.
            'LSApplicationCategoryType': 'public.app-category.music',
            'NSHumanReadableCopyright':
                'Sings with Microsoft Sam, Mike and Mary, whose voice files '
                'are not included.',
        },
    )
