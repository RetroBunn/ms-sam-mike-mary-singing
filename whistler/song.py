#!/usr/bin/env python3
"""What a song says about how it is sung: which voice sings each part, that
voice's controls, the reverb, and the names of pitches. Nothing here needs the
engine, so the song model and the dialogs can use it freely."""

#: who sings a part that has not been given anyone
DEFAULT_SINGER = 'Sam'

#: The SAPI 4 voice modes the engine rebuilds, as (the engine's name, what the
#: program calls it). A song keeps the position in this list, so a new one
#: goes on the end. Monotone is not here: a sung note says its own pitch, so
#: flattening it would do nothing at all.
EFFECTS = (('none', 'None'), ('hall', 'Hall'), ('stadium', 'Stadium'),
           ('space', 'Space'), ('room', 'Room'), ('whisper', 'Whisper'),
           ('robosoft1', 'RoboSoft One'), ('robosoft2', 'RoboSoft Two'),
           ('robosoft3', 'RoboSoft Three'), ('robosoft4', 'RoboSoft Four'),
           ('robosoft5', 'RoboSoft Five'), ('robosoft6', 'RoboSoft Six'))

#: The voice controls a part can have, as
#: (key, choices, default, low, high, label, hint). A control with choices is
#: picked from that list and holds a position in it; the rest are numbers.
#: Every default is what the engine does when it is told nothing, so a song
#: that sets none of them is Sam as Sam sings.
VOICE_CONTROLS = (
    ('vibrato', None, 0, 0, 100, 'Vibrato depth',
     'cents either side of the note; 0 for none'),
    ('vibrato_rate', None, 55, 10, 100, 'Vibrato rate',
     'tenths of a hertz: 55 wavers five and a half times a second'),
    ('portamento', None, 0, 0, 500, 'Portamento',
     'milliseconds to slide into each new pitch; 0 goes straight there'),
    ('detune', None, 0, -100, 100, 'Detune', 'cents sharp or flat'),
    ('effect', tuple(label for _name, label in EFFECTS), 0, 0,
     len(EFFECTS) - 1, 'Effect', 'a SAPI 4 voice mode: a hall, a robot, a '
     'whisper'),
)

#: {key: default}
VOICE_DEFAULTS = dict((k, d) for k, _c, d, _lo, _hi, _l, _h in VOICE_CONTROLS)


def clean_voice(values):
    """Voice controls with only the known keys, each a whole number in range."""
    out = {}
    for key, _choices, default, lo, hi, _label, _hint in VOICE_CONTROLS:
        try:
            v = int((values or {}).get(key, default))
        except (TypeError, ValueError):
            v = default
        out[key] = max(lo, min(hi, v))
    return out


def effect_name(index):
    """The engine's name for the effect at that place in the list."""
    try:
        return EFFECTS[int(index)][0]
    except (IndexError, TypeError, ValueError):
        return 'none'


#: a room of 40 with 24% of it heard: VocalWriter's own defaults, which are as
#: good a starting point as any
DEFAULT_REVERB = (40, 24)


def clean_reverb(values):
    """(room, wet) as whole percentages, clamped. None is no reverb at all.

    Two numbers: the room sets how long the reverb takes to die away, and the
    wet is how much of it is heard, the dry part being what is left.
    """
    if not values:
        return (0, 0)
    try:
        room = int(round(float(values.get('room', DEFAULT_REVERB[0]))))
        wet = int(round(float(values.get('wet', DEFAULT_REVERB[1]))))
    except (AttributeError, TypeError, ValueError):
        return (0, 0)
    return (max(0, min(100, room)), max(0, min(100, wet)))


NOTE_NAMES = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}


def parse_pitch(tok):
    """A MIDI number, or a name like C4 / F#3 / Bb5."""
    tok = tok.strip()
    if not tok:
        raise ValueError('empty pitch')
    if tok.lstrip('-').isdigit():
        return int(tok)
    step = NOTE_NAMES.get(tok[0].lower())
    if step is None:
        raise ValueError('bad pitch %r' % tok)
    i = 1
    while i < len(tok) and tok[i] in '#b':
        step += 1 if tok[i] == '#' else -1
        i += 1
    return 12 * (int(tok[i:]) + 1) + step
