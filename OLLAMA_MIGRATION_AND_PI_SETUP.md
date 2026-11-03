# Ollama migration and Raspberry Pi 5 setup

## Summary and scope

Implemented in `motion-llm-board` on `migration/offline-llm`. The sibling fork was read as reference, especially its native Ollama generate request. Its replacement audio capture, arithmetic/spelling rules, new word banks and alternate serial implementation were not copied. The maintained runtime keeps the original decision logic and hardware behavior.

Default model: **llama3.2:3b**, a text instruction model whose Ollama tag is approximately 2.0 GB (Q4_K_M). This is a reasonable starting point for a Pi 5 with 8 GB or more RAM, not a measured performance guarantee. Runtime memory exceeds download size. On a 4 GB Pi, or when latency/memory is problematic, try `llama3.2:1b`. Keep context at 2048 and close other heavy applications. Pi CPU generation and cold loading can be slow; no Pi benchmark has been performed here. Model choice is configuration, not a code change.

One supported Python install: **venv + requirements.txt**. No Conda setup is required. Ollama, ALSA, whisper.cpp and the Arduino firmware are installed separately. Initial installation/model downloads require internet; subsequent local inference does not require OpenRouter or internet access.

## Exactly what changed, file by file

| File | Change and purpose | Example |
|---|---|---|
| [openrouter/runner_spooky4.py](openrouter/runner_spooky4.py) | Replaced OpenRouter helper and its three callers with native Ollama `/api/generate`; removed key/auth headers; added root `.env` loading before speech imports; configurable model, URL, timeout, context, hardware enable and serial port; startup and raw-model/error logs. Default serial port is now Pi `/dev/ttyACM0`. | `ollama_completion(prompt, max_tokens=4)` sends `num_predict=4`, reads `response`, then existing host rules validate it. |
| [openrouter/pi_whispercpp_v4.py](openrouter/pi_whispercpp_v4.py) | Only microphone and Whisper configuration changed to environment settings, with `~` expansion and portable home-directory defaults. Recording/VAD/transcription algorithms remain unchanged. | `OUIJA_USB_MIC_ALSA=plughw:2,0` selects card 2/device 0. |
| [.env.example](.env.example) | Added all supported settings, with motion disabled for initial setup. Shell variables override `.env`. | Set `OUIJA_HARDWARE_ENABLED=true` for motion. |
| [.gitignore](.gitignore) | Added exception for `.env.example`; real `.env` remains ignored. | Commit the template, keep machine settings local. |
| [requirements.txt](requirements.txt) | Consolidated supported runtime dependencies to python-dotenv, requests, pyserial, with major-version upper bounds. Removed cloud SDK, numpy, PyAudio, Python Whisper and SpeechRecognition because this runtime does not use them. This is a dependency specification, not a fully pinned lockfile. | `python -m pip install -r requirements.txt` |
| Former requirements-pi.txt | Removed the redundant Pi list. | Use the one requirements file above. |
| Former conda-env-pi.yml | Removed the competing Conda environment definition. | Use `.venv`. |
| [README.md](README.md) | Updated Pi 5/local architecture, corrected module launch command, linked this guide and clarified supported/historical code. | `python -m openrouter.runner_spooky4` |
| [tests/test_ollama_migration.py](tests/test_ollama_migration.py) | Added native request/error, answer constraints, routing, mocked serial, repeat movement and source-preservation checks. | `python -m unittest discover -s tests -v` |
| [OLLAMA_MIGRATION_AND_PI_SETUP.md](OLLAMA_MIGRATION_AND_PI_SETUP.md) | Added this change record, architecture explanation, file inventory, examples and reproducible installation guide. | Follow the numbered installation sections below. |

The local development venv is generated and ignored; it must be recreated on the Pi. No models, environments or secrets belong in Git. The sibling fork has not been edited.

## Architecture and behavior

```text
User -> USB microphone -> Pi 5 / arecord -> whisper.cpp
     -> Python algorithmic routing -> structured prompt
     -> Ollama on 127.0.0.1:11434 / llama3.2:3b
     -> Python decision layer / constraints / word banks
     -> USB pyserial at 115200 baud
     -> unchanged Arduino AccelStepper firmware
     -> stepper motors -> hidden magnet -> surface pointer
```

The firmware implements custom serial commands, not GRBL. Wiring, pin assignments, coordinates, calibration, homing, firmware, serial bridge methods and command completion handling are preserved. The Python package still has its historical `openrouter` name; this does not imply a cloud call. Older backups/experiments still contain cloud code and are outside the maintained launch path.

### Request mapping

The old cloud payload had `model`, `prompt`, `max_tokens`, `temperature` and bearer authorization. The new local JSON payload is:

```json
{
  "model": "llama3.2:3b",
  "prompt": "Pick EXACTLY ONE word from this allowed list: ...",
  "stream": false,
  "options": {"num_predict": 4, "temperature": 0.35, "num_ctx": 2048}
}
```

Ollama returns an object such as `{"response":"SOUP","done":true}`. The helper reads the string; existing Python rules decide whether to accept it. Classification uses 4 output tokens at temperature 0.1; YES/NO uses 2 at 0.05; word selection uses 4 at 0.35, retaining the previous limits and temperatures. Tokens are model-dependent; a different tokenizer can cause truncation and fallback. Tune only after measuring on your Pi.

### Worked examples

- **Is anyone here?**: Python identifies YES_NO and its presence override returns YES without a model call. Serial sends `SPELL YES`; firmware moves to its YES target. This question alone cannot verify Ollama.
- **What should I eat?**: Python identifies ONE_WORD and scores food keywords. Ollama selects from the unchanged food bank. If it returns SOUP, the host sends `SPELL SOUP`.
- **xyzzy**: no known routing prefix/keyword; Ollama classifies YES_NO or ONE_WORD, then the corresponding answer path runs. An invalid classification defaults to ONE_WORD.
- **Will I succeed?**: YES_NO routing; model returns YES or NO. MAYBE, explanatory prose, or other invalid sanitized output triggers the existing random YES/NO fallback.
- **Invalid food answer**: a model answer such as HAMBURGER is outside the food bank, so Python randomly selects an existing allowed food word.
- **Weather**: the existing weather override returns GOOD; it is fictional board behavior, not a weather service.
- **Ollama unavailable/missing model**: request errors log `[OLLAMA ERROR]` and return empty text; existing local fallbacks continue. A board answer alone does not prove inference succeeded.
- **YES repeated twice**: original host logic sends `SPELL YES`, then `CENTER`, pauses 0.4 seconds, then `SPELL YES` again. Other word answers retain existing handling.

The host keeps its original alphanumeric sanitization; it does not execute model output as arbitrary serial commands. `[OLLAMA RAW]` shows generation before host validation. `[RESPONSE]` is the final constrained output. Some successful raw responses can still be rejected; compare these logs when validating model usage.

## Step-by-step Pi 5 installation

### 1. Prepare the Pi

Use Raspberry Pi OS **64-bit**, a suitable power supply, cooling, storage with several GB free for models/builds, and the existing USB mic and Arduino board. Prefer an 8 GB or larger Pi for the default 3B model. Keep the existing motor power, wiring and calibration.

```bash
uname -m
free -h
df -h ~
python3 --version
```

Architecture should be `aarch64`. The retained speech code imports `audioop`, which exists in Python 3.10–3.12 and was removed in 3.13. Use **Raspberry Pi OS Bookworm with Python 3.11** for this guide. If your OS ships Python 3.13+, install a supported Python 3.11/3.12 interpreter first and use that executable when creating the venv; do not assume the current OS default works. No speech algorithm replacement has been introduced for newer Python.

### 2. Install system tools

```bash
sudo apt update
sudo apt install -y git curl build-essential cmake pkg-config alsa-utils ffmpeg python3-venv python3-dev libasound2-dev
```

Python libraries are installed inside the venv, not with sudo pip. There is no need to install PyTorch, Python openai-whisper, PyAudio or an OpenRouter client.

### 3. Clone the migration branch

The migration must first be committed and pushed from the development computer before another machine can clone these changes. This implementation does not automatically publish a branch. Once available remotely:

```bash
cd ~
git clone --branch migration/offline-llm --single-branch https://github.com/HDSI-Lab-3-0/motion-llm-board.git
cd ~/motion-llm-board
git branch --show-current
```

Authenticate to GitHub if repository access requires it. For a later update, commit or preserve local edits before pulling. Keep local machine configuration in `.env`.

### 4. Create the venv and install the single dependency list

On Bookworm:

```bash
cd ~/motion-llm-board
python3 -m venv .venv
source .venv/bin/activate
python --version
python -m pip install -r requirements.txt
python -m pip check
```

The requirements install includes transitive HTTP dependencies automatically. Re-run `source .venv/bin/activate` in each new shell. Do not copy the Windows venv onto Linux.

### 5. Install Ollama and download the model

Official [Linux installation](https://docs.ollama.com/linux) supports ARM64. Use the installer on the Pi:

```bash
curl -fsSL https://ollama.com/install.sh -o /tmp/install-ollama.sh
sh /tmp/install-ollama.sh
sudo systemctl enable --now ollama
systemctl status ollama --no-pager
ollama pull llama3.2:3b
ollama list
```

If no systemd service was installed, consult the official service instructions, or run `ollama serve` in a separate terminal. Do not run a second server when the service already occupies port 11434. CPU inference is expected here; Pi GPU acceleration is not assumed.

Test generation directly, independently of Python fallbacks:

```bash
curl --fail http://127.0.0.1:11434/api/generate \
  -H 'Content-Type: application/json' \
  -d '{"model":"llama3.2:3b","prompt":"Return only YES","stream":false,"options":{"num_ctx":2048,"num_predict":8}}'
```

Expect JSON containing a nonempty `response`. Cold loading can take time. For lower memory use:

```bash
ollama pull llama3.2:1b
```

Then set `OUIJA_LOCAL_MODEL=llama3.2:1b` in `.env`. Download size is not a RAM requirement; watch `free -h` and `ollama ps` during use. This model recommendation is an engineering starting point, not an on-device benchmark. See [model details](https://ollama.com/library/llama3.2:3b).

### 6. Build whisper.cpp and download the speech model

Follow the upstream [whisper.cpp build](https://github.com/ggml-org/whisper.cpp):

```bash
cd ~
git clone https://github.com/ggml-org/whisper.cpp.git
cd ~/whisper.cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j 2
bash models/download-ggml-model.sh tiny.en
ls -lh build/bin/whisper-cli models/ggml-tiny.en.bin
cd ~/motion-llm-board
```

Keep the build tree on the Pi because the executable can depend on its built libraries. Use Linux ARM64 binaries built on the Pi, not Windows executables.

### 7. Configure microphone and paths

```bash
cd ~/motion-llm-board
cp .env.example .env
arecord -l
nano .env
```

If recording lists card 2/device 0, set `OUIJA_USB_MIC_ALSA=plughw:2,0`. This is an ALSA identifier, not a PortAudio index. Defaults for Whisper assume it was cloned to your home directory; absolute paths can also be used.

| Variable | Default / example | Meaning |
|---|---|---|
| OUIJA_LOCAL_MODEL | llama3.2:3b | Exact tag shown by `ollama list` |
| OUIJA_OLLAMA_URL | http://127.0.0.1:11434/api/generate | Local generate endpoint |
| OUIJA_OLLAMA_TIMEOUT | 180 | HTTP timeout in seconds, positive number |
| OUIJA_OLLAMA_CONTEXT | 2048 | Context token limit, positive integer |
| OUIJA_HARDWARE_ENABLED | false in template | true/1/yes enables serial; absent setting preserves original enabled default |
| OUIJA_SERIAL_PORT | /dev/ttyACM0 | Actual board USB serial port |
| OUIJA_USB_MIC_ALSA | plughw:3,0 | ALSA capture device |
| OUIJA_WHISPERCPP_DIR | ~/whisper.cpp | Directory containing build/bin/whisper-cli |
| OUIJA_WHISPER_MODEL | ~/whisper.cpp/models/ggml-tiny.en.bin | Speech model path |

The main runner loads root `.env` before importing speech settings. Shell environment values take precedence. If invoking the speech module directly, export settings first or use the actual microphone/path values in the following commands.

Test audio, replacing the device if needed:

```bash
arecord -D plughw:2,0 -f S16_LE -r 16000 -c 1 -d 5 /tmp/ouija-test.wav
~/whisper.cpp/build/bin/whisper-cli -m ~/whisper.cpp/models/ggml-tiny.en.bin -f /tmp/ouija-test.wav --no-timestamps
```

### 8. Test the application without motion

Keep `OUIJA_HARDWARE_ENABLED=false` in `.env`:

```bash
cd ~/motion-llm-board
source .venv/bin/activate
python -m unittest discover -s tests -v
python -m openrouter.runner_spooky4
```

Enter `t`, then `What should I eat?`. Check `[OLLAMA RAW]` and `[RESPONSE]`. Test `xyzzy` for the classification request and `Will I succeed?` for a YES/NO model request. `Is anyone here?` uses a rule and cannot verify model connectivity.

Press Enter for microphone input. Stay quiet during three two-second calibration chunks, then speak once listening proceeds. The existing runtime records/transcribes short chunks, calibrates ambient RMS thresholds and stops after speech followed by silence. This behavior is unchanged; it is not continuous transcription while the model responds. Enter `q` to exit.

### 9. Connect and run the existing Arduino hardware

Keep the already working firmware. If provisioning a new controller, upload [hardware/SPELL_numbers.ino](hardware/SPELL_numbers.ino) with its AccelStepper dependency using the Arduino IDE and your existing board selection/calibration. Python installation does not flash the controller. Consult the unchanged [wiring guide](hardware/docs/wiring-guide.md) and [stepper setup](hardware/docs/stepper-motor-setup.md).

Find the USB serial device:

```bash
ls /dev/ttyACM* /dev/ttyUSB*
sudo usermod -aG dialout "$USER"
```

Log out and back in after group changes. Close Arduino Serial Monitor so it does not occupy the port. Set the actual `OUIJA_SERIAL_PORT` and `OUIJA_HARDWARE_ENABLED=true` in `.env`, then:

```bash
cd ~/motion-llm-board
source .venv/bin/activate
python -m openrouter.runner_spooky4
```

Opening serial may reset the controller and trigger its existing homing motion. Existing runner behavior waits for startup output up to 15 seconds and retains its original handling on timeout/error; this migration does not strengthen that behavior. Check for `READY_AT_CENTER` and correct homing before asking questions. Commands wait for existing DONE / OK SPELL_DONE responses. A failed serial connection retains the original behavior of continuing without hardware. Ctrl+C closes the serial connection; it is not a firmware emergency-stop instruction.

### 10. Verify offline operation and later launches

After downloads and setup succeed, disconnect the Pi from the internet and repeat typed/voice questions. Local Ollama and whisper.cpp should still work; no API key is used. Preserve the localhost Ollama URL. To run later:

```bash
cd ~/motion-llm-board
source .venv/bin/activate
python -m openrouter.runner_spooky4
```

## Troubleshooting

| Symptom | Action |
|---|---|
| No module named audioop | Use Python 3.10–3.12; recreate venv with a supported interpreter. |
| No module named requests/dotenv/serial | Activate this repository's venv and install its requirements.txt. |
| Ollama connection refused | Check `systemctl status ollama` and the localhost URL. |
| Model not found / HTTP 404 | Pull the exact configured tag; check `ollama list`. |
| Slow answer / timeout / out of memory | Check `free -h`, `ollama ps`, and `journalctl -u ollama -n 50 --no-pager`; use 1B, close other apps, retain small context, or increase timeout. |
| Answers appear despite failed model | Existing random fallbacks are intentional; use direct API test and compare raw/final logs. |
| Raw model output is truncated or explanatory | The original short token limits and strict word-bank membership remain; invalid output falls back. Evaluate before tuning limits. |
| arecord cannot open device | Run `arecord -l`, set correct ALSA device, close competing capture apps. |
| Whisper executable/model missing | Check `.env` paths and build tree; use absolute paths for custom locations. |
| Serial permission denied | Add dialout group, log out/in, close Serial Monitor. |
| No movement | Check hardware-enable setting, actual port, `[HW]` errors, homing output and motor power. |

## Verification record

Development validation uses Python 3.12.8 in a newly created repository venv. The consolidated requirements install succeeded. Seven unittest cases passed, covering HTTP payload/response, error shapes/timeouts, preserved overrides, constraints, serial command bytes, repeated-answer centering and unchanged core source logic/hardware. No live Pi, microphone, Ollama generation or motor test has been performed by these automated checks. Follow steps 5, 7, 8 and 9 to complete on-device acceptance.

## Remaining repository files (unchanged)

The inventory below accounts for every remaining tracked file. Historical modules are not required by the maintained launch command and their imports may need additional research dependencies. Examples describe their role, not a supported installation path.
| File | Role and example |
|---|---|
| [data/adapter_history.txt](data/adapter_history.txt) | Historical adapter metadata; not loaded by the local runtime (for example, no adapter is needed for Ollama). |
| [data/adapter_path.txt](data/adapter_path.txt) | Historical adapter path metadata; not used when selecting OUIJA_LOCAL_MODEL. |
| [data/manual_additions.jsonl](data/manual_additions.jsonl) | Historical hand-added training records; not required to run a downloaded Ollama model. |
| [data/ouija_train.jsonl](data/ouija_train.jsonl) | Historical training dataset; no fine-tuning step is needed in the Pi setup. |
| [experimental/prototypes/add_no_calibration.py](experimental/prototypes/add_no_calibration.py) | Historical runner/prototype, retained unchanged; example use is comparing earlier speech-to-motion approaches. Not part of the supported Ollama entry point. |
| [experimental/prototypes/run_ouija_openrouter_v6.py](experimental/prototypes/run_ouija_openrouter_v6.py) | Historical runner/prototype, retained unchanged; example use is comparing earlier speech-to-motion approaches. Not part of the supported Ollama entry point. |
| [experimental/prototypes/run_ouija_openrouter_v7.py](experimental/prototypes/run_ouija_openrouter_v7.py) | Historical runner/prototype, retained unchanged; example use is comparing earlier speech-to-motion approaches. Not part of the supported Ollama entry point. |
| [experimental/prototypes/runner_test_1.py](experimental/prototypes/runner_test_1.py) | Historical runner/prototype, retained unchanged; example use is comparing earlier speech-to-motion approaches. Not part of the supported Ollama entry point. |
| [experimental/runner.py](experimental/runner.py) | Historical runner/prototype, retained unchanged; example use is comparing earlier speech-to-motion approaches. Not part of the supported Ollama entry point. |
| [experimental/runner_v2.py](experimental/runner_v2.py) | Historical runner/prototype, retained unchanged; example use is comparing earlier speech-to-motion approaches. Not part of the supported Ollama entry point. |
| [experimental/runner_v3.py](experimental/runner_v3.py) | Historical runner/prototype, retained unchanged; example use is comparing earlier speech-to-motion approaches. Not part of the supported Ollama entry point. |
| [experimental/runner_v4.py](experimental/runner_v4.py) | Historical runner/prototype, retained unchanged; example use is comparing earlier speech-to-motion approaches. Not part of the supported Ollama entry point. |
| [experimental/tinker/run_ouija_v3.py](experimental/tinker/run_ouija_v3.py) | Historical Tinker inference/server experiment, retained unchanged; example use is inspecting earlier research inference paths. Not part of the local Pi runtime. |
| [experimental/tinker/testmodel.py](experimental/tinker/testmodel.py) | Historical Tinker inference/server experiment, retained unchanged; example use is inspecting earlier research inference paths. Not part of the local Pi runtime. |
| [experimental/tinker/tinker_infer.py](experimental/tinker/tinker_infer.py) | Historical Tinker inference/server experiment, retained unchanged; example use is inspecting earlier research inference paths. Not part of the local Pi runtime. |
| [experimental/tinker/tinker_server.py](experimental/tinker/tinker_server.py) | Historical Tinker inference/server experiment, retained unchanged; example use is inspecting earlier research inference paths. Not part of the local Pi runtime. |
| [experimental/training/dataset.py](experimental/training/dataset.py) | Historical dataset/training utility, retained unchanged; example use is research into the original fine-tuning workflow, not downloading or running an Ollama model. |
| [experimental/training/manual_additions.py](experimental/training/manual_additions.py) | Historical dataset/training utility, retained unchanged; example use is research into the original fine-tuning workflow, not downloading or running an Ollama model. |
| [experimental/training/train_and_test.py](experimental/training/train_and_test.py) | Historical dataset/training utility, retained unchanged; example use is research into the original fine-tuning workflow, not downloading or running an Ollama model. |
| [hardware/SPELL_numbers.ino](hardware/SPELL_numbers.ino) | Unchanged AccelStepper controller firmware; SPELL SOUP spells letters, SPELL YES moves to the YES target, CENTER returns to center. |
| [hardware/docs/hardware-architecture.md](hardware/docs/hardware-architecture.md) | Existing hardware architecture reference; consult alongside the actual unchanged sketch when tracing the motor system. |
| [hardware/docs/stepper-motor-setup.md](hardware/docs/stepper-motor-setup.md) | Existing stepper setup reference; use when configuring the original motor assembly. |
| [hardware/docs/wiring-guide.md](hardware/docs/wiring-guide.md) | Existing wiring reference; use when checking the original electrical connections. |
| [openrouter/__init__.py](openrouter/__init__.py) | Package marker; permits python -m openrouter.runner_spooky4. |
| [openrouter/backup/ouija_hardware.py](openrouter/backup/ouija_hardware.py) | Historical backup implementation, retained unchanged; compare this version with the active runner when researching earlier routing or hardware behavior. Do not use for the local Pi launch. |
| [openrouter/backup/ouija_hardware_back.py](openrouter/backup/ouija_hardware_back.py) | Historical backup implementation, retained unchanged; compare this version with the active runner when researching earlier routing or hardware behavior. Do not use for the local Pi launch. |
| [openrouter/backup/ouija_hardware_backup.py](openrouter/backup/ouija_hardware_backup.py) | Historical backup implementation, retained unchanged; compare this version with the active runner when researching earlier routing or hardware behavior. Do not use for the local Pi launch. |
| [openrouter/backup/pi_runner.py](openrouter/backup/pi_runner.py) | Historical backup implementation, retained unchanged; compare this version with the active runner when researching earlier routing or hardware behavior. Do not use for the local Pi launch. |
| [openrouter/backup/runner_spooky.py](openrouter/backup/runner_spooky.py) | Historical backup implementation, retained unchanged; compare this version with the active runner when researching earlier routing or hardware behavior. Do not use for the local Pi launch. |
| [openrouter/backup/runner_spooky2.py](openrouter/backup/runner_spooky2.py) | Historical backup implementation, retained unchanged; compare this version with the active runner when researching earlier routing or hardware behavior. Do not use for the local Pi launch. |
| [openrouter/backup/runner_spooky3.py](openrouter/backup/runner_spooky3.py) | Historical backup implementation, retained unchanged; compare this version with the active runner when researching earlier routing or hardware behavior. Do not use for the local Pi launch. |
| [openrouter/backup/runner_test.py](openrouter/backup/runner_test.py) | Historical backup implementation, retained unchanged; compare this version with the active runner when researching earlier routing or hardware behavior. Do not use for the local Pi launch. |
| [openrouter/backup/wordbanks.py](openrouter/backup/wordbanks.py) | Historical backup implementation, retained unchanged; compare this version with the active runner when researching earlier routing or hardware behavior. Do not use for the local Pi launch. |
| [openrouter/backup/wordbanks_spooky2.py](openrouter/backup/wordbanks_spooky2.py) | Historical backup implementation, retained unchanged; compare this version with the active runner when researching earlier routing or hardware behavior. Do not use for the local Pi launch. |
| [openrouter/backup/wordbanks_spooky_no_maybe.py](openrouter/backup/wordbanks_spooky_no_maybe.py) | Historical backup implementation, retained unchanged; compare this version with the active runner when researching earlier routing or hardware behavior. Do not use for the local Pi launch. |
| [openrouter/new_hardware_bridge.py](openrouter/new_hardware_bridge.py) | Standalone diagnostic serial bridge; for example python -m openrouter.new_hardware_bridge --port /dev/ttyACM0 --interactive opens an interactive hardware console. |
| [openrouter/wordbanks_spooky3.py](openrouter/wordbanks_spooky3.py) | Active unchanged YES/NO values, keyword categories and word banks; food questions select from the food vocabulary. |

## Follow-up: explicit spelling requests

A reported transcript, `Hello? Can you spell Apple, please? Hey, thanks.`, exposed a routing issue: the fork's spelling matcher rejected the comma before please and then routed Can you to YES_NO. This was a host parsing issue, not evidence of model training failure.

The motion runner now checks explicit spelling before its existing question routing, using [openrouter/spelling.py](openrouter/spelling.py). It accepts a single ASCII alphabetic target of 1–19 characters, handles polite wrappers and separate greeting/thanks sentences, and rejects negated/conflicting spelling extraction. The exact transcript produces SPELL mode, APPLE, and the existing bridge command `SPELL APPLE` without an LLM request. Nonmatching questions keep the previous routing. No firmware or serial implementation changed. A nonmatching/negated request still proceeds through the original question-answer pipeline; it does not constitute a universal no-motion instruction.

## Personal-question policy (both repositories)

The maintained runtime now applies [openrouter/response_policy.py](openrouter/response_policy.py) before model classification (after explicit spelling). The fork mirrors this in its pc_ouija_test/response_policy.py, calls it from oracle.answer, and validates PERSONAL_UNKNOWN in ouija.hardware.command_for. These are host rules; model training is unchanged.

- Personal facts, identity, age, family, location and personal predictions matched by the policy return `[MODE] PERSONAL_UNKNOWN`, `[RESPONSE] IDK`, `[SOURCE] rules`. Examples: `How old am I?`, `Do you know how old I am?`, `What is my name?`, `Will I get married?`. Motion sends `SPELL IDK` using the existing firmware protocol.
- Fictional presence prompts such as `Are you here?`, `Is anyone here?` and `Can you hear me?` return YES through rules. Personal facts take precedence over presence in mixed prompts.
- Requests for suggestions such as `What should I eat?`, `Where should I go?`, and `What do I do next?` retain the existing constrained board-answer flow; they do not ask the system to know a private fact.
- Explicit `Spell apple` still spells APPLE. This is a request, not a claim about the user.

This is a pattern-based policy, not universal natural-language understanding. Unseen personal phrasing can still miss the rules; add its exact transcript as a regression case before expanding the matcher. No firmware, motor calibration, wiring or serial implementation was changed by this policy. The fork's host command validator was extended only to accept IDK for a validated personal-policy result.

## Personal fallback revised to WAIT

Supersedes the IDK policy examples above: all recognized personal questions now return WAIT, selected from the generic vocabulary in [openrouter/wordbanks_spooky3.py](openrouter/wordbanks_spooky3.py). Motion sends SPELL WAIT; presence questions still return YES. Explicit spelling is unchanged. The fork mirrors this behavior. WAIT stays deterministic rather than randomly choosing a different spooky word for personal facts.
