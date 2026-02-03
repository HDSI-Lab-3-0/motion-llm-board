# openrouter/pi_whispercpp.py
import subprocess
import tempfile
import os
import re
import wave
import audioop
from typing import Optional, List

USB_MIC_ALSA = "plughw:3,0"

WHISPERCPP_DIR = "/home/ouijaboard/whisper.cpp"
MODEL_PATH = "/home/ouijaboard/whisper.cpp/models/ggml-tiny.en.bin"


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
    Debian/arecord often requires -d to be an INTEGER.
    We record in whole seconds.
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
    p = _run(cmd, timeout=dur_int + 6)
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
    Uses stdlib only.
    """
    with wave.open(wav_path, "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        frames = wf.readframes(wf.getnframes())

    if n_channels != 1:
        # if stereo, downmix by taking left channel chunks is more work;
        # but your arecord command records mono, so this is mostly a safety guard.
        pass

    # RMS for 16-bit signed audio
    return audioop.rms(frames, sampwidth)


def transcribe_wav(
    wav_path: str,
    whispercpp_dir: str = WHISPERCPP_DIR,
    model_path: str = MODEL_PATH,
) -> str:
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

    # Keep transcript-ish lines
    text_lines = []
    for ln in lines:
        low = ln.lower()
        if "whisper" in low and ("load" in low or "model" in low):
            continue
        if re.search(r"[A-Za-z]", ln):
            text_lines.append(ln)

    return text_lines[-1] if text_lines else ""


def listen_question_near_realtime(
    max_seconds: float = 12.0,
    chunk_s: float = 1.0,
    silence_chunks_to_stop: int = 2,
    rms_threshold: int = 250,        # <-- main knob (increase if never stops)
    min_speech_chunks: int = 1,      # require at least this many "speech" chunks before stopping
) -> str:
    """
    Records/transcribes short chunks until it detects you've stopped speaking.
    Uses RMS (audio amplitude) to detect silence so it actually stops.
    """
    if chunk_s < 1.0:
        chunk_s = 1.0

    chunks = int(max_seconds // chunk_s) + 1
    collected: List[str] = []

    heard_speech_chunks = 0
    silent_streak = 0

    with tempfile.TemporaryDirectory() as td:
        for i in range(chunks):
            wav_path = os.path.join(td, f"chunk_{i}.wav")
            record_wav(wav_path, duration_s=chunk_s)

            rms = wav_rms(wav_path)

            # If chunk is quiet, count silence (don’t transcribe)
            if rms < rms_threshold:
                if heard_speech_chunks >= min_speech_chunks:
                    silent_streak += 1
                    if silent_streak >= silence_chunks_to_stop:
                        break
                continue

            # Loud enough = speech chunk
            heard_speech_chunks += 1
            silent_streak = 0

            t = transcribe_wav(wav_path).strip()
            t = re.sub(r"\s+", " ", t)
            if t:
                collected.append(t)

    joined = " ".join(collected).strip()
    joined = re.sub(r"\s+", " ", joined)

    # Light de-dupe: collapse exact repeated phrases
    joined = re.sub(r"\b(.+?)\s+\1\b", r"\1", joined, flags=re.IGNORECASE)

    return joined

