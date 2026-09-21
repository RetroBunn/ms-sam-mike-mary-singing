#!/usr/bin/env python3
"""Sam's phonemes: which are vowels, where syllables divide, and VocalWriter's
phonemes said in Sam's.

The engine speaks the SAPI 5 American English phone set: forty sounds written
in lower case, `aa` as in father to `zh` as in pleasure, with `1` or `2` after
a vowel that carries primary or secondary stress and `-` between syllables.
The dictionary gives words in exactly that form, so a word looked up comes
back already divided: "daisy" is `d ey 1 - z iy`.
"""

PHONES = ('aa', 'ae', 'ah', 'ao', 'aw', 'ax', 'ay', 'b', 'ch', 'd', 'dh', 'eh',
          'er', 'ey', 'f', 'g', 'h', 'ih', 'iy', 'jh', 'k', 'l', 'm', 'n', 'ng',
          'ow', 'oy', 'p', 'r', 's', 'sh', 't', 'th', 'uh', 'uw', 'v', 'w', 'y',
          'z', 'zh')
PHONE_SET = frozenset(PHONES)
VOWELS = frozenset(('aa', 'ae', 'ah', 'ao', 'aw', 'ax', 'ay', 'eh', 'er', 'ey',
                    'ih', 'iy', 'ow', 'oy', 'uh', 'uw'))
STRESS = ('1', '2')
SYLLABLE = '-'

#: The phoneme that is silence. A note holding nothing else is a rest.
REST = '%'

#: A word for each, from SAPI's own table of the phone set; the capitals are
#: the sound.
EXAMPLES = {
    'aa': 'fAther', 'ae': 'cAt', 'ah': 'cUt', 'ao': 'dOg', 'aw': 'fOUl',
    'ax': 'Ago', 'ay': 'bIte', 'b': 'Big', 'ch': 'CHin', 'd': 'Dig',
    'dh': 'THen', 'eh': 'pEt', 'er': 'fUR', 'ey': 'Ate', 'f': 'Fork',
    'g': 'Gut', 'h': 'Help', 'ih': 'fIll', 'iy': 'fEEl', 'jh': 'Joy',
    'k': 'Cut', 'l': 'Lid', 'm': 'Mat', 'n': 'No', 'ng': 'siNG', 'ow': 'gO',
    'oy': 'tOY', 'p': 'Put', 'r': 'Red', 's': 'Sit', 'sh': 'SHe', 't': 'Talk',
    'th': 'THin', 'uh': 'bOOk', 'uw': 'tOO', 'v': 'Vat', 'w': 'With',
    'y': 'Yard', 'z': 'Zap', 'zh': 'pleaSure',
}

#: VocalWriter's fifty-seven phonemes in Sam's terms, for bringing in a
#: VocalWriter Studio project or a MIDI file VocalWriter exported. Each was
#: matched by the example word VocalWriter itself gives it: UX is "bUd", so it
#: is Sam's `ah`; OH is the vowel of "bOy" on its own, `ao`. The r-coloured
#: vowels and the syllabic consonants are two of Sam's phonemes: AR ("bAR") is
#: `aa r`, EN ("buttON") is `ax n`. Sam has no flap and no glottal stop, and
#: says "better" with a `t` itself, so the flaps and stops of beTTer, iT and
#: greaTer are `t`.
FROM_VOCALWRITER = {
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
    FROM_VOCALWRITER[_c] = [_c]


def from_vocalwriter(phonemes):
    """A VocalWriter note's phonemes as Sam's. Anything neither program knows
    is left out rather than guessed at; `unknown_vocalwriter` names it."""
    out = []
    for sym in phonemes or ():
        mapped = FROM_VOCALWRITER.get(sym) or FROM_VOCALWRITER.get(sym.upper())
        if mapped:
            out.extend(mapped)
        elif sym.lower() in PHONE_SET:
            out.append(sym.lower())
    return out


def unknown_vocalwriter(phonemes):
    """The symbols `from_vocalwriter` could not place."""
    return [s for s in phonemes or ()
            if not (FROM_VOCALWRITER.get(s) or FROM_VOCALWRITER.get(s.upper())
                    or s.lower() in PHONE_SET)]


def singable(phonemes):
    """A note's phonemes as the engine takes them: Sam's, in lower case, with
    any of VocalWriter's said in Sam's and anything else left out -- so a
    symbol typed wrong cannot stop a whole song rendering. A stress mark stays
    where it is, after its vowel; silence goes, since a rest is a note."""
    out = []
    for sym in phonemes or ():
        if sym in STRESS or sym == SYLLABLE:
            if out:
                out.append(sym)
            continue
        low = sym.lower()
        if low in PHONE_SET:
            out.append(low)
        else:
            out.extend(p for p in from_vocalwriter([sym]) if p != REST)
    return out


def is_nucleus(sym):
    """Whether a phoneme is a vowel: what a note's length is spent on."""
    return sym in VOWELS


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
