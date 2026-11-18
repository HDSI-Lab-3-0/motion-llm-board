# openrouter/pi_whispercpp_v4.py
import subprocess
import tempfile
import os
import re
import wave
import audioop
import time
import queue
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List

# =====================================================
# AUDIO / WHISPER CONFIG
# =====================================================

USB_MIC_ALSA = os.getenv("OUIJA_USB_MIC_ALSA", "plughw:2,0")
WHISPERCPP_DIR = os.path.expanduser(os.getenv("OUIJA_WHISPERCPP_DIR", "~/whisper.cpp"))
MODEL_PATH = os.path.expanduser(os.getenv("OUIJA_WHISPER_MODEL", os.path.join(WHISPERCPP_DIR, "models", "ggml-tiny.en.bin")))


# =====================================================
# LOW-LEVEL HELPERS
# =====================================================

def _run(cmd: List[str], timeout: Optional[float] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )


def record_wav(
    out_wav: str,
    duration_s: float = 1.0,
    device: str = USB_MIC_ALSA,
    rate: int = 16000,
) -> None:
    """
    Records mono 16-bit WAV using arecord.
    arecord requires integer seconds for -d.
    """
    dur_int = int(duration_s)
    if duration_s > dur_int:
        dur_int += 1
    if dur_int < 1:
        dur_int = 1

    cmd = [
        "arecord",
        "-D", device,
        "-f", "S16_LE",
        "-r", str(rate),
        "-c", "1",
        "-d", str(dur_int),
        out_wav,
    ]

    p = _run(cmd, timeout=dur_int + 5)
    if p.returncode != 0:
        raise RuntimeError(
            "arecord failed:\n"
            f"CMD: {' '.join(cmd)}\n"
            f"STDERR:\n{p.stderr}\n"
            f"STDOUT:\n{p.stdout}"
        )


def wav_rms(wav_path: str) -> int:
    """
    Compute RMS amplitude from a 16-bit mono wav.
    """
    with wave.open(wav_path, "rb") as wf:
        sampwidth = wf.getsampwidth()
        frames = wf.readframes(wf.getnframes())

    return audioop.rms(frames, sampwidth)


def transcribe_wav(
    wav_path: str,
    whispercpp_dir: str = WHISPERCPP_DIR,
    model_path: str = MODEL_PATH,
) -> str:
    """
    Runs whisper.cpp CLI and returns last transcription line.
    """
    whisper_cli = os.path.join(whispercpp_dir, "build", "bin", "whisper-cli")

    if not os.path.exists(whisper_cli):
        raise FileNotFoundError(f"whisper-cli not found at: {whisper_cli}")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found at: {model_path}")

    cmd = [
        whisper_cli,
        "-m", model_path,
        "-f", wav_path,
        "--no-timestamps",
    ]

    p = _run(cmd, timeout=90)
    if p.returncode != 0:
        raise RuntimeError(
            "whisper-cli failed:\n"
            f"CMD: {' '.join(cmd)}\n"
            f"STDERR:\n{p.stderr}\n"
            f"STDOUT:\n{p.stdout}"
        )

    lines = [ln.strip() for ln in p.stdout.splitlines() if ln.strip()]
    if not lines:
        return ""

    # Filter out non-transcript lines
    text_lines = []
    for ln in lines:
        low = ln.lower()
        if "whisper" in low and ("load" in low or "model" in low):
            continue
        if re.search(r"[a-zA-Z]", ln):
            text_lines.append(ln)

    return text_lines[-1] if text_lines else ""


# =====================================================
# MAIN LISTEN FUNCTION (ROBUST VAD)
# =====================================================

def listen_question_near_realtime(
    max_seconds: float = 12.0,
    chunk_s: float = 1.0,
    silence_chunks_to_stop: int = 2,

    # --- Dynamic noise calibration ---
    calibrate_chunks: int = 2,
    start_mult: float = 2.6,
    stop_mult: float = 1.9,
    start_offset: int = 60,
    stop_offset: int = 40,

    # --- Guardrails ---
    min_speech_chunks: int = 1,
    max_total_chunks: int = 30,
    debug_rms: bool = False,
    automatic: bool = False,
    calibration_state=None,
) -> str:
    """
    Continuously captures audio, then transcribes the complete question.

    Features:
    - Ambient noise calibration before the timestamped ready signal
    - Hysteresis (start threshold > stop threshold)
    - Requires actual speech before stopping
    """
    if chunk_s <= 0 or max_seconds <= 0 or max_total_chunks <= 0:
        raise ValueError("Recording duration and chunk limits must be positive")

    # AUTOMATIC START: wait continuously for speech using 20 ms WebRTC VAD frames.
    # Manual capture retains its existing timing and return type.
    vad = None
    if automatic:
        import webrtcvad
        vad = webrtcvad.Vad(2)
        chunk_s = .02
        silence_chunks_to_stop = 50
        min_speech_chunks = 10
        calibrate_chunks = 50
    started = time.monotonic()

    def event(message):
        stamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        print(f"[MIC {stamp} +{time.monotonic() - started:.3f}s] {message}", flush=True)

    # One ALSA process for calibration and speech: no device reopen gaps.
    rate = 16000
    block_bytes = max(2, int(rate * chunk_s) * 2)
    blocks = queue.Queue()
    with tempfile.TemporaryFile() as errors:
        proc = subprocess.Popen(
            ["arecord", "-q", "-D", USB_MIC_ALSA, "-t", "raw",
             "-f", "S16_LE", "-r", str(rate), "-c", "1"],
            stdout=subprocess.PIPE, stderr=errors,
        )

        def read_audio():
            try:
                while True:
                    data = proc.stdout.read(block_bytes)
                    if not data:
                        break
                    blocks.put(data)
            finally:
                blocks.put(None)

        reader = threading.Thread(target=read_audio, daemon=True)
        reader.start()

        def next_block():
            try:
                data = blocks.get(timeout=chunk_s + 5)
            except queue.Empty:
                raise RuntimeError("Microphone timed out waiting for audio") from None
            if data is None or len(data) != block_bytes:
                proc.poll()
                errors.seek(0)
                detail = errors.read().decode(errors="replace").strip()
                raise RuntimeError(f"Microphone stopped before capture completed: {detail}")
            return data

        captured = []
        try:
            noise_samples = []
            # Even without calibration, verify actual PCM arrives before readiness.
            cached = automatic and calibration_state is not None and "noise_rms" in calibration_state
            for _ in range(1 if cached else max(1, calibrate_chunks)):
                noise_samples.append(audioop.rms(next_block(), 2))
            noise_samples.sort()
            noise_rms = calibration_state["noise_rms"] if cached else (noise_samples[len(noise_samples) // 2] if calibrate_chunks else 0)
            if automatic and calibration_state is not None:
                # AUTOMATIC START: reuse calibration across answers instead of a deaf
                # one-second calibration window on every return to listening.
                calibration_state["noise_rms"] = noise_rms
            start_threshold = max(200, min(1500, int(noise_rms * start_mult + start_offset)))
            stop_threshold = max(150, min(start_threshold - 50, int(noise_rms * stop_mult + stop_offset)))
            event("Listening - speak now")
            heard = silent = 0
            speaking = False
            quiet_frames = 0
            frames_left = max(1, int(max_seconds * rate))
            preroll = deque(maxlen=15)
            i = 0
            while automatic or i < min(max_total_chunks, int(max_seconds / chunk_s) + 1):
                i += 1
                data = next_block()[:frames_left * 2]
                rms = audioop.rms(data, 2)
                if automatic and not speaking:
                    quiet_frames = quiet_frames + 1 if rms == 0 else 0
                    if quiet_frames == 3000:
                        event("Audio is arriving but has been all-zero for 60 seconds; check mute/device with a recording test")
                is_speech = rms >= (stop_threshold if speaking else start_threshold)
                if vad is not None:
                    is_speech = is_speech and vad.is_speech(data, rate)
                    if not speaking and not is_speech and rms < start_threshold:
                        # Slowly track quiet room changes; never learn loud motor noise.
                        noise_rms = .995 * noise_rms + .005 * rms
                        start_threshold = max(200, min(1500, int(noise_rms * start_mult + start_offset)))
                        stop_threshold = max(150, min(start_threshold - 50, int(noise_rms * stop_mult + stop_offset)))
                        if calibration_state is not None:
                            calibration_state["noise_rms"] = noise_rms
                # Keep leading audio and pauses so words are never cut at VAD boundaries.
                if automatic and not speaking:
                    preroll.append(data)
                    if is_speech:
                        captured.extend(preroll)
                else:
                    captured.append(data)
                if is_speech:
                    speaking = True
                    heard += 1
                    silent = 0
                elif speaking:
                    silent += 1
                    if silent >= silence_chunks_to_stop:
                        if automatic and heard < min_speech_chunks:
                            # AUTOMATIC START: reject clicks and brief noise without Whisper.
                            captured.clear()
                            preroll.clear()
                            speaking = False
                            heard = silent = 0
                            frames_left = max(1, int(max_seconds * rate))
                            continue
                        break
                if speaking or not automatic:
                    frames_left -= len(data) // 2
                if frames_left <= 0:
                    break
            event("Captured")
        finally:
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            reader.join(timeout=2)
            proc.stdout.close()

    if not speaking:
        return ""
    with tempfile.TemporaryDirectory() as td:
        wav_path = os.path.join(td, "question.wav")
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(b"".join(captured))
        try:
            text = re.sub(r"\s+", " ", transcribe_wav(wav_path).strip())
        except Exception as exc:
            if automatic:
                return AudioResult("TRANSCRIPTION_ERROR", reason=str(exc))
            raise
        event("Transcribed")
        return validate_transcript(text) if automatic else text


# AUTOMATIC START: rejected audio never becomes a word-bank/model question.
@dataclass(frozen=True)
class AudioResult:
    status: str
    text: str = ""
    reason: str = ""


def validate_transcript(text):
    cleaned = re.sub(r"\[[^\]]*\]|\([^)]*\)|<\|[^|]*\|>", "", text).strip()
    if not re.search(r"[a-zA-Z]", cleaned):
        return AudioResult("BACKGROUND_NOISE", reason="No intelligible transcript")
    if cleaned.lower().strip(" .!?") in {"inaudible", "unintelligible", "background noise", "silence", "music", "blank_audio"}:
        return AudioResult("BACKGROUND_NOISE", reason="Non-speech annotation")
    words = cleaned.lower().split()
    if len(words) >= 6 and len(set(words)) == 1:
        return AudioResult("BACKGROUND_NOISE", reason="Repetitive transcription artifact")
    return AudioResult("SPEECH", text=cleaned)
