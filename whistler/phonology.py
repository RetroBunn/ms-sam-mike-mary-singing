#!/usr/bin/env python3
"""Sam's phonemes: which there are and which are vowels, both as the engine
lists them, and where syllables divide.

The phonemes are the engine's own -- asked of it once (`libsam.phonemes`),
never a list kept here -- so the program uses exactly what the engine
provides: the SAPI 5 American English set, forty sounds in lower case, `aa`
as in father to `zh` as in pleasure. A vowel may have `1` or `2` after it for
primary or secondary stress, and `-` divides syllables. The dictionary gives
words in that same form: "daisy" is `d ey 1 - z iy`.

Nothing here knows VocalWriter's phonemes. Those are said in Sam's only when
a VocalWriter Studio project or a MIDI file VocalWriter exported is brought
in; see app/vocalwriter.py.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whistler import libsam                                  # noqa: E402

STRESS = ('1', '2')
SYLLABLE = '-'

#: The phoneme that is silence. A note holding nothing else is a rest.
REST = '%'

#: A word each phoneme is heard in, for the picker -- SAPI's own examples.
#: The phonemes come from the engine; these only describe them, and one the
#: engine lists that is not here is offered without a word, not left out.
EXAMPLES = {
    'aa': 'father', 'ae': 'cat', 'ah': 'cut', 'ao': 'dog', 'aw': 'foul',
    'ax': 'ago', 'ay': 'bite', 'b': 'big', 'ch': 'chin', 'd': 'dig',
    'dh': 'then', 'eh': 'pet', 'er': 'fur', 'ey': 'ate', 'f': 'fork',
    'g': 'gut', 'h': 'help', 'ih': 'fill', 'iy': 'feel', 'jh': 'joy',
    'k': 'cut', 'l': 'lid', 'm': 'mat', 'n': 'no', 'ng': 'sing', 'ow': 'go',
    'oy': 'toy', 'p': 'put', 'r': 'red', 's': 'sit', 'sh': 'she',
    't': 'talk', 'th': 'thin', 'uh': 'book', 'uw': 'too', 'v': 'vat',
    'w': 'with', 'y': 'yard', 'z': 'zap', 'zh': 'pleasure',
}

_engine = None


def _asked():
    """(phonemes, vowels) as the engine lists them, asked for once."""
    global _engine
    if _engine is None:
        _engine = (libsam.phonemes(), frozenset(libsam.phonemes(vowels=True)))
    return _engine


def all_phonemes():
    """Every phoneme a note can be sung with, in the engine's own order."""
    return _asked()[0]


def vowels():
    """The engine's vowels: the sounds a note's length is spent on."""
    return _asked()[1]


def is_nucleus(sym):
    """Whether a phoneme is a vowel."""
    return sym in vowels()


def clean(phonemes):
    """Phonemes as someone typed them, kept to the engine's: each of its own
    in the lower case it spells them in, a stress mark after the vowel it
    belongs to, and the rest sign for a rest. A syllable division means
    nothing inside one note, so it goes quietly. Anything else -- a
    VocalWriter phoneme such as UX or AR included -- is not the engine's.

    Returns (phonemes, what was left out), so that a note only ever holds what
    the engine has, and whoever typed it can be told what went.
    """
    known, vowel = set(all_phonemes()), vowels()
    out, left = [], []
    for sym in phonemes or ():
        if sym == SYLLABLE:
            continue
        if sym == REST:
            out.append(REST)
        elif sym in STRESS:
            if out and out[-1] in vowel:
                out.append(sym)
            else:
                left.append(sym)
        elif sym.lower() in known:
            out.append(sym.lower())
        else:
            left.append(sym)
    return out, left


def singable(phonemes):
    """A note's phonemes as the engine takes them: `clean`'s, so a symbol
    typed wrong cannot stop a whole song rendering, and without the rest sign,
    since a rest is a note of its own."""
    return [p for p in clean(phonemes)[0] if p != REST]


#: Consonants that can follow another one at the start of a syllable: the
#: liquids and glides, as in "cra-", "blue", "twin", "few".
GLIDES = frozenset(('l', 'r', 'w', 'y'))

#: What /s/ can be followed by, as in "spy", "sty", "sky", "small", "snow".
AFTER_S = frozenset(('p', 't', 'k', 'm', 'n', 'f'))


def legal_onset(syms):
    """Could this run of consonants begin an English syllable?

    One consonant always can. Two can when the second is a liquid or glide, or
    when the first is /s/. Three can when the first is /s/ and the other two
    could stand alone, which is what allows "str-" and "spl-".
    """
    if len(syms) <= 1:
        return True
    if len(syms) == 2:
        return syms[1] in GLIDES or (syms[0] == 's' and syms[1] in AFTER_S)
    if len(syms) == 3 and syms[0] == 's':
        return legal_onset(syms[1:])
    return False


def syllabify(phonemes):
    """Split a word's phonemes into syllables, one group per vowel.

    A word from the dictionary carries its own divisions, `-`, and those are
    used as they are. Without them the consonants between two vowels go to the
    second syllable as far as they legally can -- the maximum onset principle,
    which puts the /s/ of "bicycle" on "cy" rather than on "bi". A stress mark
    stays with the vowel before it. A word with one vowel, or none, comes back
    as a single group.
    """
    syms = list(phonemes)
    if SYLLABLE in syms:
        out, cur = [], []
        for sym in syms:
            if sym == SYLLABLE:
                if cur:
                    out.append(cur)
                cur = []
            else:
                cur.append(sym)
        if cur:
            out.append(cur)
        return out
    nuclei = [i for i, s in enumerate(syms) if is_nucleus(s)]
    if len(nuclei) < 2:
        return [syms] if syms else []
    cuts = []
    for a, b in zip(nuclei, nuclei[1:]):
        first = a + 1
        while first < b and syms[first] in STRESS:
            first += 1
        run = syms[first:b]              # the consonants between two vowels
        take = 0                         # how many of them open the next one
        while take < len(run) and legal_onset(run[len(run) - take - 1:]):
            take += 1
        cuts.append(b - take)
    out, start = [], 0
    for c in cuts:
        out.append(syms[start:c])
        start = c
    out.append(syms[start:])
    return [g for g in out if g]


def regroup(phonemes, count):
    """Divide a word into exactly `count` notes, as evenly as it allows.

    Syllables are kept whole and shared out as evenly as they go, so asking a
    three-syllable word for two notes gives two syllables then one rather than
    breaking a syllable in half. Asking for more notes than there are
    syllables gives one per syllable.
    """
    parts = syllabify(phonemes)
    count = max(1, min(int(count), len(parts)))
    if count == len(parts):
        return parts
    out, at = [], 0
    for k in range(count):
        take = (len(parts) - at) // (count - k)
        group = []
        for p in parts[at:at + take]:
            group.extend(p)
        out.append(group)
        at += take
    return out
