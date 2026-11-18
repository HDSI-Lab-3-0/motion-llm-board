# Automatic start on Raspberry Pi

Automatic mode runs independently of terminals and desktop login. Code comments
marked `AUTOMATIC START` identify this feature. Manual mode remains available.

The optional display is a separate Tkinter window with a yellow background and
the title `OUIJAI`. It reads `data/ouija_status.json`; the listener continues to
work if the display is closed.

## 1. Install and configure on the Pi

Finish the existing [Pi setup](OLLAMA_MIGRATION_AND_PI_SETUP.md), then run from
the repository root:

```bash
.venv/bin/python -m pip install -r requirements.txt
test -f .env || cp .env.example .env
nano .env
```

Set `OUIJA_USB_MIC_ALSA=plughw:2,0` in `.env`, replacing any existing line.
Set the actual serial and Whisper paths. Initially keep
`OUIJA_HARDWARE_ENABLED=false`. The runner loads `.env` before microphone imports;
an exported environment variable overrides it. No recurring export is needed.

Check `arecord -l` and test the microphone:

```bash
arecord -D plughw:2,0 -f S16_LE -r 16000 -c 1 -d 5 /tmp/ouija-mic.wav
aplay /tmp/ouija-mic.wav
```

Verify your voice is recorded. ALSA card numbers can change. If supported, test
`plughw:CARD=<actual-card-id>,DEV=0` using the ID from `arecord -l`, then save
the verified identifier in `.env`. Never use the placeholder literally.

## 2. Test automatic mode before enabling boot

```bash
.venv/bin/python -m openrouter.runner_spooky4 --auto-listen
```

The app logs the selected microphone, checks Whisper and the installed Ollama
model, and calibrates for one second before logging `Listening - speak now`.
Remain quiet during calibration. No Enter key is needed. Ctrl+C stops it.
With motion enabled it requires Arduino `READY_AT_CENTER` acknowledgement.
Opening serial may reset and home the Arduino; retries can therefore home again.

Automatic capture uses WebRTC speech detection plus amplitude thresholds, a
300 ms leading buffer, at least 200 ms of detected speech, a one-second ending
pause, and a 14-second utterance limit. Silence stays inside capture without
Whisper or model calls. Brief noise is discarded; rejected transcripts log
`BACKGROUND_NOISE` at most once per ten seconds. Nothing is sent to the board.
Microphone faults are errors, not silence. Whisper errors retry after a delay.

Recording closes before transcription and stays closed through model processing
and movement. Speech during that interval is not queued. The next session starts
after `OUIJA_AUTO_SETTLE_SECONDS` (default 1), reusing calibration and slowly
tracking quiet ambient levels while idle. There is no wake
word: intelligible TV or background conversation can still trigger an answer.
Unclear audio can also produce plausible Whisper text; these filters cannot
guarantee rejection. Test in the intended room before unattended use.

## 3. Install the service

Edit [deploy/ouija.service](deploy/ouija.service): replace every `YOUR_USER`
and use the actual absolute project path (check `whoami` and `pwd`). Ensure that
user has permission to read the project and access audio/serial. Do not add a
second microphone value to the service; the application reads `.env`.

```bash
sudo cp deploy/ouija.service /etc/systemd/system/ouija.service
sudo systemctl daemon-reload
sudo systemctl start ouija
sudo systemctl status ouija --no-pager
journalctl -u ouija -f
```

Stop the foreground instance first. Linux launches use an exclusive project
lock, so manual and service processes cannot run together in the same checkout.
After checking voice input with motion disabled, stop the service, set
`OUIJA_HARDWARE_ENABLED=true`, and start it again. Check homing and real movement.

Only after this succeeds:

```bash
sudo systemctl enable ouija
sudo reboot
```

It now starts without a terminal or login. Failed startup/device checks restart
after ten seconds. Movement failures stop the process instead of replaying an
uncertain command. Service restarts reconnect and home before accepting questions.

## 4. Add the Pi display

The display requires Raspberry Pi OS with a graphical desktop and automatic
desktop login. It uses the same project `.venv`; no second environment is
needed. Install the updated code and dependencies first:

```bash
cd ~/motion-llm-board
git pull --ff-only
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Replace `YOUR_USER` in `deploy/ouijai-ui.desktop` with `robotflower` (or the
value from `whoami`), then install it for the logged-in desktop user:

```bash
mkdir -p ~/.config/autostart
cp deploy/ouijai-ui.desktop ~/.config/autostart/ouijai-ui.desktop
```

The file should contain:

```ini
Exec=/home/robotflower/motion-llm-board/.venv/bin/python /home/robotflower/motion-llm-board/ui/ouijai_display.py
```

Test it before rebooting:

```bash
/home/robotflower/motion-llm-board/.venv/bin/python ui/ouijai_display.py
```

Press `Esc` to close the test window. The normal automatic listener remains a
systemd service. On the next desktop login the yellow `OUIJAI` display opens
automatically. It shows `LISTENING`, `THINKING`, `MOVING`, the latest heard
question, and the response. A stale or missing status file shows `SERVICE NOT
RUNNING`.

## 5. Verify and maintain

Test prolonged silence, brief bumps, fans, unclear speech, clear short questions,
natural pauses, repeated answers, missing peripherals, and reboot without login.
Confirm rejected audio never causes model calls or movement. A completely muted
microphone can look like silence: the recording/playback test remains essential.
Measure startup time and false activations on the Pi; Windows tests cannot prove
audio or motor performance. There is no audible/LED ready cue in this version;
read readiness through the journal.

```bash
sudo systemctl stop ouija
sudo systemctl start ouija
sudo systemctl restart ouija
journalctl -u ouija -n 100 --no-pager
sudo systemctl disable --now ouija
```

Restart after changing `.env`. Stop the service before manual mode:
`.venv/bin/python -m openrouter.runner_spooky4`.
