#!/usr/bin/env python3
"""The engine, in this process, answering on a worker thread.

A render is fast, not instant -- Sam sings a minute of song in a small
fraction of a second, but a fraction of a second of a frozen window is the
difference between an interface that answers and one that stutters. So
requests go on a queue, they are answered in the order they were asked, and
the answer arrives in a callback; whoever asked hands it back to the window
with `wx.CallAfter`.
"""
import os
import queue
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from whistler.engine import Engine as Synthesiser            # noqa: E402


class Engine(object):
    """What the window asks, answered on the worker thread."""

    def __init__(self, on_error=None, voice_folder=None):
        self.on_error = on_error
        #: the folder of voices chosen in the program, if one was
        self.voice_folder = voice_folder
        self._q = queue.Queue()
        self._eng = None
        self._lock = threading.Lock()
        self._closing = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    # -- plumbing ----------------------------------------------------------

    @property
    def engine(self):
        """Built on the worker thread, the first time something is asked.

        Opening it looks for the voices and reads one, which is quick but not
        free, and doing it here means the window is already up and saying so
        rather than waiting on it.
        """
        if self._eng is None:
            self._eng = Synthesiser(voice_folder=self.voice_folder)
        return self._eng

    def _run(self):
        while True:
            job = self._q.get()
            if job is None:
                break
            op, kw, callback = job
            try:
                result = getattr(self.engine, op)(**kw)
            except Exception as exc:                  # noqa: BLE001
                # A failed request still has to come back. Dropping the
                # callback left whatever asked for it waiting for an answer
                # that would never arrive: one failed render and the window
                # said "already rendering" to everything afterwards, for good.
                if self.on_error:
                    self.on_error('%s: %s' % (type(exc).__name__, exc))
                if callback:
                    callback(None)
                continue
            if callback:
                callback(result)

    def send(self, op, callback=None, **kw):
        self._q.put((op, kw, callback))

    # -- operations --------------------------------------------------------

    def ping(self, cb):
        self.send('ping', cb)

    def phonemes(self, words, cb):
        self.send('phonemes', cb, words=list(words))

    def voices(self, cb):
        self.send('voices', cb)

    def render(self, song, out, cb):
        self.send('render', cb, song=song, out=out)

    def close(self):
        if self._closing:
            return
        self._closing = True
        self._q.put(None)
        self._thread.join(timeout=5)
