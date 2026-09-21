#!/usr/bin/env python3
"""Where the engine library and Microsoft's voice files are.

The voices are not this program's to hand out. Sam, Mike and Mary are
Microsoft's, and the engine reads them from wherever they were installed --
which, on a Windows machine that has the SAPI 5.1 voices, is two folders under
Common Files: the voices in one and the dictionary and letter-to-sound rules
in the other. They can also be put in a folder of their own and chosen in the
program, or dropped into `voices` beside it.

The library is this program's own. It is built from the `engine` submodule,
so it is in that submodule's build folder when running from source and beside
the executable in a packaged build.
"""
import os
import sys

#: The voices offered first, in this order. Any other voice file found -- a
#: Microsoft Anna built with the engine's annavoice tools, say -- comes after.
KNOWN = ('Sam', 'Mike', 'Mary')

#: the dictionary and the letter-to-sound rules every voice shares
LEXICON = 'LTTS1033.LXA'
LETTERS = 'r1033tts.LXA'

LIBRARY = {'win32': 'libsam.dll',
           'darwin': 'libsam.dylib'}.get(sys.platform, 'libsam.so')


def frozen():
    return getattr(sys, 'frozen', False)


def source_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def program_dir():
    """The folder the program is in: the executable's in a build, the
    checkout's otherwise."""
    if frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return source_root()


def bundled(*parts):
    """A file belonging to this program: inside a build's bundle, or in the
    checkout."""
    if frozen():
        base = getattr(sys, '_MEIPASS', None) or program_dir()
    else:
        base = source_root()
    return os.path.join(base, *parts)


# -- the library ---------------------------------------------------------------

def library_candidates():
    """Where the engine library may be, nearest first."""
    env = os.environ.get('WHISTLER_LIBSAM')
    if env:
        yield env
    if frozen():
        yield os.path.join(program_dir(), LIBRARY)
        inside = getattr(sys, '_MEIPASS', None)
        if inside:
            yield os.path.join(inside, LIBRARY)
    build = os.path.join(source_root(), 'engine', 'build')
    yield os.path.join(build, LIBRARY)                  # make: MinGW, macOS, Linux
    if sys.platform == 'win32':
        yield os.path.join(build, 'x64', 'sam.dll')     # src\build.bat: MSVC


def library():
    """The engine library, or None when it has not been built."""
    for path in library_candidates():
        if os.path.isfile(path):
            return path
    return None


# -- the voices ----------------------------------------------------------------

def _common_files():
    out = []
    for var in ('CommonProgramFiles(x86)', 'CommonProgramFiles',
                'CommonProgramW6432'):
        value = os.environ.get(var)
        if value and value not in out:
            out.append(value)
    return out


def voice_folders(chosen=None):
    """Where voices may be, nearest first: the folder chosen in the program,
    then WHISTLER_VOICES, then `voices` beside the program, then the places
    SAPI 5 installs them."""
    out = [f for f in (chosen, os.environ.get('WHISTLER_VOICES'),
                       os.path.join(program_dir(), 'voices')) if f]
    for common in _common_files():
        out.append(os.path.join(common, 'SpeechEngines', 'Microsoft', 'TTS',
                                '1033'))
        out.append(os.path.join(common, 'Microsoft Shared', 'Speech', '1033'))
        out.append(os.path.join(common, 'Microsoft Shared', 'Speech'))
    unique, seen = [], set()
    for folder in out:
        key = os.path.normcase(os.path.abspath(folder))
        if key not in seen:
            seen.add(key)
            unique.append(folder)
    return unique


def _listing(folder):
    """{lower-case name: name as it is} for a folder, {} if it cannot be read.

    Files keep whatever case they were installed with -- Sam.spd sits beside
    MARY.SPD, and the dictionary is ltts1033.lxa -- so they are matched without
    regard to it, which on a case-sensitive file system is not free.
    """
    try:
        return dict((n.lower(), n) for n in os.listdir(folder))
    except OSError:
        return {}


def _find(folder, name):
    real = _listing(folder).get(name.lower())
    path = os.path.join(folder, real) if real else None
    return path if path and os.path.isfile(path) else None


def _lexicon_folders(folder):
    """Where a voice folder's dictionary may be: beside the voices, in their
    1033 folder, or -- as SAPI 5.1 lays them out -- in the Lexicon folder next
    to the TTS one."""
    yield folder
    yield os.path.join(folder, '1033')
    yield os.path.normpath(os.path.join(folder, '..', '..', 'Lexicon', '1033'))
    for common in _common_files():
        yield os.path.join(common, 'SpeechEngines', 'Microsoft', 'Lexicon',
                           '1033')


class VoiceData(object):
    """What was found: [(name, .spd file)], the two dictionary files, and
    every folder that was looked in, for saying where when nothing was."""

    def __init__(self, voices, lexicon, letters, looked):
        self.voices = voices
        self.lexicon = lexicon
        self.letters = letters
        self.looked = looked

    def complete(self):
        return bool(self.voices and self.lexicon and self.letters)

    def names(self):
        return [name for name, _path in self.voices]

    def spd(self, name):
        """The voice file for a name, however it is capitalised; None if
        there is no such voice."""
        for known, path in self.voices:
            if known.lower() == (name or '').lower():
                return path
        return None


def find_voices(chosen=None):
    """Every voice in every folder worth looking in, and the dictionary."""
    voices, lexicon, letters, looked = [], None, None, []
    for folder in voice_folders(chosen):
        looked.append(folder)
        listing = _listing(folder)
        found = [listing[k] for k in sorted(listing) if k.endswith('.spd')]
        if not found:
            continue
        for real in found:
            stem = os.path.splitext(real)[0]
            name = next((k for k in KNOWN if k.lower() == stem.lower()), stem)
            if not any(n.lower() == name.lower() for n, _p in voices):
                voices.append((name, os.path.join(folder, real)))
        if lexicon is None:
            for place in _lexicon_folders(folder):
                lx, lt = _find(place, LEXICON), _find(place, LETTERS)
                if lx and lt:
                    lexicon, letters = lx, lt
                    break
    rank = dict((k.lower(), i) for i, k in enumerate(KNOWN))
    voices.sort(key=lambda v: (rank.get(v[0].lower(), len(KNOWN)),
                               v[0].lower()))
    return VoiceData(voices, lexicon, letters, looked)


def missing(chosen=None):
    """What is absent, as things to tell someone. Empty when all is here."""
    out = []
    if not library():
        out.append('the engine library, %s (python tools/build_engine.py '
                   'builds it)' % LIBRARY)
    data = find_voices(chosen)
    if not data.voices:
        out.append('a voice: Sam.spd, Mike.spd or Mary.spd')
    if not data.lexicon:
        out.append(LEXICON)
    if not data.letters:
        out.append(LETTERS)
    return out
