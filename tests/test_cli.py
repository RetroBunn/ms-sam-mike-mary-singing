"""The command line, and the song it builds.

Nothing here needs the synthesiser: what is checked is the reading of the
arguments and the dictionary the engine is handed, which is the part that
would quietly diverge from the window's.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import cli, project


def track(name='Voice 1', **kw):
    kw.setdefault('notes', [project.Note(['d', 'ey', '1'], 67, 1.0, 'day')])
    return project.Track(name=name, **kw)


class ArgumentTests(unittest.TestCase):
    def parse(self, *argv):
        return cli.build_parser().parse_args(list(argv))

    def test_a_file_on_its_own_is_a_window_not_a_job(self):
        self.assertFalse(cli.wants_console(self.parse('song.wst')))
        self.assertFalse(cli.wants_console(self.parse()))
        for job in (['song.wst', '-o', 'out.wav'], ['song.wst', '--tracks', 'd'],
                    ['old.vws', '--save', 'x.wst'], ['--list-voices'],
                    ['--version'], ['--pronounce', 'daisy']):
            self.assertTrue(cli.wants_console(self.parse(*job)), job)

    def test_the_kind_of_file_is_told_by_its_ending(self):
        self.assertTrue(cli.is_vws('old.VWS'))
        self.assertTrue(cli.is_midi('tune.mid'))
        self.assertFalse(cli.is_vws('song.wst') or cli.is_midi('song.wst'))

    def test_the_overrides_are_read(self):
        args = self.parse('song.wst', '-o', 'out.wav', '--tempo', '96',
                          '--consonants', '40', '--from', '8',
                          '--track', 'Lead', '--track', 'Bass',
                          '--no-anticipate')
        self.assertEqual(args.file, 'song.wst')
        self.assertEqual(args.output, 'out.wav')
        self.assertEqual((args.tempo, args.consonants, args.start), (96, 40, 8))
        self.assertEqual(args.track, ['Lead', 'Bass'])
        self.assertIs(args.anticipate, False)

    def test_anticipation_says_nothing_unless_it_is_asked_about(self):
        self.assertIsNone(self.parse('song.wst').anticipate)
        self.assertIs(self.parse('song.wst', '--anticipate').anticipate, True)

    def test_reverb(self):
        self.assertEqual(cli.parse_reverb('40,24'), (40, 24))
        self.assertEqual(cli.parse_reverb('40 24'), (40, 24))
        for wrong in ('40', '40,24,8', '400,4', 'loud,soft', ''):
            with self.assertRaises(ValueError):
                cli.parse_reverb(wrong)


class VoiceTests(unittest.TestCase):
    # Sam, Mike and Mary, and two voices built with the engine's annavoice
    NAMES = ['Sam', 'Mike', 'Mary', 'Anna', 'Anna 2']

    def test_by_name_by_number_and_by_the_beginning_of_a_name(self):
        self.assertEqual(cli.find_voice('Mary', self.NAMES), 2)
        self.assertEqual(cli.find_voice('mary', self.NAMES), 2)
        self.assertEqual(cli.find_voice('ma', self.NAMES), 2)
        self.assertEqual(cli.find_voice('1', self.NAMES), 1)
        # a name in full beats a name that is only the start of another
        self.assertEqual(cli.find_voice('Anna', self.NAMES), 3)

    def test_what_it_refuses(self):
        for wrong in ('an', 'nosuch', '99'):
            with self.assertRaises(ValueError):
                cli.find_voice(wrong, self.NAMES)


class TrackChoiceTests(unittest.TestCase):
    def setUp(self):
        self.tracks = [track('Lead'), track('Bass'), track('Choir')]

    def test_everything_when_nothing_is_asked_for(self):
        self.assertEqual(cli.chosen_tracks(self.tracks, []), self.tracks)

    def test_by_name_and_by_number_in_the_song_s_own_order(self):
        got = cli.chosen_tracks(self.tracks, ['Choir', '1'])
        self.assertEqual([t.name for t in got], ['Lead', 'Choir'])

    def test_a_name_that_is_not_there(self):
        with self.assertRaises(ValueError):
            cli.chosen_tracks(self.tracks, ['Drums'])


class SongTests(unittest.TestCase):
    """What the engine is handed. The window builds this same dictionary."""

    def test_volume_and_pan_go_out_as_fractions(self):
        song = project.song_dict(120, [track(volume=50, pan=-100)])
        part = song['tracks'][0]
        self.assertEqual((part['volume'], part['pan']), (0.5, -1.0))

    def test_a_part_with_no_voice_controls_is_sung_with_the_song_s(self):
        mine = {'vibrato': 30}
        song = project.song_dict(120, [track(), track('Own', voice=mine)],
                                 voice={'vibrato': 10})
        self.assertEqual(song['tracks'][0]['voice'], {'vibrato': 10})
        # a track's own controls arrive filled out, since a Track cleans them
        self.assertEqual(song['tracks'][1]['voice']['vibrato'], 30)

    def test_a_note_with_nothing_on_it_is_a_rest(self):
        song = project.song_dict(120, [track(notes=[project.Note()])])
        self.assertEqual(song['tracks'][0]['notes'][0]['phonemes'],
                         [project.REST])

    def test_each_part_says_who_sings_it(self):
        song = project.song_dict(120, [track(), track('Alto', singer='Mary')])
        self.assertEqual([p['singer'] for p in song['tracks']],
                         ['Sam', 'Mary'])

    def test_the_notes_of_one_word_are_joined(self):
        # Add Word writes the word on its first note; a MIDI lyric broken over
        # notes ends in a hyphen; a rest joins nothing
        notes = [project.Note(['d', 'ey', '1'], 60, 1, 'daisy'),
                 project.Note(['z', 'iy'], 60, 1, ''),
                 project.Note(['%'], 60, 1, ''),
                 project.Note(['k', 'ah', '1', 'n'], 60, 1, 'coun-'),
                 project.Note(['t', 'r', 'iy'], 60, 1, 'try'),
                 project.Note(['g', 'ow', '1'], 60, 1, 'go')]
        song = project.song_dict(120, [track(notes=notes)])
        self.assertEqual([n['join'] for n in song['tracks'][0]['notes']],
                         [False, True, False, False, True, False])

    def test_the_reverb_and_the_consonants_are_the_song_s(self):
        song = project.song_dict(90, [track()], consonants=0.4,
                                 reverb=(40, 24), anticipate=False, start=8)
        self.assertEqual(song['bpm'], 90.0)
        self.assertEqual(song['consonants'], 0.4)
        self.assertEqual(song['reverb'], {'room': 40, 'wet': 24})
        self.assertIs(song['anticipate'], False)
        self.assertEqual(song['start'], 8.0)


class ExportTests(unittest.TestCase):
    def test_no_two_tracks_write_the_same_file(self):
        jobs = project.export_jobs([track('Choir'), track('Choir'),
                                    track('', notes=[])], 'out', 'song')
        self.assertEqual([os.path.basename(p) for _t, p in jobs],
                         ['song - Choir.wav', 'song - Choir 2.wav'])

    def test_a_name_a_file_cannot_have(self):
        jobs = project.export_jobs([track('Lead: 1/2')], 'out', 'song')
        self.assertEqual(os.path.basename(jobs[0][1]), 'song - Lead- 1-2.wav')


class PronounceTests(unittest.TestCase):
    def test_a_word_the_dictionary_knows_and_one_it_does_not(self):
        rows = [[([], 60, 1.0, 'daisy', []), ([], 62, 1.0, 'zzzq', [])]]
        pending = [(0, 'daisy', [0]), (0, 'zzzq', [1])]
        out, got = project.pronounce(
            rows, pending, {'daisy': ['d', 'ey', '1', '-', 'z', 'iy']})
        self.assertEqual(got, 1)
        # on one note the syllables run together; the division is not sung
        self.assertEqual(out[0][0][0], ['d', 'ey', '1', 'z', 'iy'])
        self.assertEqual(out[0][1][0], [project.DEFAULT_PHONEME])

    def test_a_word_over_two_notes_divides_where_the_dictionary_does(self):
        rows = [[([], 60, 1.0, 'dai-', []), ([], 62, 1.0, 'sy', [])]]
        out, _got = project.pronounce(
            rows, [(0, 'daisy', [0, 1])],
            {'daisy': ['d', 'ey', '1', '-', 'z', 'iy']})
        self.assertEqual([r[0] for r in out[0]],
                         [['d', 'ey', '1'], ['z', 'iy']])


if __name__ == '__main__':
    unittest.main()
