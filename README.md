# Whistler Studio

Singing with **Microsoft Sam, Mike and Mary** -- the voices of Windows XP's
text to speech -- built up note by note, and **built to be used without
seeing it**.

Whistler was the codename of the Microsoft speech engine behind those three
voices. Whistler Studio is a fork of Bryn's
[VocalWriter Studio](https://github.com/masonasons/vocalwriter), an accessible
editor for VocalWriter 2.0's singing synthesiser, with that synthesiser
replaced by KamiKitsune420's
[reconstruction of Microsoft's engine in portable C](https://github.com/KamiKitsune420/ms-sam-mike-mary-decomp)
-- which matches the real engine to within one step in every sample -- taught
to sing.

```
app/       the editor, and the same program as a command line
whistler/  the engine as the editor drives it: voices, phonemes, rendering
engine/    Microsoft Sam, Mike and Mary in portable C, as a submodule
tools/     build_engine.py, which builds the engine; smf.py, which reads MIDI
tests/     python -m unittest discover -s tests
docs/      read-me.txt, the guide that goes beside the program
```

## The voices are not included

Sam, Mike and Mary are Microsoft's recordings, and their files are not in this
repository or in any build of it. Whistler Studio reads them from wherever they
already are:

```
Sam.spd  Sam.sdf     the voice, and its base pitch
Mike.spd Mike.sdf    the same for Mike, and for Mary
LTTS1033.LXA         the dictionary
r1033tts.LXA         the letter-to-sound rules
```

They come with Windows XP and with the SAPI 5.1 voices. Where Windows has them
installed -- `Common Files\SpeechEngines\Microsoft\TTS\1033` for the voices and
`...\Lexicon\1033` for the dictionary -- they are found without asking.
Otherwise the program asks for the folder they are in and remembers it; a
`voices` folder beside the program, or `WHISTLER_VOICES` naming one, works too.
Any other `.spd` beside them is offered as a voice as well, such as a Microsoft
Anna built with the engine's own `annavoice` tools.

## Running from source

```bash
git clone --recursive https://github.com/RetroBunn/ms-sam-mike-mary-singing.git
cd ms-sam-mike-mary-singing
python -m pip install numpy wxPython
python tools/build_engine.py
python launch.py
```

GitHub Desktop fetches the `engine` submodule along with the rest.
`tools/build_engine.py` builds the engine library with the engine's own
Makefile -- MinGW's gcc on Windows, cc elsewhere -- or with Visual Studio when
that is all there is, and the program finds it in `engine/build`.

## Builds

`.github/workflows/build.yml` builds every commit on `main` for Windows and for
Apple Silicon and keeps the newest pair at
[releases/latest](../../releases/latest), once GitHub Actions is turned on for
the repository. The builds carry the engine and no voices.

## The application

A song is built note by note. A note carries a *group* of phonemes and one
pitch, because that is how singing works: a syllable sits on a note, not one
phoneme per note. "Add word" looks a word up in Sam's own dictionary, which
divides it into syllables itself -- `daisy` is `d ey 1 - z iy`, the `1` marking
the stressed vowel -- and spreads it over as many notes as it has syllables.

**It is built to be used without seeing it.** Everything is on the menus with a
shortcut on each item, so a screen reader announces the key along with the name;
editing happens in dialogs with ordinary labelled fields rather than inside the
list; and every control states its own accessible name rather than leaving
Windows to guess it from whatever static text happens to precede it, which is
wrong more often than not. Nothing is conveyed by colour or position alone.

A song is made of **tracks**, each with its own voice, volume, pan and notes.
The voices are Sam, Mike and Mary, and any other found beside them.

| | |
|---|---|
| F6 | between the tracks list and the notes list |
| Ctrl+T | add a track |
| Enter on a track | its name, voice, volume, pan and voice controls |
| M / S on a track | mute / solo |
| Delete on a track | remove it |
| Ctrl+Up / Ctrl+Down | reorder the parts |

| | |
|---|---|
| Ctrl+W / Ctrl+N / Ctrl+R | add a word / a note / a rest |
| Ctrl+Shift+R | a rest to the end of the bar |
| Ctrl+E, or Enter on a note | edit it, including its pitch bend |
| Ctrl+D, or Delete | remove it |
| Alt+Up / Alt+Down | transpose a semitone |
| Alt+Right / Alt+Left | a sixteenth note longer or shorter |
| Ctrl+Z / Ctrl+Shift+Z | undo / redo |
| Ctrl+C / Ctrl+X / Ctrl+V / Ctrl+A | copy, cut, paste, select all |
| Ctrl+Up / Ctrl+Down | move a note earlier or later |
| Ctrl+G | go to a bar |
| Ctrl+, | song settings: tempo, signature, consonants, reverb, voice controls |
| Ctrl+Shift+P | hear a note whenever it is nudged |
| Space | play from the cursor, or stop |
| Ctrl+P / Ctrl+H / Ctrl+M / Ctrl+. | play from the start / hear one note / metronome / stop |
| Ctrl+O / Ctrl+S | open and save a song |
| Ctrl+Shift+I | import a VocalWriter Studio project |
| Ctrl+I | import a MIDI file |
| Ctrl+Shift+S / Ctrl+Shift+T | export one WAV / one WAV per track |
| F1 | list the keys in Messages |

Undo and redo cover the last 100 edits to notes, tracks, and song settings.
The Edit menu names the next action to undo or redo. Opening, importing, or
starting a new song clears history; saving preserves it. On macOS, use
Command+Z and Command+Shift+Z; Hear Note is **Option+H**, leaving Command+H to
hide the app, and play from the start is **Command+P**.

The picker inside the note editor offers all forty of Sam's phonemes, each with
a word it is heard in -- `aa` as in fAther to `zh` as in pleaSure. A note's
phonemes can also be typed, separated by spaces, with `1` or `2` after a vowel
to stress it; a symbol that is not one of Sam's is left out rather than
stopping the song.

What belongs to the whole song -- the tempo, the time signature, how long the
consonants are, the reverb, and the voice controls -- is set once in the song
settings and then left alone, which is why it is behind Ctrl+comma rather than
in the window. A part follows the song's consonant length, reverb and voice
controls until it is given its own in the track dialog. Parts that share a
reverb share its tail; a part with its own is in a room of its own, which is
how a dry lead sits in front of a choir in a hall.

The voice controls are the vibrato's depth (in cents) and rate, portamento --
how long each new pitch takes to slide in -- detune, and an **effect**: the
voice modes of Microsoft's older SAPI 4 engine, rebuilt by the engine's
author -- Hall, Stadium, Space, Whisper and RoboSoft One to Six, and Room, a
setting Microsoft had and never used.

**A note is heard where its vowel is, not where it starts.** "Star" with its
`s` and `t` in front of the vowel is heard 141 ms after the beat it is written
on. *Consonants before the beat*, in the song settings, is on: a note's opening
consonants are sung into the end of the note before it, and its vowel lands on
its beat. The engine places every sound where the score puts it rather than
trusting its own lengths, so however long a phrase is, each vowel starts within
one pitch period of its beat: 1.2 ms in the middle of the range, about 4 ms at
the bottom of Sam's and Mike's.

How you like to work, as opposed to what the song is, lives on the **Settings**
menu and is kept between songs: *Preview notes as they change* (Ctrl+Shift+P)
plays a note whenever its pitch or length is nudged, once the nudging stops.

A MIDI file from anywhere else arrives singing: a note that carries no words of
its own is given **aa**, the open vowel of "father", so the line can be played
before a single word is typed. Where the file does carry words, they are looked
up, and a word broken over notes with hyphens ("coun-" "try") is looked up whole
and divided where the dictionary divides it.

Pitch bend belongs to the note and is written as the points it passes through,
so it survives the note being retimed, transposed or moved. Exporting tracks
separately gives stems, not separate performances: each file carries the volume
and the pan it has in the song, so laying them back on top of one another
reproduces the mix.

### Songs, and bringing in VocalWriter Studio's

A song is plain JSON, a `.wst` file: the tempo, time signature, consonant
length, reverb and voice controls, and for each track its name, voice, volume,
pan, mute and solo, and its notes -- each with its phonemes, pitch, length in
beats, word and pitch bend.

A VocalWriter Studio project (`.vws`) is not opened but imported,
**File > Import VWS** (Ctrl+Shift+I), because its phonemes are VocalWriter's and
have to be said in Sam's first. Each of VocalWriter's 57 phonemes is matched by
the example word VocalWriter itself gives it: `UX` ("bUd") is Sam's `ah`, `AR`
("bAR") is `aa r`, `EN` ("buttON") is `ax n`, and the flaps and stops of beTTer
and iT are `t`. The notes, words, bends, tempo, signature, consonant length and
reverb come across as they were. VocalWriter's voices and voice controls do
not -- they belong to a different synthesiser -- so every part is sung by Sam
until it is given another voice, and the import says so, along with any symbol
it could not place. Saving then writes a `.wst` beside the original.

### From the command line

The editor is also a command line program, for batches and for scripts:

```bash
python launch.py song.wst -o song.wav
python launch.py tune.mid -o tune.wav --voice Mary --tempo 96
python launch.py old.vws --save new.wst
python launch.py song.wst --tracks stems
python launch.py --list-voices
python launch.py --pronounce daisy bicycle
```

A MIDI file or a VocalWriter Studio project is imported exactly as the File
menu imports it. `--tempo`, `--voice`, `--consonants`, `--reverb`, `--from`,
`--track` and `--anticipate` override what the file says; `--help` lists
everything. Given a file and nothing else it opens the editor on that song.

The song is built by `app/project.py`, which is what the window builds its
songs with as well, so a file rendered here and the same file exported from the
window are the same audio to the sample.

A Windows build has two executables in it: `WhistlerStudio.exe`, which is the
editor, and `whistler.exe`, which is the same program built as a console
program so that a shell waits for it and can read what it said. Windows decides
that when a program is built rather than when it is run, so one executable
cannot be both. On macOS the one inside the bundle does both:

```bash
"/Applications/Whistler Studio.app/Contents/MacOS/WhistlerStudio" song.wst -o song.wav
```

## How it sings

The engine is Microsoft's own, rebuilt: KamiKitsune420's port reproduces the
SAPI 5 engine that speaks as Sam, Mike and Mary, to within one step in every
sample, from the same voice files. Speaking is left exactly as it was. Singing
is added in
[a fork of it](https://github.com/RetroBunn/ms-sam-mike-mary-decomp), through
one call, `sam_tts_sing_notes` in `engine/src/sam_tts.h`:

- A phrase is handed over whole, a note at a time, each with its own phonemes,
  length and pitch, and with which notes belong to one word, since the engine
  chooses its sounds differently inside a word and at its edges.
- Consonants keep their natural length and the vowel fills the rest of the
  note; a trailing r, l, m, n or ng shares the note with the vowel; held vowels
  hold their steadiest frame instead of looping.
- The engine can only change sound a pitch period at a time, so every sound is
  aimed at where the score puts its end, and the next makes up for whatever the
  last one ran over or under. That is what keeps a long phrase on the beat.
- Pitch bends, portamento and vibrato follow the note; the effects are the
  SAPI 4 voice modes.

Everything is sung at the voices' own rate, 22,050 Hz, and that is what the
exported files are. Rendering is quick: eleven seconds of Mary with reverb take
about a quarter of a second, and finished renders are kept, so playing the same
thing twice renders once. Sung notes are louder than speech -- a held vowel high
in a voice's range can reach three times full scale -- so every note is sung at a
third of full volume and scaled back up in floating point, and the mix is
turned down, rather than clipped, when parts add up past full scale.

```
app/studio.py        the window: tracks, notes, phonemes, play
app/cli.py           the same program with no window: a song in, a WAV out
app/project.py       songs, Import VWS and Import MIDI
app/engine.py        the engine on a worker thread, answering in callbacks
whistler/engine.py   phrases in, a mixed song out, with the render cache
whistler/libsam.py   the engine library, through ctypes
whistler/phonology.py Sam's phonemes, syllables, and VocalWriter's in Sam's
whistler/paths.py    where the engine and the voices are
```

## Licence

The work in this repository is under the MIT licence; see
[LICENSE](LICENSE) and [NOTICE](NOTICE). The engine carries its own MIT
licence.

That covers none of Microsoft's voices. **Microsoft Sam, Mike and Mary and
their files are Microsoft's**, and they are not included: the program reads the
copy already on the machine it runs on. Whistler Studio is not affiliated with
or endorsed by Microsoft.
