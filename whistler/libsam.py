#!/usr/bin/env python3
"""The engine, spoken to through ctypes.

libsam is the `engine` submodule built as a shared library: Microsoft Sam,
Mike and Mary in portable C, with the singing interface this program asks for
(engine/src/sam_tts.h). ctypes needs nothing compiled on this side, so a
checkout runs as soon as the library is built.
"""
import ctypes as C
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whistler import paths                                   # noqa: E402

#: what the Microsoft voices are recorded at, and so what everything is mixed at
SAMPLE_RATE = 22050

NOTE_JOIN = 1         # the note carries on the word of the one before it
SING_ON_BEAT = 1      # consonants on the beat rather than before it
SING_STEPPED = 2      # no blending between frames


class Note(C.Structure):
    _fields_ = [('phones', C.c_char_p), ('seconds', C.c_double),
                ('pitch', C.c_double), ('volume', C.c_float),
                ('flags', C.c_int)]


class SingOpts(C.Structure):
    _fields_ = [('consonants', C.c_float), ('lead', C.c_double),
                ('portamento', C.c_float), ('vibrato', C.c_float),
                ('vibrato_rate', C.c_float),
                ('bend', C.POINTER(C.c_double)), ('nbend', C.c_int),
                ('flags', C.c_int)]


class NotePos(C.Structure):
    _fields_ = [('beat', C.c_int64), ('vowel', C.c_int64)]


AUDIO = C.CFUNCTYPE(C.c_int, C.POINTER(C.c_int16), C.c_size_t, C.c_void_p)
EVENT = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p)


class Callbacks(C.Structure):
    _fields_ = [('audio', AUDIO), ('event', EVENT), ('user', C.c_void_p)]


_lib = None
_where = None
#: why the library could not be loaded, once it has been tried
REASON = ''


def load():
    """The library, loaded once. Raises OSError saying why it cannot be."""
    global _lib, _where, REASON
    if _lib is not None:
        return _lib
    path = paths.library()
    if not path:
        REASON = 'it has not been built: python tools/build_engine.py builds it'
        raise OSError('the engine library, %s: %s' % (paths.LIBRARY, REASON))
    try:
        lib = C.CDLL(path)
        lib.sam_tts_open_files.restype = C.c_void_p
        lib.sam_tts_open_files.argtypes = [C.c_char_p, C.c_char_p, C.c_char_p,
                                           C.c_char_p, C.c_size_t]
        lib.sam_tts_close.restype = None
        lib.sam_tts_close.argtypes = [C.c_void_p]
        lib.sam_tts_set_effect.restype = C.c_int
        lib.sam_tts_set_effect.argtypes = [C.c_void_p, C.c_char_p]
        lib.sam_tts_sample_rate.restype = C.c_int
        lib.sam_tts_sample_rate.argtypes = [C.c_void_p]
        lib.sam_tts_pronounce.restype = C.c_int
        lib.sam_tts_pronounce.argtypes = [C.c_void_p, C.c_char_p, C.c_char_p,
                                          C.c_size_t]
        lib.sam_tts_phonemes.restype = C.c_int
        lib.sam_tts_phonemes.argtypes = [C.c_int, C.c_char_p, C.c_size_t]
        lib.sam_tts_sing_notes.restype = C.c_int
        lib.sam_tts_sing_notes.argtypes = [
            C.c_void_p, C.POINTER(Note), C.c_int, C.POINTER(SingOpts),
            C.POINTER(Callbacks), C.POINTER(NotePos)]
    except AttributeError as exc:
        # a library built before the engine could sing
        REASON = 'it is too old to sing (%s); build it again' % exc
        raise OSError('the engine library at %s: %s' % (path, REASON))
    except OSError as exc:
        REASON = str(exc)
        raise OSError('the engine library at %s could not be loaded: %s'
                      % (path, exc))
    _lib, _where = lib, path
    return lib


def available():
    try:
        load()
        return True
    except OSError:
        return False


def describe():
    """Which engine this is, for the window and --version to say."""
    if available():
        return 'libsam (Microsoft Sam, Mike and Mary), %s' % _where
    return 'libsam: %s' % REASON


def phonemes(vowels=False):
    """The phonemes a note can be sung with, as the engine lists them -- or,
    with `vowels`, the vowels among them. Needs no voice."""
    buf = C.create_string_buffer(1024)
    if load().sam_tts_phonemes(1 if vowels else 0, buf, len(buf)) < 0:
        raise OSError('the engine would not list its phonemes')
    return tuple(buf.value.decode('ascii').split())


def _fs(path):
    """A path as the library's fopen wants it: on Windows, in the ANSI code
    page, or as its short name when it holds a character that page lacks."""
    path = os.path.abspath(path)
    if sys.platform != 'win32':
        return os.fsencode(path)
    try:
        return path.encode('mbcs', 'strict')
    except UnicodeEncodeError:
        buf = C.create_unicode_buffer(32768)
        if C.windll.kernel32.GetShortPathNameW(path, buf, len(buf)):
            return buf.value.encode('mbcs', 'replace')
        raise


class Voice(object):
    """One voice, opened from its files: what every call goes through."""

    def __init__(self, spd, lexicon, letters):
        lib = load()
        err = C.create_string_buffer(512)
        self._h = lib.sam_tts_open_files(_fs(spd), _fs(lexicon), _fs(letters),
                                         err, len(err))
        if not self._h:
            raise OSError('%s: %s' % (os.path.basename(spd),
                                      err.value.decode('utf-8', 'replace')
                                      or 'it could not be opened'))
        self.rate = lib.sam_tts_sample_rate(self._h)
        self.effect = 'none'

    def set_effect(self, name):
        """One of the SAPI 4 voice modes, by the engine's name for it."""
        if name == self.effect:
            return
        if load().sam_tts_set_effect(self._h, name.encode('ascii')) != 0:
            raise ValueError('there is no effect called %r' % name)
        self.effect = name

    def pronounce(self, word):
        """The dictionary's phonemes for one word, "-" between syllables."""
        buf = C.create_string_buffer(1024)
        n = load().sam_tts_pronounce(self._h, word.encode('utf-8'), buf,
                                     len(buf))
        return buf.value.decode('ascii', 'replace').split() if n > 0 else []

    def sing(self, notes, consonants=1.0, lead=0.0, portamento=0.0,
             vibrato=0.0, vibrato_rate=0.0, bend=None, on_beat=False,
             stepped=False):
        """Sing one phrase. `notes` are (phonemes, seconds, MIDI pitch,
        volume, joins the word before); `bend` is [(seconds from the first
        beat, semitones)], each holding until the next.

        Returns (samples as int16, [(beat, vowel)]): where each note's beat
        falls in the samples, and where its vowel began.
        """
        lib = load()
        n = len(notes)
        arr = (Note * n)()
        kept = []                 # the phoneme strings must outlive the call
        for i, (phonemes, seconds, pitch, volume, join) in enumerate(notes):
            text = ' '.join(phonemes).encode('ascii', 'replace')
            kept.append(text)
            arr[i].phones = text
            arr[i].seconds = float(seconds)
            arr[i].pitch = float(pitch)
            arr[i].volume = float(volume)
            arr[i].flags = NOTE_JOIN if join else 0
        opts = SingOpts()
        opts.consonants = float(consonants)
        opts.lead = max(0.0, float(lead))
        opts.portamento = float(portamento)
        opts.vibrato = float(vibrato)
        opts.vibrato_rate = float(vibrato_rate)
        opts.flags = ((SING_ON_BEAT if on_beat else 0)
                      | (SING_STEPPED if stepped else 0))
        if bend:
            flat = [float(x) for point in bend for x in point]
            opts.bend = (C.c_double * len(flat))(*flat)
            opts.nbend = len(bend)
        chunks = []

        def heard(pcm, count, _user):
            chunks.append(C.string_at(pcm, count * 2))
            return 0

        cb = Callbacks(AUDIO(heard), EVENT(), None)
        pos = (NotePos * n)()
        rc = lib.sam_tts_sing_notes(self._h, arr, n, C.byref(opts),
                                    C.byref(cb), pos)
        if rc < 0:
            raise ValueError('the engine would not sing that phrase')
        samples = np.frombuffer(b''.join(chunks), dtype='<i2')
        return samples, [(int(p.beat), int(p.vowel)) for p in pos]

    def close(self):
        if self._h:
            load().sam_tts_close(self._h)
            self._h = None

    def __del__(self):
        try:
            self.close()
        except Exception:                                    # noqa: BLE001
            pass
