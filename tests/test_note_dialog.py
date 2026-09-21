"""The note editor works on a copy: nothing reaches the song but OK.

The dialog is made but never shown. Where there is no desktop to make one on,
the test skips itself.
"""
import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import project


class NoteDialogTests(unittest.TestCase):
    def setUp(self):
        try:
            import wx
            from app import studio
            self.app = wx.GetApp() or wx.App(False)
            self.studio = studio
        except Exception as exc:                             # noqa: BLE001
            self.skipTest('no desktop for a dialog: %s' % exc)
        self.window = SimpleNamespace(say=lambda text: None, singable=lambda: [])

    def test_hearing_a_change_and_cancelling_leaves_the_note_alone(self):
        live = project.Note(['d', 'ey', '1'], 60, 1.0, 'day', [(0.0, 0.0),
                                                              (1.0, 2.0)])
        dlg = self.studio.NoteDialog(None, self.window, live)
        try:
            dlg.phon.SetValue('g ow 1')
            dlg.pitch.SetValue('C5')
            dlg.bend_end.SetValue('-3')
            # what Preview note and Bend points take the fields as
            heard = dlg.result()
            self.assertEqual((heard.phonemes, heard.pitch, heard.bend[-1]),
                             (['g', 'ow', '1'], 72, (1.0, -3.0)))
            # the song's note has not been touched
            self.assertEqual((live.phonemes, live.pitch, live.bend),
                             (['d', 'ey', '1'], 60, [(0.0, 0.0), (1.0, 2.0)]))
            # and there is one copy, so a bend edited point by point on it is
            # still there when OK hands it back
            self.assertIs(dlg.result(), heard)
        finally:
            dlg.Destroy()


if __name__ == '__main__':
    unittest.main()
