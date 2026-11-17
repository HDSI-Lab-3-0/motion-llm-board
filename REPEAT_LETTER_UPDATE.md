# Update repeated-letter motion

This guide is for the **motion-llm-board** repository on branch
**migration/offline-llm**. Use this repository for future updates.

Development checks on November 17, 2026: all 17 tests passed, including the C++
firmware movement test. The full sketch compiled for Arduino Uno using AVR core
1.8.6 and AccelStepper 1.64.0. It used 17,676 bytes of program storage and 1,029
bytes of RAM. No upload or physical movement test was performed. Compile for
your actual board model before uploading.

## What the board does

Repeated letters now travel through the same center used by the CENTER command.

```text
GOD:  G -> O -> D
GOOD: G -> O -> CENTER -> O -> D
AAA:  A -> CENTER -> A -> CENTER -> A
```

Only adjacent matching letters get this extra trip. Normal letters and digits keep
their existing paths. The runner's existing move to center before a repeated
YES/NO answer also stays in place.

The checked-in center is X = -7 mm, Y = 3 mm. It comes from `xCenterMm` and
`yCenterMm`, so the repeat gesture uses your board's center calibration.

## Files changed

| File | Change |
| --- | --- |
| [Arduino sketch](hardware/SPELL_numbers.ino) | Detects repeated letters, goes to center, then returns to the letter. Fixed serial messages use flash storage to save RAM. |
| [Main runner](openrouter/runner_spooky4.py) | Allows up to 900 seconds for a movement command. |
| [Diagnostic bridge](openrouter/new_hardware_bridge.py) | Uses the same longer command wait. |
| [Spelling tests](tests/test_spelling.py) | Checks exact words and waits for the full word to finish. |
| [Firmware tests](tests/test_firmware_spelling.py) | Runs the real spelling functions with fake motors. |
| [Migration tests](tests/test_ollama_migration.py) | Allows the intended timeout update and checks that calibration stays the same. |

## 1. Save your working setup

1. Save the firmware that currently works on your Arduino.
2. Record its board type, USB port, motor directions, steps per mm, speed, bounds,
   and letter coordinates.
3. Back up your Pi's `.env` file.
4. Stop the runner before uploading anything.

The repository keeps its existing calibration. If your installed firmware has
different values, copy your known working values into the new sketch first.

## 2. Check the branch and software

Open a terminal in this repository and run:

```sh
git branch --show-current
git status --short
```

The branch should be `migration/offline-llm`. Keep any local work safe before
switching branches or pulling updates. These edits are local until committed and
sent to your remote repository. A Pi cannot get them through `git pull` before that.

Activate your project Python environment. Follow the
[Pi setup guide](OLLAMA_MIGRATION_AND_PI_SETUP.md) if dependencies are missing.
Run:

```sh
python -m unittest discover -s tests -p "test_*.py"
```

The firmware test needs g++ or clang++ on PATH. If it is skipped, that movement
test has not run. The fake motors check paths and order; they do not prove how
the real board moves. You must still compile and physically test the sketch.

## 3. Upload the firmware

1. Open [SPELL_numbers.ino](hardware/SPELL_numbers.ino) in Arduino IDE.
2. If asked, let the IDE put it in a folder named `SPELL_numbers`. Make sure you
   upload this updated copy, not an old copy.
3. Select the actual board model and USB port under **Tools**.
4. Install **AccelStepper** in Library Manager if needed.
5. Check your saved calibration against the sketch.
6. Click **Verify** and wait for a successful compile.
7. Clear the travel area and keep a way to stop motor power within reach.
8. Click **Upload** and wait for success.

Opening the serial port can reset the Arduino and start homing. Watch the motors.
The current blocking movement loop does not read serial STOP commands during a
move. Closing the app is not a physical emergency stop.

## 4. Test in Serial Monitor

Set Serial Monitor to **115200 baud** and a newline line ending. Wait for
`READY_AT_CENTER`. Send commands one at a time.

| Command | Expected motion |
| --- | --- |
| `CENTER` | The same center point that repeats will use. |
| `SPELL GOD` | No extra center trip. |
| `SPELL GOOD` | One center trip between the two O selections. |
| `SPELL APPLE` | One center trip between the two P selections. |
| `SPELL BOOKKEEPER` | Three center trips: OO, KK, EE. |
| `SPELL AAA` | Two center trips. |
| `SPELL MM`, `SPELL ZZ`, `SPELL NN` | Clear movement from letters near the edges. |
| `SPELL 11` | Existing digit behavior, with no repeat trip. |
| `SPELL FOUR` | Goes to number 4, as before. |
| `YES`, `NO` | Existing special targets. |

Wait for `OK SPELL_DONE` after each spelling command. A repeat prints
`REPEAT LETTER` followed by the letter. Intermediate `DONE` messages only mark
small parts of the word. Direct CENTER, YES, and NO commands finish with DONE.

Stop if an ERR message appears. A center outside the bounds, or exactly on the
repeated letter, produces `ERR repeat_center_invalid` and ends the word without
a success message. These checks do not detect obstacles or printed letters.

Have someone watch without knowing the word. They should tell GOOD from GOD and
count three As. Check the full path to center for every tested letter.

## 5. Understand timing

The sketch pauses 500 ms before leaving a repeated letter and 500 ms after
returning. It pauses 150 ms at center. These settings are `repeatLetterPauseMs`
and `repeatAwayPauseMs` near the motion settings.

Travel to center is longer than the earlier 1 mm gesture. At the checked-in motor
settings, a repeat can take around 30 seconds for a full round trip. Many repeats
can take several minutes. Both Python bridges now allow 900 seconds (15 minutes)
for a command. This is a maximum wait, not a forced delay. They continue when the
word finishes. Measure real times after changing calibration or speed.

## 6. Update the Pi application

Use this branch of this repository on the Pi. Do not use the fork's generated
release folders: they use a different launcher.

Once these changes are committed and available on your remote, save local work
on the Pi, switch to `migration/offline-llm`, and pull the update. Or copy this
updated checkout to a new folder on the Pi, without copying a Windows `.venv`.
Keep the old application folder as a backup. Preserve the Pi's working `.env`.

Install dependencies using this repository's `requirements.txt` in your Pi Python
environment if needed. Whisper binaries and model files stay in their existing
locations. Uploading firmware and updating Python are separate steps.

## 7. Test the full runner

Close Serial Monitor first. In `.env`, set `OUIJA_HARDWARE_ENABLED=false`, then run:

```sh
python -m openrouter.runner_spooky4
```

Type `t`, press Enter, and enter `Spell GOOD`. Check that the response is GOOD.
Quit with `q`.

Set `OUIJA_HARDWARE_ENABLED=true` and set `OUIJA_SERIAL_PORT` to the actual port,
such as `/dev/ttyACM0` on the Pi or `COM3` on Windows. Run the same command again.
Opening the connection may start homing. Repeat the typed test and watch the
center trip. Then try voice input and normal one-word questions.

## 8. Completion and recovery

- [ ] Software tests pass, including the firmware test.
- [ ] The full sketch compiles for your board and uploads.
- [ ] GOOD and GOD look different; AAA has two center trips.
- [ ] Edge letters, YES/NO, digits, and number words still work.
- [ ] The Pi runs this repository on the correct branch.
- [ ] Typed and voice input finish without a movement timeout.

If a test fails, stop motor power if needed. Save the serial log and the word
being spelled. Restore your saved firmware and old application folder to return
to the previous setup. Do not remove bounds checks to fix a movement problem.
