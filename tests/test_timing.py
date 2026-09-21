"""Notes have to land where the score puts them.

The engine can only start a note on a frame boundary -- 220 samples, 4.99 ms
-- and it takes a note's length as `floor(beats * frames per beat)`. Asking it
for each note's own length therefore loses part of a frame every time, always
downwards, and a phrase slides forward off the beat: 210 ms by the end of one
phrase of a real song. So the renderer asks for the frames that put the *next*
note where it belongs, and the error stays at half a frame and stays there.

Nothing here needs the synthesiser: what is checked is the arithmetic that
decides what the engine is asked for.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ppc import render
from ppc.midi import Note

HALF_A_FRAME = 0.5 / render.FRAMES_A_SECOND * 1000.0       # 2.49 ms


class Recorder(object):
    """An engine that only writes down what it was asked to sing."""

    def __init__(self):
        self.beats = []

    def note(self, _midi, _next, _velocity, beats):
        self.beats.append(beats)

    def frames(self, bpm):
        """What the engine would make of those lengths, note by note."""
        import math
        fpb = render.frames_per_beat(render.engine_tempo(bpm))
        return [int(math.floor(b * fpb)) for b in self.beats]


def sung(beats, bpm, phonemes=('d', 'AA')):
    """Where each note actually begins, in seconds, and where it should."""
    r = render.Renderer(program=0, bpm=bpm)
    r._begin()
    eng = Recorder()
    for b in beats:
        r._note_call(eng, Note(60, b, list(phonemes)))
    frames = eng.frames(bpm)
    at, got = 0, []
    for f in frames:
        got.append(at / render.FRAMES_A_SECOND)
        at += f
    want, t = [], 0.0
    for b in beats:
        want.append(t)
        t += b * 60.0 / bpm
    return got, want


class FramesPerBeatTests(unittest.TestCase):
    def test_it_is_the_engine_s_own_arithmetic(self):
        # SetTempo: 12027.2727273 / (tempoMul * bpm) / 240, in single
        # precision. At 115 that is 104.585 frames, not 104.
        self.assertAlmostEqual(render.frames_per_beat(115), 104.5850, places=3)
        self.assertAlmostEqual(render.frames_per_beat(60), 200.4545, places=3)
        # a beat is frames a second times seconds a beat, whatever the tempo
        for bpm in (10, 60, 97, 115, 120, 250):
            self.assertAlmostEqual(
                render.frames_per_beat(bpm),
                render.FRAMES_A_SECOND * 60.0 / bpm, places=2)

    def test_the_tempo_the_engine_is_set_to_is_a_whole_one_in_range(self):
        self.assertEqual(render.engine_tempo(115.4), 115)
        self.assertEqual(render.engine_tempo(115.6), 116)
        self.assertEqual(render.engine_tempo(4), 10)
        self.assertEqual(render.engine_tempo(900), 250)


class PlacementTests(unittest.TestCase):
    def worst(self, beats, bpm, phonemes=('d', 'AA')):
        got, want = sung(beats, bpm, phonemes)
        return max(abs(a - b) for a, b in zip(got, want)) * 1000.0

    def test_a_long_phrase_of_equal_notes_does_not_slide(self):
        # the case that drifts worst: the same length every time, so the same
        # part of a frame is lost every time
        for bpm in (97, 115, 120, 132):
            self.assertLess(self.worst([1.0] * 96, bpm), HALF_A_FRAME + 0.01,
                            'a phrase at %d bpm slid off the beat' % bpm)

    def test_the_lengths_a_song_is_actually_written_in(self):
        beats = [0.25, 0.25, 0.5, 0.75, 0.125, 1.0, 0.375, 2.0] * 12
        for bpm in (97, 115, 143):
            self.assertLess(self.worst(beats, bpm), HALF_A_FRAME + 0.01)

    def test_lengths_that_are_not_round_at_all(self):
        # what anticipating the consonants leaves behind
        beats = [0.4913, 0.2571, 1.3329, 0.6667, 0.1041] * 20
        self.assertLess(self.worst(beats, 115), HALF_A_FRAME + 0.01)

    def test_a_note_is_never_shorter_than_one_frame(self):
        r = render.Renderer(program=0, bpm=115)
        r._begin()
        eng = Recorder()
        for _ in range(8):
            r._note_call(eng, Note(60, 0.0, ['AA']))
        self.assertTrue(all(f >= 1 for f in eng.frames(115)), eng.frames(115))

    def test_the_clock_starts_again_for_the_next_phrase(self):
        r = render.Renderer(program=0, bpm=115)
        r._begin()
        eng = Recorder()
        for _ in range(4):
            r._note_call(eng, Note(60, 1.0, ['d', 'AA']))
        first = list(eng.beats)
        r._begin()
        eng2 = Recorder()
        for _ in range(4):
            r._note_call(eng2, Note(60, 1.0, ['d', 'AA']))
        self.assertEqual(first, eng2.beats)


if __name__ == '__main__':
    unittest.main()
