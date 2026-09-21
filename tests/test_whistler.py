"""Sam's side of things: the phonemes, the song file, finding the voices, and
singing.

Everything down to EngineTests runs anywhere. EngineTests sings for real, so
it needs the engine library built (python tools/build_engine.py) and
Microsoft's voice files, and it skips itself on a machine without them.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import project
from whistler import paths, phonology, song

#: VocalWriter's own phoneme table, all fifty-seven, and the one name its
#: palette spells differently
VOCALWRITER = ('IY IH EH AE AA UX AO UH AX ER EY AY OY AW OW UW YU IR XR AR OR '
               'UR IX % RX LX EL EN w y r l h m n NG f v TH DH s z SH ZH p b t '
               'd k g CH JH TX Q QX DD O OH').split()


class PhonologyTests(unittest.TestCase):
    def test_a_dictionary_word_divides_where_the_dictionary_says(self):
        self.assertEqual(phonology.syllabify('d ey 1 - z iy'.split()),
                         [['d', 'ey', '1'], ['z', 'iy']])
        self.assertEqual(phonology.syllabify('b ay 1 - s ih 2 k - ax l'.split()),
                         [['b', 'ay', '1'], ['s', 'ih', '2', 'k'], ['ax', 'l']])

    def test_without_divisions_the_next_syllable_takes_what_it_can(self):
        # "bicycle": the s opens "cy"; "twinkle": ng cannot open a syllable
        # with k, so it stays behind, and the stress mark stays with its vowel
        self.assertEqual(phonology.syllabify('b ay s ih k ax l'.split()),
                         [['b', 'ay'], ['s', 'ih'], ['k', 'ax', 'l']])
        self.assertEqual(phonology.syllabify('t w ih 1 ng k ax l'.split()),
                         [['t', 'w', 'ih', '1', 'ng'], ['k', 'ax', 'l']])
        self.assertEqual(phonology.syllabify(['s', 't', 'aa', 'r']),
                         [['s', 't', 'aa', 'r']])

    def test_regroup_keeps_syllables_whole(self):
        word = 'b ay 1 - s ih 2 k - ax l'.split()
        self.assertEqual(phonology.regroup(word, 2),
                         [['b', 'ay', '1'], ['s', 'ih', '2', 'k', 'ax', 'l']])
        self.assertEqual(len(phonology.regroup(word, 9)), 3)

    def test_every_vocalwriter_phoneme_becomes_sam_s(self):
        for sym in VOCALWRITER:
            got = phonology.from_vocalwriter([sym])
            self.assertTrue(got, sym)
            for p in got:
                self.assertTrue(p in phonology.PHONE_SET or p == phonology.REST,
                                '%s became %r' % (sym, got))
        self.assertEqual(phonology.unknown_vocalwriter(VOCALWRITER), [])

    def test_the_ones_that_needed_thinking_about(self):
        cases = {'UX': ['ah'], 'OH': ['ao'], 'AR': ['aa', 'r'],
                 'EN': ['ax', 'n'], 'YU': ['y', 'uw'], 'DD': ['t'],
                 'IX': ['ax'], 'EY': ['ey'], 'CH': ['ch'], 'y': ['y']}
        for sym, want in cases.items():
            self.assertEqual(phonology.from_vocalwriter([sym]), want, sym)
        self.assertEqual(phonology.from_vocalwriter(['g', 'I', 'v']), ['g', 'v'])
        self.assertEqual(phonology.unknown_vocalwriter(['g', 'I', 'v']), ['I'])

    def test_what_the_engine_is_given(self):
        # Sam's own, lower-cased; VocalWriter's said in Sam's; nonsense and
        # silence left out; a stress mark kept after its vowel
        self.assertEqual(phonology.singable(['D', 'EY', '1', 'zz', 'UX', '%']),
                         ['d', 'ey', '1', 'ah'])
        self.assertEqual(phonology.singable(['1', 'aa']), ['aa'])


class SongSettingsTests(unittest.TestCase):
    def test_voice_controls_are_kept_in_range(self):
        got = song.clean_voice({'vibrato': 900, 'detune': -500, 'effect': 99,
                                'colour': 3})
        self.assertEqual(got['vibrato'], 100)
        self.assertEqual(got['detune'], -100)
        self.assertEqual(got['effect'], len(song.EFFECTS) - 1)
        self.assertNotIn('colour', got)
        self.assertEqual(song.clean_voice(None), song.VOICE_DEFAULTS)

    def test_effects_by_place(self):
        self.assertEqual(song.effect_name(0), 'none')
        self.assertEqual(song.effect_name(1), 'hall')
        self.assertEqual(song.effect_name(99), 'none')

    def test_pitch_names(self):
        self.assertEqual(song.parse_pitch('C4'), 60)
        self.assertEqual(song.parse_pitch('F#3'), 54)
        self.assertEqual(song.parse_pitch('Bb5'), 82)
        self.assertEqual(song.parse_pitch('67'), 67)


class VoiceFolderTests(unittest.TestCase):
    """Laid out the way the SAPI 5.1 voices install, capitals and all."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.tts = os.path.join(self.root, 'Microsoft', 'TTS', '1033')
        lex = os.path.join(self.root, 'Microsoft', 'Lexicon', '1033')
        for folder, names in ((self.tts, ['Sam.spd', 'Sam.sdf', 'MARY.SPD']),
                              (lex, ['ltts1033.lxa', 'R1033TTS.LXA'])):
            os.makedirs(folder)
            for name in names:
                open(os.path.join(folder, name), 'wb').close()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_the_voices_and_the_dictionary_beside_them_are_found(self):
        data = paths.find_voices(self.tts)
        self.assertEqual(data.spd('Sam'), os.path.join(self.tts, 'Sam.spd'))
        self.assertEqual(data.spd('mary'), os.path.join(self.tts, 'MARY.SPD'))
        self.assertEqual(os.path.basename(data.lexicon), 'ltts1033.lxa')
        self.assertEqual(os.path.basename(data.letters), 'R1033TTS.LXA')
        self.assertEqual(data.names()[:1], ['Sam'])
        self.assertIn('Mary', data.names())
        self.assertIsNone(data.spd('Nobody'))


class SongFileTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_a_song_comes_back_as_it_went(self):
        notes = [project.Note(['d', 'ey', '1'], 69, 3, 'daisy', [(0, 0), (1, 2)]),
                 project.Note(['z', 'iy'], 66, 3, '')]
        tracks = [project.Track(name='Lead', singer='Mary', volume=80, pan=-30,
                                notes=notes, voice={'effect': 1}),
                  project.Track(name='Low', singer='Mike', reverb=(60, 30))]
        path = os.path.join(self.dir, 'song.wst')
        project.save(path, 150, tracks, (3, 4), 0.8, {'vibrato': 25},
                     (40, 24), False)
        with open(path, encoding='utf-8') as fh:
            doc = json.load(fh)
        self.assertEqual((doc['format'], doc['version']), (project.FORMAT, 1))
        bpm, docs, sig, con, voice, rev, early = project.load(path)
        back = project.tracks_from(docs)
        self.assertEqual((bpm, sig, con, rev, early), (150, (3, 4), 0.8,
                                                       (40, 24), False))
        self.assertEqual(voice['vibrato'], 25)
        self.assertEqual([(t.name, t.singer, t.volume, t.pan) for t in back],
                         [('Lead', 'Mary', 80, -30), ('Low', 'Mike', 100, 0)])
        self.assertEqual(back[0].voice['effect'], 1)
        self.assertEqual(back[1].reverb, (60, 30))
        self.assertEqual([(n.phonemes, n.pitch, n.beats, n.word, n.bend)
                          for n in back[0].notes],
                         [(n.phonemes, n.pitch, n.beats, n.word, n.bend)
                          for n in notes])

    def vws(self, **doc):
        path = os.path.join(self.dir, 'old.vws')
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(dict({'format': project.VWS_FORMAT, 'version': 2,
                            'bpm': 100}, **doc), fh)
        return path

    def test_open_turns_a_vocalwriter_project_away_with_the_way_in(self):
        path = self.vws(tracks=[{'name': 'V', 'notes': []}])
        with self.assertRaises(ValueError) as caught:
            project.load(path)
        self.assertIn('Import VWS', str(caught.exception))

    def test_a_vocalwriter_project_is_brought_in(self):
        path = self.vws(
            time_signature=[3, 4], consonants=0.7, voice={'color': 80},
            reverb={'room': 40, 'wet': 24},
            tracks=[{'name': 'Lead', 'program': 3, 'voice_id': 40,
                     'volume': 70, 'pan': 25, 'mute': True,
                     'voice': {'chorus': 20}, 'consonants': 0.5,
                     'notes': [{'phonemes': ['d', 'EY'], 'pitch': 69,
                                'beats': 1.5, 'word': 'daisy'},
                               {'phonemes': ['z', 'IY'], 'pitch': 65,
                                'beats': 1.5, 'word': ''},
                               {'phonemes': ['%'], 'pitch': 60, 'beats': 1},
                               {'phonemes': ['b', 'AR'], 'pitch': 60,
                                'beats': 1, 'word': 'bar',
                                'bend': [[0, 0], [1, -2]]}]}])
        (bpm, docs, sig, con, voice, rev, early), said = project.import_vws(path)
        t = project.tracks_from(docs)[0]
        self.assertEqual((bpm, sig, con, rev), (100, (3, 4), 0.7, (40, 24)))
        self.assertEqual((t.name, t.singer, t.volume, t.pan, t.mute,
                          t.consonants, t.voice), ('Lead', 'Sam', 70, 25, True,
                                                   0.5, None))
        self.assertEqual(voice, song.VOICE_DEFAULTS)
        self.assertEqual([n.phonemes for n in t.notes],
                         [['d', 'ey'], ['z', 'iy'], ['%'], ['b', 'aa', 'r']])
        self.assertEqual(t.notes[3].bend, [(0.0, 0.0), (1.0, -2.0)])
        self.assertTrue(any('voice controls' in line for line in said))

    def test_a_whistler_song_is_not_imported_as_vocalwriter(self):
        path = os.path.join(self.dir, 'song.wst')
        project.save(path, 120, [project.Track(name='V')])
        with self.assertRaises(ValueError):
            project.import_vws(path)


def _can_sing():
    try:
        from whistler import libsam
        return libsam.available() and paths.find_voices().complete()
    except Exception:                                        # noqa: BLE001
        return False


@unittest.skipUnless(_can_sing(), 'needs the engine library and the voices')
class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from whistler.engine import Engine, SAMPLE_RATE
        cls.eng, cls.rate = Engine(), SAMPLE_RATE

    def notes(self, *words):
        out = []
        for text, pitches in words:
            ph = self.eng.phonemes([text])[text]
            groups = phonology.regroup(ph, len(pitches))
            out += [project.Note(g, p, 1.0, text if i == 0 else '')
                    for i, (g, p) in enumerate(zip(groups, pitches))]
        return out

    def test_the_dictionary(self):
        self.assertEqual(self.eng.phonemes(['daisy'])['daisy'],
                         ['d', 'ey', '1', '-', 'z', 'iy'])
        self.assertEqual(self.eng.voices()[:1], ['Sam'])

    def test_a_phrase_after_a_rest_starts_on_its_beat(self):
        # two beats of rest at 120, then "star": its s and t are sung into the
        # rest and its vowel lands on the beat, one second in
        v = self.eng.voice()
        samples, pos = v.sing([(['s', 't', 'aa', '1', 'r'], 1.0, 60, 1 / 3.0,
                                False)], lead=1.0)
        vowel = (pos[0][1] - pos[0][0]) / float(self.rate)
        self.assertLess(abs(vowel), 0.005)
        song_ = project.song_dict(120, [project.Track(notes=[
            project.Note(['%'], 60, 2.0)] + self.notes(('star', [60])))])
        y, _peak = self.eng._samples(song_)
        onset = next(i for i, s in enumerate(y) if abs(s) > 1e-3) / float(self.rate)
        self.assertTrue(0.8 < onset < 1.0, onset)       # the consonants, early

    def test_the_same_song_sings_the_same(self):
        s = project.song_dict(100, [project.Track(
            notes=self.notes(('daisy', [69, 65]), ('daisy', [62, 57])))])
        a, _ = self.eng._samples(s)
        b, _ = self.eng._samples(s)
        self.assertEqual(len(a), len(b))
        self.assertTrue((a == b).all())

    def test_a_file_is_written_at_the_voice_s_rate(self):
        import wave
        out = os.path.join(tempfile.mkdtemp(), 'x.wav')
        res = self.eng.render(project.song_dict(120, [project.Track(
            singer='Mary', notes=self.notes(('go', [72])))]), out)
        with wave.open(res['path']) as w:
            self.assertEqual(w.getframerate(), self.rate)
        self.assertGreater(res['seconds'], 0.5)

    def test_an_effect_leaves_its_echoes(self):
        plain = project.Track(notes=self.notes(('go', [60])))
        hall = project.Track(notes=self.notes(('go', [60])), voice={'effect': 1})
        a, _ = self.eng._samples(project.song_dict(120, [plain]))
        b, _ = self.eng._samples(project.song_dict(120, [hall]))
        self.assertGreater(len(b), len(a))


if __name__ == '__main__':
    unittest.main()
