# OuijAI: local speech to physical motion

The maintained runtime targets Raspberry Pi 5, a USB microphone, and the existing Arduino motion board. Speech is transcribed with whisper.cpp; local Ollama replaces the former OpenRouter API. No cloud key is required.

## Install and run

For boot startup, hands-free listening, and the optional yellow `OUIJAI` display,
follow [Automatic start on Raspberry Pi](AUTOMATIC_START.md).

Use Python 3.10–3.12 and **one dependency file**, [requirements.txt](requirements.txt), inside a venv. Ollama, whisper.cpp, and ALSA are separate system tools.

Follow [OLLAMA_MIGRATION_AND_PI_SETUP.md](OLLAMA_MIGRATION_AND_PI_SETUP.md) for the complete clone, installation, model, microphone, serial, testing, and troubleshooting instructions.

After completing that setup, run from the repository root:

```bash
source .venv/bin/activate
export OUIJA_USB_MIC_ALSA=plughw:2,0
python -m openrouter.runner_spooky4
```

Press Enter to speak, `t` to type a question, or `q` to quit. The package retains its historical name `openrouter` for compatibility; the maintained runner uses Ollama. Copy [.env.example](.env.example) to `.env` and configure it. The example disables physical motion for initial testing; set `OUIJA_HARDWARE_ENABLED=true` when ready.

The `export` command selects microphone card 2, device 0 for the current terminal.
Run it before starting the app. Check microphone card numbers with `arecord -l`;
they can change after reconnecting USB devices. To save this choice for future
sessions, put `OUIJA_USB_MIC_ALSA=plughw:2,0` in `.env` (without `export`). An
exported shell value takes precedence over `.env`.

## Architecture

```text
User speaks
  -> USB microphone
  -> Raspberry Pi 5 / ALSA recording
  -> whisper.cpp local transcription (existing VAD)
  -> Python algorithmic routing and structured prompt
  -> Ollama local model (default llama3.2:3b)
  -> Python decision constraints and word-bank selection
  -> USB / pyserial (115200 baud)
  -> existing Arduino AccelStepper firmware
  -> motors / hidden magnet / surface pointer
```

Routing rules handle common questions first. The model handles remaining classification and constrained answer selection. Python accepts YES/NO or a word from the selected bank; existing local fallbacks handle invalid or unavailable model output. MAYBE is excluded. The firmware uses a custom serial protocol, rather than GRBL.

## Runtime files

- [runner_spooky4.py](openrouter/runner_spooky4.py): entry point, routing, Ollama requests, decision constraints, existing serial bridge.
- [pi_whispercpp_v4.py](openrouter/pi_whispercpp_v4.py): ALSA recording, noise calibration, VAD, whisper.cpp execution.
- [wordbanks_spooky3.py](openrouter/wordbanks_spooky3.py): unchanged vocabulary and keyword categories.
- [new_hardware_bridge.py](openrouter/new_hardware_bridge.py): separate serial diagnostic utility with a longer movement timeout.
- [SPELL_numbers.ino](hardware/SPELL_numbers.ino): firmware, homing and calibrated motion; repeated letters travel through CENTER.
- [tests](tests): model/serial simulations and behavior-preservation checks.

Historical [experimental](experimental) and [backup](openrouter/backup) code remains for reference and may require its own research dependencies or cloud services. It is not part of the supported local launch path. Training is unnecessary to run this project.

For the repeat-letter firmware update, follow [the update guide](REPEAT_LETTER_UPDATE.md).
