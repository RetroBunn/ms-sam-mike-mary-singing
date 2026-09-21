#!/usr/bin/env python3
"""Build the library the program sings with: engine/build/libsam.dll (or
.dylib, or .so).

    python tools/build_engine.py

It runs the engine's own Makefile, so how the engine is built stays the
engine's business: gcc from MinGW on Windows, cc anywhere else. On a Windows
machine with Visual Studio and no MinGW it runs the engine's build.bat
instead, which leaves sam.dll in engine/build/x64; the program looks there
too.
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(ROOT, 'engine')
EXT = {'win32': 'dll', 'darwin': 'dylib'}.get(sys.platform, 'so')


def with_make():
    makes = ('mingw32-make', 'make') if sys.platform == 'win32' else ('make',)
    make = next((m for m in makes if shutil.which(m)), None)
    cc = 'gcc' if sys.platform == 'win32' else os.environ.get('CC', 'cc')
    if not make or not shutil.which(cc):
        return None
    # made here rather than by the Makefile's "mkdir -p", which a Windows
    # make without a Unix shell would run as two folders called -p and build
    os.makedirs(os.path.join(ENGINE, 'build'), exist_ok=True)
    cmd = [make, '-C', ENGINE, 'CC=' + cc, 'SOEXT=' + EXT, 'build/libsam.' + EXT]
    print(' '.join(cmd))
    return subprocess.call(cmd)


def with_msvc():
    script = os.path.join(ENGINE, 'src', 'build.bat')
    vswhere = os.path.join(os.environ.get('ProgramFiles(x86)', ''),
                           'Microsoft Visual Studio', 'Installer', 'vswhere.exe')
    if sys.platform != 'win32' or not os.path.isfile(vswhere):
        return None
    print(script, 'x64')
    return subprocess.call(['cmd', '/c', script, 'x64'])


def main():
    if not os.path.isfile(os.path.join(ENGINE, 'Makefile')):
        print('the engine folder is empty: git submodule update --init '
              'fetches it (GitHub Desktop does this when it clones)')
        return 1
    rc = with_make()
    if rc is None:
        rc = with_msvc()
    if rc is None:
        print('no C compiler found: install MinGW-w64 (gcc) or Visual Studio '
              'Build Tools on Windows, Xcode command line tools on a Mac, or '
              'gcc and make on Linux')
        return 1
    if rc == 0:
        sys.path.insert(0, ROOT)
        from whistler import paths
        print('built: %s' % paths.library())
    return rc


if __name__ == '__main__':
    sys.exit(main())
