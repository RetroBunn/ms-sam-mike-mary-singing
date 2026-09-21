#!/usr/bin/env python3
"""VocalWriter's phonemes said in Sam's, for bringing in what VocalWriter
Studio and VocalWriter left behind.

Only the importers use this: File > Import VWS, and a MIDI file VocalWriter
exported, which carries its phonemes. Everywhere else a note holds the
engine's own phonemes and nothing else (whistler/phonology.py), and the note
editor does not take VocalWriter's.

Each of VocalWriter's fifty-seven phonemes was matched by the example word
VocalWriter itself gives it: UX is "bUd", so it is Sam's `ah`; OH is the
vowel of "bOy" on its own, `ao`. The r-coloured vowels and the syllabic
consonants are two of Sam's phonemes: AR ("bAR") is `aa r`, EN ("buttON") is
`ax n`. Sam has no flap and no glottal stop, and says "better" with a `t`
itself, so the flaps and stops of beTTer, iT and greaTer are `t`.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whistler.phonology import REST                          # noqa: E402

TO_SAM = {
    'AE': ['ae'], 'AA': ['aa'], 'AX': ['ax'], 'AO': ['ao'], 'EH': ['eh'],
    'IH': ['ih'], 'UX': ['ah'], 'EY': ['ey'], 'AY': ['ay'], 'IY': ['iy'],
    'UW': ['uw'], 'UH': ['uh'], 'OW': ['ow'], 'AW': ['aw'], 'OY': ['oy'],
    'YU': ['y', 'uw'], 'ER': ['er'], 'AR': ['aa', 'r'], 'XR': ['eh', 'r'],
    'IR': ['ih', 'r'], 'OR': ['ao', 'r'], 'UR': ['uh', 'r'], 'OH': ['ao'],
    'O': ['ao'], 'LX': ['l'], 'EL': ['ax', 'l'], 'EN': ['ax', 'n'],
    'IX': ['ax'], 'RX': ['er'], 'DX': ['t'], 'DD': ['t'], 'TX': ['t'],
    'Q': ['t'], 'QX': ['t'], 'CH': ['ch'], 'DH': ['dh'], 'JH': ['jh'],
    'NG': ['ng'], 'SH': ['sh'], 'TH': ['th'], 'ZH': ['zh'], REST: [REST],
}
#: the single letters are the same sound in both
for _c in 'bdfghklmnprstvwyz':
    TO_SAM[_c] = [_c]


def _mapped(sym):
    return TO_SAM.get(sym) or TO_SAM.get(sym.upper())


def to_sam(symbols):
    """A VocalWriter note's phonemes in Sam's. A symbol VocalWriter did not
    have either is left out rather than guessed at; `unknown` names it."""
    out = []
    for sym in symbols or ():
        out.extend(_mapped(sym) or ())
    return out


def unknown(symbols):
    """The symbols `to_sam` could not place."""
    return [s for s in symbols or () if not _mapped(s)]
