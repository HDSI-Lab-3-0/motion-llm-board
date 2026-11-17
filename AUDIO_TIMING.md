# Microphone timing

Run the maintained entry point as usual: `python -m openrouter.runner_spooky4`.
After pressing Enter, stay quiet while **Preparing microphone** is displayed.
Speak after **Listening — speak now**. This cue is emitted only after PCM audio
has arrived and four 250 ms calibration blocks have been collected. Device
startup adds to the approximately one second calibration period.

Each microphone event includes a UTC wall-clock timestamp and elapsed time from
the listen request, measured with a monotonic clock. Events cover preparation,
readiness, speech detection, recording completion, and transcription start/end.
Speech detection reports the 250 ms audio interval relative to calibration end;
the log timestamp is when that interval was processed, not exact word onset.
These are application timestamps, not hardware ADC timestamps.

One continuous ALSA recording process captures calibration and the question.
The question, including leading quiet audio and pauses, is transcribed once
after capture ends. The runner stops after one second of silence following
speech, or at its 14 second question limit. Startup failures never print the
ready cue. A stalled stream produces a microphone error rather than waiting
indefinitely.

On the Pi, check that speaking immediately after the ready cue preserves the
first word, and that a sentence longer than two seconds retains its middle and
ending. Compare the event timestamps to distinguish microphone setup delay
from transcription delay. Automated tests simulate PCM capture; they cannot
measure USB/ALSA latency on the physical device.
