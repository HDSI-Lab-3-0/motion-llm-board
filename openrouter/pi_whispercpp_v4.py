# openrouter/pi_whispercpp_v3.py
import subprocess
import tempfile
import os
import re
import wave
import audioop
from typing import Optional, List

# =====================================================
# AUDIO / WHISPER CONFIG
# =====================================================

USB_MIC_ALSA = "plughw:3,0"   # change if needed
WHISPERCPP_DIR = "/home/ouijaboard/whisper.cpp"
MODEL_PATH = "/home/ouijaboard/whisper.cpp/models/ggml-tiny.en.bin"


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
) -> str:
    """
    Records/transcribes short chunks until speech ends.

    Features:
    - Ambient noise calibration
    - Hysteresis (start threshold > stop threshold)
    - Requires actual speech before stopping
    """
    if chunk_s < 1.0:
        chunk_s = 1.0

    chunks = int(max_seconds // chunk_s) + 1
    chunks = min(chunks, max_total_chunks)

    collected: List[str] = []
    heard_speech_chunks = 0
    silent_streak = 0
    speaking_started = False

    def clamp(x: int, lo: int, hi: int) -> int:
        return max(lo, min(hi, x))

    with tempfile.TemporaryDirectory() as td:
        # --------------------------------
        # 1) Ambient noise calibration
        # --------------------------------
        noise_samples = []

        for i in range(max(0, calibrate_chunks)):
            wav_path = os.path.join(td, f"calib_{i}.wav")
            record_wav(wav_path, duration_s=chunk_s)
            noise_samples.append(wav_rms(wav_path))

        if noise_samples:
            noise_samples.sort()
            noise_rms = noise_samples[len(noise_samples) // 2]  # median
        else:
            noise_rms = 0

        start_threshold = int(noise_rms * start_mult + start_offset)
        stop_threshold = int(noise_rms * stop_mult + stop_offset)

        start_threshold = clamp(start_threshold, 200, 1500)
        stop_threshold = clamp(stop_threshold, 150, start_threshold - 50)

        if debug_rms:
            print(
                f"[VAD] noise_rms={noise_rms} "
                f"start_th={start_threshold} stop_th={stop_threshold}"
            )

        # --------------------------------
        # 2) Main recording loop
        # --------------------------------
        for i in range(chunks):
            wav_path = os.path.join(td, f"chunk_{i}.wav")
            record_wav(wav_path, duration_s=chunk_s)
            rms = wav_rms(wav_path)

            if debug_rms:
                print(
                    f"[VAD] chunk={i} rms={rms} "
                    f"speaking={speaking_started} silent={silent_streak}"
                )

            if not speaking_started:
                is_speech = rms >= start_threshold
                if is_speech:
                    speaking_started = True
            else:
                is_speech = rms >= stop_threshold

            if not is_speech:
                if speaking_started and heard_speech_chunks >= min_speech_chunks:
                    silent_streak += 1
                    if silent_streak >= silence_chunks_to_stop:
                        break
                continue

            # Speech detected
            heard_speech_chunks += 1
            silent_streak = 0

            t = transcribe_wav(wav_path).strip()
            t = re.sub(r"\s+", " ", t)
            if t:
                collected.append(t)

    joined = " ".join(collected).strip()
    joined = re.sub(r"\s+", " ", joined)

    # Collapse exact repeated phrases
    joined = re.sub(r"\b(.+?)\s+\1\b", r"\1", joined, flags=re.IGNORECASE)

    return joined

