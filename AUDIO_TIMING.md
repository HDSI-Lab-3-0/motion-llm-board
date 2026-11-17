# Microphone timing

Run `python -m openrouter.runner_spooky4` as usual. After pressing Enter,
stay quiet until **Listening - speak now** appears.

Successful speech capture displays only three timestamped microphone messages:

1. **Listening - speak now**: audio capture is verified and calibration finished.
2. **Captured**: question recording has finished.
3. **Transcribed**: speech-to-text has finished.

Each message includes UTC time and elapsed seconds since the listen request.
Calibration takes approximately one second, plus device startup time.
Recording is continuous; transcription runs afterward. Silence without speech
returns the existing no-speech message without claiming transcription finished.
Microphone or transcription failures still display errors.

Physical USB/ALSA latency must be checked on the Pi; automated tests use simulated
PCM audio. These timestamps measure application events, not hardware ADC timing.
