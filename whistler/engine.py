#!/usr/bin/env python3
"""The engine the editor asks for pronunciations and audio.

A part is sung phrase by phrase: the notes between two rests go to the engine
together, and each phrase is placed where the score puts its first beat. The
engine itself fits every note's consonants and vowel around its beat and keeps
a long phrase on time (engine/src/sam_tts.h), so what is left to do here is
the mixing -- each part's level and pan, the reverb, the metronome -- and
keeping what has been rendered, so that playing the same thing twice renders
once.
"""
import bisect
import hashlib
import json          # only for the cache key
import math
import os
import shutil
import sys
import tempfile
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from whistler import libsam, paths, phonology                # noqa: E402
from whistler.song import clean_reverb, clean_voice, effect_name  # noqa: E402

SAMPLE_RATE = libsam.SAMPLE_RATE

#: What a note is sung at, and what the result is scaled back up by. Sung
#: notes run louder than speech, and a held vowel high in a voice's range can
#: go well past full scale, where the engine would clip it. Sung at a third
#: and scaled up here, in floating point, even the loudest note measured stays
#: whole; mixing turns the song down afterwards if it needs to.
SING_LEVEL = 1.0 / 3.0

#: how long after the last note the file runs on, so its decay is not clipped
TAIL_SECONDS = 0.4

#: The metronome. It is a ruler held up against the singing rather than part
#: of it, so it is mixed in only when the song is played and never written
#: into an exported file.
CLICK_HZ = 1000.0            # the beats
CLICK_ACCENT_HZ = 1600.0     # the first beat of each bar
CLICK_SECONDS = 0.035
CLICK_LEVEL = 0.22


def click(rate=SAMPLE_RATE, hz=CLICK_HZ, level=CLICK_LEVEL):
    """One tick: a tone that dies away immediately, so it reads as a tap."""
    n = int(rate * CLICK_SECONDS)
    t = np.arange(n, dtype=np.float32) / float(rate)
    return (level * np.sin(2 * np.pi * hz * t)
            * np.exp(-t * 45.0)).astype(np.float32)


def with_metronome(y, bpm, bar_beats, start=0.0, rate=SAMPLE_RATE):
    """The audio with a tick on every beat, accented at each bar line.

    `start` is the beat the audio itself begins on, so that playing from
    partway through a song still puts the ticks on the song's beats and the
    accents on its bar lines.
    """
    spb = 60.0 / max(bpm, 1e-6)
    plain, accent = click(rate), click(rate, CLICK_ACCENT_HZ,
                                       CLICK_LEVEL * 1.4)
    out = np.array(y, dtype=np.float32)
    n = out.shape[0]
    ticks = np.zeros(n, dtype=np.float32)
    beats = max(1, int(round(bar_beats)))             # keep 3/4, 6/8 and 7/8
    k = int(math.ceil(start - 1e-9))
    while True:
        at = int(round((k - start) * spb * rate))
        if at >= n:
            break
        tick = accent if (k % beats == 0) else plain
        end = min(at + len(tick), n)
        ticks[at:end] += tick[:end - at]
        k += 1
    out += ticks if out.ndim == 1 else ticks[:, None]
    peak = float(np.abs(out).max()) if n else 0.0
    if peak > 1.0:                        # the ticks must not push it into clip
        out /= peak
    return out


#: How finely a bend in motion is followed: every 5 ms, which is finer than
#: the engine's own pitch periods for any note a voice would sing.
BEND_STEP = 0.005


def glide(points, step=BEND_STEP):
    """Fill in between the written points so a bend moves rather than jumps.

    A bend is written down as the places it passes through, and the engine
    holds each value until the next one, so a slide has to be given as the
    small steps it takes. Only where a point says to slide: one that holds
    stays put until the next point arrives. (Filling in between every pair
    regardless is how a bend that finished on one note went on sliding into
    the next bend written anywhere later in the song.)
    """
    pts = [(t, v, bool(sl)) for t, v, sl in _triples(points)]
    if len(pts) < 2:
        return [(t, v) for t, v, _sl in pts]
    out = []
    for (t0, v0, slides), (t1, v1, _) in zip(pts, pts[1:]):
        out.append((t0, v0))
        if not slides or v1 == v0 or t1 - t0 <= step:
            continue                        # a hold needs nothing in between
        n = int((t1 - t0) / step)
        for k in range(1, n):
            f = k * step / (t1 - t0)
            out.append((t0 + k * step, v0 + (v1 - v0) * f))
    out.append((pts[-1][0], pts[-1][1]))
    return out


def _triples(points):
    """Accept points with or without the slide flag; without it, they hold."""
    for pt in points:
        if len(pt) >= 3:
            yield pt[0], pt[1], pt[2]
        else:
            yield pt[0], pt[1], False


def phrase_bend(curve, first, before, after):
    """The part of a bend one phrase needs, timed from its first beat.

    `curve` is [(seconds into the song, semitones)] as `glide` makes it;
    `before` and `after` say how far either side of the first beat the phrase
    reaches. Whatever value was in force as the phrase began is carried in
    ahead of it, or a phrase starting partway through a slide would begin on
    the wrong pitch.
    """
    if not curve:
        return None
    times = [t for t, _v in curve]
    lo = max(0, bisect.bisect_right(times, first - before) - 1)
    hi = bisect.bisect_right(times, first + after)
    part = curve[lo:hi] or curve[-1:]
    return [(t - first, v) for t, v in part]


def pan_gains(pan):
    """The left and right gains for a pan of -1 (hard left) to +1 (right).

    Constant power -- a track keeps its loudness as it moves across -- but
    normalised so that the middle is unity in both channels rather than the
    usual three decibels down, so a track left in the middle sounds the same
    in one channel or two.
    """
    theta = (max(-1.0, min(1.0, float(pan))) + 1.0) * (math.pi / 4.0)
    return (math.sqrt(2.0) * math.cos(theta),
            math.sqrt(2.0) * math.sin(theta))


def tracks_of(song):
    """A song's parts, whichever way it was written down: a single note to
    preview arrives as one voice and one list of notes."""
    parts = song.get('tracks')
    if parts:
        return parts
    return [{'singer': song.get('singer'), 'notes': song.get('notes') or [],
             'bends': song.get('bends') or []}]


def is_rest(phonemes):
    """A note nobody sings: no phonemes, or nothing but silence."""
    return not phonemes or all(p == phonology.REST for p in phonemes)


def phrases(entries):
    """[(start in beats, [note...])] between the rests, and the total length.

    The rests themselves are dropped -- they are not sung, they are the gaps
    the phrases are placed around.
    """
    runs, cur, start, at = [], [], 0.0, 0.0
    for e in entries:
        beats = float(e.get('beats', 0.5))
        if is_rest(e.get('phonemes')):
            if cur:
                runs.append((start, cur))
                cur = []
        else:
            if not cur:
                start = at
            cur.append(e)
        at += beats
    if cur:
        runs.append((start, cur))
    return runs, at


# -- the reverb ---------------------------------------------------------------

def room_response(room, rate=SAMPLE_RATE):
    """The reverb itself: for each side, noise dying away over the time the
    room sets, from a third of a second at 0 to three seconds at 100.

    The two sides are different noise, so the room spreads out around a voice
    in the middle rather than sitting on top of it; each is scaled to carry as
    much energy as what goes into it, so the wet setting alone says how much
    of the room is heard.
    """
    decay = 0.3 + 2.7 * max(0, min(100, room)) / 100.0      # seconds to -60 dB
    n = max(1, int(decay * rate))
    t = np.arange(n, dtype=np.float64) / rate
    envelope = np.power(10.0, -3.0 * t / decay)
    rng = np.random.default_rng(1)                          # the same room every time
    ir = rng.standard_normal((n, 2)) * envelope[:, None]
    soften = np.hanning(9)                                  # the highs go first
    soften /= soften.sum()
    ir = np.stack([np.convolve(ir[:, c], soften, mode='same')
                   for c in range(2)], axis=1)
    ir = np.concatenate([np.zeros((int(0.012 * rate), 2)), ir])  # the first wall
    ir /= np.sqrt((ir ** 2).sum(axis=0, keepdims=True))
    return ir.astype(np.float32)


def convolve(x, h):
    """x convolved with h, a block at a time through the FFT (overlap-add)."""
    n, m = len(x), len(h)
    out = np.zeros(n + m - 1, dtype=np.float64)
    if not n:
        return out.astype(np.float32)
    size = 4096
    while size < 2 * m:
        size <<= 1
    step = size - m + 1
    spectrum = np.fft.rfft(h, size)
    for at in range(0, n, step):
        seg = x[at:at + step]
        y = np.fft.irfft(np.fft.rfft(seg, size) * spectrum, size)
        k = len(seg) + m - 1
        out[at:at + k] += y[:k]
    return out.astype(np.float32)


def write_wav(path, y, sr=SAMPLE_RATE):
    """Write samples to a WAV: one column is mono, two columns are stereo."""
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    y = np.asarray(y, dtype=np.float32)
    pcm = (np.clip(y, -1.0, 1.0) * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(1 if y.ndim == 1 else y.shape[1])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def engine_name():
    return libsam.describe()


class Engine(object):
    def __init__(self, voice_folder=None):
        #: a folder chosen in the program, looked in before any other
        self.voice_folder = voice_folder or None
        self._data = None
        #: (voice, effect) -> an open voice. Changing a voice's effect can
        #: mean reloading it, so each combination a song uses is kept open.
        self._voices = {}
        self._rooms = {}
        #: key -> (seconds, peak). The audio itself lives in `cache_dir` under
        #: the key, never at the caller's path: callers reuse paths (the note
        #: preview always writes the same file), so an entry pointing at one
        #: would go on claiming a hit after a later render had overwritten it.
        self._cache = {}
        #: whether the last render ended early, for the caller to pass on;
        #: the engine has no limit on a phrase's length, so it never does
        self.stopped_short = False
        self.cache_dir = os.path.join(tempfile.gettempdir(), 'whistler-cache')

    # -- the voices ---------------------------------------------------------

    def data(self):
        """Which voices there are and where, looked for once."""
        if self._data is None:
            self._data = paths.find_voices(self.voice_folder)
        return self._data

    def voice(self, singer=None, effect='none'):
        """An open voice. One that is not here is sung by the first that is,
        so a song naming a voice this machine lacks still plays."""
        data = self.data()
        if not data.complete():
            raise RuntimeError('the voice files are not here: missing %s'
                               % ', '.join(paths.missing(self.voice_folder)))
        name = singer if data.spd(singer) else data.names()[0]
        key = (name.lower(), effect)
        v = self._voices.get(key)
        if v is None:
            v = libsam.Voice(data.spd(name), data.lexicon, data.letters)
            v.set_effect(effect)
            self._voices[key] = v
        return v

    def ping(self):
        """What is running, for the window to say out loud."""
        data = self.data()
        return {'engine': engine_name(),
                'python': '.'.join(str(v) for v in sys.version_info[:3]),
                'voices': len(data.voices), 'names': data.names(),
                'where': (os.path.dirname(data.voices[0][1])
                          if data.voices else '')}

    def voices(self):
        """Every voice found, Sam, Mike and Mary first."""
        return self.data().names()

    def phonemes(self, words):
        """{word: its phonemes}, "-" between syllables; [] for a word the
        dictionary cannot say."""
        v = self.voice()
        out = {}
        for w in words:
            clean = ''.join(c for c in w if c.isalpha() or c == "'")
            out[w] = v.pronounce(clean) if clean else []
        return out

    def palette(self):
        """Every phoneme, with a word it is heard in."""
        return ([[p, phonology.EXAMPLES[p]] for p in phonology.PHONES]
                + [[phonology.REST, 'silence, a rest']])

    def preview(self, phoneme, pitch=60, singer=None, beats=0.45, out=None):
        """Sing one phoneme on its own, for the picker's Preview button."""
        song = {'bpm': 120, 'singer': singer,
                'notes': [{'pitch': pitch, 'beats': beats,
                           'phonemes': [phoneme]}]}
        if out is None:
            out = os.path.join(tempfile.gettempdir(),
                               'whistler_preview_%s_%d.wav'
                               % (phoneme.replace('%', 'rest'), pitch))
        return self.render(song, out)

    # -- rendering ----------------------------------------------------------

    def render(self, song, out):
        # The metronome is mixed on afterwards and left out of the key, so
        # switching it on and off never sings the song again.
        metro = song.get('metronome') or None
        core = {k: v for k, v in song.items() if k != 'metronome'}
        key = hashlib.sha256(
            json.dumps(core, sort_keys=True).encode()).hexdigest()
        kept = os.path.join(self.cache_dir, key + '.wav')
        hit = self._cache.get(key)
        if hit is not None and os.path.isfile(kept):
            # a hit still has to reach the caller's file, or saving a song
            # that has already been played writes nothing and says it did
            seconds, peak = hit
            return {'seconds': seconds, 'peak': peak, 'cached': True,
                    'path': self._deliver(kept, out, metro, core)}

        y, peak = self._samples(core)
        seconds = len(y) / float(SAMPLE_RATE)
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            write_wav(kept, y)
            self._cache[key] = (seconds, peak)
            where = self._deliver(kept, out, metro, core)
        except OSError:                      # no cache: still give the caller
            write_wav(out, self._ticked(y, metro, core))   # the audio anyway
            where = out
        return {'seconds': seconds, 'peak': peak, 'path': where,
                'cached': False, 'stopped_short': self.stopped_short}

    @staticmethod
    def _ticked(y, metro, song):
        if not metro:
            return y
        return with_metronome(y, float(song.get('bpm', 120)),
                              float(metro.get('bar', 4)),
                              float(song.get('start', 0.0)))

    def _samples(self, song):
        """Mix every track of a song, and say how loud the result came out.

        Returns (samples, peak). The samples are one column if every track sits
        in the middle with no reverb on it, and two otherwise.

        Reverb is a property of the song that a part may take over. Parts are
        grouped by the reverb they end up with, each group mixed and
        reverberated on its own and the groups added together -- so two parts
        in the same room share its tail, and a part in a room of its own is not
        dragged into theirs. Panning moves the voices, not the room they are
        singing in, so each group goes into its reverb unpanned.
        """
        bpm = float(song.get('bpm', 120))
        consonants = float(song.get('consonants', 1.0))
        start = float(song.get('start', 0.0))
        early = song.get('anticipate', True)
        tracks = tracks_of(song)
        if not any(t.get('notes') for t in tracks):
            raise ValueError('nothing to sing')
        self.stopped_short = False
        song_reverb = clean_reverb(song.get('reverb'))
        groups = {}
        for t in tracks:
            y = self._track(t, bpm, consonants, start, early)
            left, right = pan_gains(t.get('pan', 0.0))
            own = t.get('reverb')
            rev = song_reverb if own is None else clean_reverb(own)
            groups.setdefault(rev, []).append((y, left, right))
        parts = [p for group in groups.values() for p in group]
        n = max(len(y) for y, _l, _r in parts)
        stereo = (any(abs(float(t.get('pan', 0.0))) > 1e-6 for t in tracks)
                  or any(wet > 0 for _room, wet in groups))
        if stereo:
            mixes = []
            for rev, group in groups.items():
                mix = np.zeros((n, 2), dtype=np.float32)
                room = np.zeros((n, 2), dtype=np.float32)   # the same, unpanned
                for y, gl, gr in group:
                    mix[:len(y), 0] += y * gl
                    mix[:len(y), 1] += y * gr
                    room[:len(y), 0] += y
                    room[:len(y), 1] += y
                mixes.append((rev, mix, room))
            # several voices at once can add up past full scale, and turning
            # the mix down is a great deal better than clipping it
            peak = float(np.abs(sum(m for _r, m, _q in mixes)).max()) if n else 0.0
            if peak > 1.0:
                for _rev, mix, room in mixes:
                    mix /= peak
                    room /= peak
            done = []
            for rev, mix, room in mixes:
                # the room is given the group unpanned and the panning is
                # added back afterwards at the dry level, so a part sung hard
                # left is answered by a room all round it, not one also hard
                # left
                out = np.array(self._reverberate(room, rev))
                out[:n] += (mix - room) * (1.0 - rev[1] / 100.0)
                done.append(out)
            out = np.zeros((max(len(d) for d in done), 2), dtype=np.float32)
            for d in done:
                out[:len(d)] += d
            return out, peak
        out = np.zeros(n, dtype=np.float32)
        for y, gl, _gr in parts:          # in the middle both gains are one
            out[:len(y)] += y * gl
        peak = float(np.abs(out).max()) if n else 0.0
        if peak > 1.0:
            # the caller is told the number, so it can say why the song got
            # quieter rather than leave someone wondering
            out /= peak
        return out, peak

    def _reverberate(self, mix, reverb):
        """One group's mix in its room: the dry part at what is left of the
        wet, and the room's own tail after it, trimmed where it falls silent."""
        room, wet = reverb
        if wet <= 0 or not len(mix):
            return mix
        ir = self._rooms.get(room)
        if ir is None:
            ir = self._rooms[room] = room_response(room)
        w = wet / 100.0
        out = np.zeros((len(mix) + len(ir) - 1, 2), dtype=np.float32)
        out[:len(mix)] = mix * (1.0 - w)
        for c in range(2):
            out[:, c] += w * convolve(mix[:, c], ir[:, c])
        loud = np.abs(out).max(axis=1) > (1.0 / 32767.0)
        last = int(np.nonzero(loud)[0][-1]) + 1 if loud.any() else len(mix)
        return out[:max(len(mix), last)]

    def _track(self, track, bpm, consonants, start=0.0, early=True):
        """One track's audio, phrase by phrase, laid out on the beat.

        Each run of notes between two rests is one call to the engine, placed
        so that the beat it reports for the first note falls where the score
        puts it. The silence before a phrase is what its first consonants may
        be sung into.

        `start` is where playing begins, in beats. A phrase that is over by
        then is not sung at all; one already under way is sung whole and has
        its beginning cut off, so a note the cursor lands in the middle of is
        heard from the middle rather than started again.
        """
        spb = 60.0 / max(bpm, 1e-6)
        controls = clean_voice(track.get('voice'))
        voice = self.voice(track.get('singer'), effect_name(controls['effect']))
        # the notes go in at SING_LEVEL, and come back up to the track's level
        level = float(track.get('volume', 1.0)) / SING_LEVEL / 32768.0
        detune = controls['detune'] / 100.0
        own = track.get('consonants')
        if own is not None:
            try:
                consonants = float(own)
            except (TypeError, ValueError):
                pass
        # [(beat, semitones, slides into the next)] in the song's own time, by
        # time alone: two points may share a moment -- that is how a bend that
        # steps rather than slides is written -- and sorting on the whole
        # point would put those two in order of value instead
        points = sorted(_triples(track.get('bends') or []),
                        key=lambda point: point[0])
        curve = glide([(t * spb, v, sl) for t, v, sl in points])
        runs, total = phrases(track.get('notes') or [])
        out = np.zeros(int(round((max(0.0, total - start) * spb + TAIL_SECONDS)
                                 * SAMPLE_RATE)), dtype=np.float32)
        was_over = 0.0                   # the beat the phrase before ended on
        for at, run in runs:
            beats = [float(e.get('beats', 0.5)) for e in run]
            span = sum(beats)
            room = (at - was_over) * spb
            was_over = at + span
            if (at + span) * spb + TAIL_SECONDS <= start * spb:
                continue                 # over and done with before the cursor
            notes = [(phonology.singable(e.get('phonemes')), b * spb,
                      int(e['pitch']) + detune, SING_LEVEL,
                      bool(k and e.get('join')))
                     for k, (e, b) in enumerate(zip(run, beats))]
            first = at * spb
            samples, pos = voice.sing(
                notes, consonants=consonants, lead=room if early else 0.0,
                portamento=controls['portamento'] / 1000.0,
                vibrato=controls['vibrato'],
                vibrato_rate=controls['vibrato_rate'] / 10.0,
                bend=phrase_bend(curve, first, room + 1.0, span * spb + 2.0),
                on_beat=not early)
            y = samples.astype(np.float32) * level
            i = int(round((at - start) * spb * SAMPLE_RATE)) - pos[0][0]
            if i < 0:                     # the phrase began before the cursor
                y = y[-i:]
                i = 0
            if not len(y):
                continue
            if i + len(y) > len(out):
                out = np.concatenate(
                    [out, np.zeros(i + len(y) - len(out), dtype=np.float32)])
            out[i:i + len(y)] += y
        return out

    @classmethod
    def _deliver(cls, kept, out, metro=None, song=None):
        """Put the audio where the caller asked, and say where it ended up.

        Windows refuses to write a file that something else has open, and the
        thing most likely to have this one open is the player that just played
        it. Rather than fail the whole render over that, the caller is handed
        the copy in the cache, which is the same audio.
        """
        try:
            if metro:
                with wave.open(kept) as w:
                    channels = w.getnchannels()
                    y = (np.frombuffer(w.readframes(w.getnframes()), '<i2')
                         .astype(np.float32) / 32768.0)
                if channels > 1:
                    y = y.reshape(-1, channels)
                write_wav(out, cls._ticked(y, metro, song or {}))
            elif os.path.abspath(kept) != os.path.abspath(out):
                shutil.copyfile(kept, out)
            return out
        except OSError:
            return kept

    def close(self):
        for v in self._voices.values():
            v.close()
        self._voices = {}


if __name__ == '__main__':
    # a quick look at the engine from the command line
    eng = Engine()
    print(engine_name())
    print('voices:', ', '.join(eng.voices()))
    print('daisy:', eng.phonemes(['daisy']))
