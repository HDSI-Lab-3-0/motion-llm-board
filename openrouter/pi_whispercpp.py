# openrouter/pi_whispercpp.py
import subprocess
import tempfile
import os
import re
from typing import Optional

USB_MIC_ALSA = "plughw:3,0"  # from your arecord -l (card 3, device 0)

def _run(cmd: list[str], timeout: Optional[float] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )

def record_wav(
    out_wav: str,
    duration_s: float = 1.6,
    device: str = USB_MIC_ALSA,
    rate: int = 16000,
) -> None:
    # arecord writes wav if filename ends with .wav
    cmd = [
        "arecord",
        "-D", device,
        "-f", "S16_LE",
        "-r", str(rate),
        "-c", "1",
        "-d", str(duration_s),
        out_wav,
    ]
    p = _run(cmd, timeout=duration_s + 3)
    if p.returncode != 0:
        raise RuntimeError(f"arecord failed:\nSTDERR:\n{p.stderr}\nSTDOUT:\n{p.stdout}")

def transcribe_wav(
    wav_path: str,
    whispercpp_dir: str = "/home/ouijaboard/whisper.cpp",
    model_path: str = "/home/ouijaboard/whisper.cpp/models/ggml-tiny.en.bin",
) -> str:
    whisper_cli = os.path.join(whispercpp_dir, "build", "bin", "whisper-cli")

    cmd = [
        whisper_cli,
        "-m", model_path,
        "-f", wav_path,
        "--no-timestamps",
    ]
    p = _run(cmd, timeout=60)

    if p.returncode != 0:
        raise RuntimeError(f"whisper-cli failed:\nSTDERR:\n{p.stderr}\nSTDOUT:\n{p.stdout}")

    # whisper-cli prints lines; actual text is usually on the last non-empty line(s)
    lines = [ln.strip() for ln in p.stdout.splitlines() if ln.strip()]
    if not lines:
        return ""

    # Heuristic: keep lines that have letters and aren't just stats
    text_lines = []
    for ln in lines:
        if "whisper" in ln.lower() and "load" in ln.lower():
            continue
        if re.search(r"[A-Za-z]", ln):
            text_lines.append(ln)

    # Often the final transcript is at the end
    return text_lines[-1] if text_lines else ""

def listen_question_near_realtime(
    max_seconds: float = 10.0,
    chunk_s: float = 1.6,
    silence_chunks_to_stop: int = 2,
) -> str:
    """
    Records and transcribes short chunks until it detects you've stopped speaking.
    Returns the accumulated text.
    """
    chunks = int(max_seconds // chunk_s) + 1
    collected: list[str] = []

    heard_speech = False
    silent_streak = 0

    with tempfile.TemporaryDirectory() as td:
        for i in range(chunks):
            wav_path = os.path.join(td, f"chunk_{i}.wav")
            record_wav(wav_path, duration_s=chunk_s)

            t = transcribe_wav(wav_path).strip()
            # Normalize a bit
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

    # Join chunks; de-duplicate obvious repeats
    joined = " ".join(collected).strip()
    joined = re.sub(r"\s+", " ", joined)
    return joined

