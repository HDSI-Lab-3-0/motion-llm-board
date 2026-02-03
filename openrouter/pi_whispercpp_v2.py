# openrouter/pi_whispercpp.py
import subprocess
import tempfile
import os
import re
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
    Record a WAV clip with arecord.
    NOTE: Many arecord builds require -d (duration) to be an INTEGER.
    So we round up to the nearest whole second.
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

    # Keep lines that look like transcript (letters) and ignore noisy logs
    text_lines = []
    for ln in lines:
        low = ln.lower()
        if "whisper" in low and ("load" in low or "model" in low):
            continue
        if re.search(r"[A-Za-z]", ln):
            text_lines.append(ln)

    return text_lines[-1] if text_lines else ""


def listen_question_near_realtime(
    max_seconds: float = 10.0,
    chunk_s: float = 1.0,              # keep this at 1.0 on Debian arecord
    silence_chunks_to_stop: int = 2,
) -> str:
    """
    Records/transcribes short chunks until it detects you've stopped speaking.
    Returns the accumulated text.
    """
    # duration is integer anyway; this is just a guard
    if chunk_s < 1.0:
        chunk_s = 1.0

    chunks = int(max_seconds // chunk_s) + 1
    collected: List[str] = []

    heard_speech = False
    silent_streak = 0

    with tempfile.TemporaryDirectory() as td:
        for i in range(chunks):
            wav_path = os.path.join(td, f"chunk_{i}.wav")
            record_wav(wav_path, duration_s=chunk_s)

            t = transcribe_wav(wav_path).strip()
            t = re.sub(r"\s+", " ", t)

            if t:
                heard_speech = True
                silent_streak = 0
                collected.append(t)
            else:
                if heard_speech:
                    silent_streak += 1
                    if silent_streak >= silence_chunks_to_stop:
                        break

    joined = " ".join(collected).strip()
    joined = re.sub(r"\s+", " ", joined)

    # Basic de-dupe: if chunks repeat exactly, collapse repeats
    joined = re.sub(r"\b(\w+(?:\s+\w+)*)\s+\1\b", r"\1", joined, flags=re.IGNORECASE)

    return joined

