This is the build of the newest commit on `main`, replaced every time
something lands. It is not a version: for those, see the
[releases page](../../releases).

`Read Me.txt` in the zip is the guide: the keys, what a song is made of, the
voices, and what to do if something goes wrong.

**The voices are not in it.** Microsoft Sam, Mike and Mary are Microsoft's:
the program finds them where Windows installs them, and otherwise asks for the
folder that holds `Sam.spd` (or Mike's, or Mary's), `LTTS1033.LXA` and
`r1033tts.LXA`, which come with Windows XP and with the SAPI 5.1 voices.

**Windows** — `WhistlerStudio-win64.zip`. Unzip it anywhere and run
`WhistlerStudio.exe` from inside the folder, which has to stay together.
`whistler.exe` beside it is the same program for the command line. It is
unsigned, so SmartScreen stops it the first time: "More info", then
"Run anyway".

**macOS** — `WhistlerStudio-macos-arm64.zip`. Apple Silicon. Unzip and put
`Whistler Studio.app` where you like. It is signed only ad-hoc, not
notarised, so macOS refuses to open it until the download flag is cleared:

```
xattr -c "/Applications/Whistler Studio.app"
```

Microsoft Sam, Mike and Mary are Microsoft's and are not covered by this
project's MIT licence. See [NOTICE](../../blob/main/NOTICE).
