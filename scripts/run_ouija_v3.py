import subprocess
import time
import re
import sys
import selectors
from pathlib import Path

# ---------- Paths / Envs ----------
REPO_ROOT = Path(__file__).resolve().parents[1]

WHISPER_PY = "/Users/hanatjendrawasi/miniconda3/envs/whisperenv/bin/python"
WHISPER_SCRIPT = str(Path.home() / "realtime-whisper" / "transcribe_demo.py")

TINKER_PY = "/Users/hanatjendrawasi/miniconda3/envs/motion-llm/bin/python"
TINKER_SERVER = str(REPO_ROOT / "scripts" / "tinker_server.py")
TINKER_CWD = str(REPO_ROOT)

# ---------- Settings ----------
WHISPER_FINAL_RE = re.compile(r"^FINAL:\s*(.*)\s*$")
TINKER_FINAL_RE = re.compile(r"^FINAL:\s*(.*)\s*$")

COOLDOWN = 2.5
DUP_WINDOW = 6.0
YES_NO_MAYBE = {"YES", "NO", "MAYBE"}

# Optional: simple "does this look like a question" filter
QUESTION_WORDS = (
    "should", "can", "could", "would", "will",
    "is", "are", "do", "does", "did",
    "what", "why", "how", "when", "where", "who"
)

def looks_like_question(s: str) -> bool:
    s2 = s.strip().lower()
    if len(s2) < 3:
        return False
    if s2 in ("you", "yeah", "hey", "hi", "hello"):
        return False
    if s2.endswith("?"):
        return True
    return any(s2.startswith(w + " ") for w in QUESTION_WORDS)


# ---------- Tinker ----------
def start_tinker_server():
    """
    Starts the persistent Tinker server (stdin/stdout).
    NOTE: Adjust temperature / timeout flags as you like.
    """
    return subprocess.Popen(
        [
            TINKER_PY,
            TINKER_SERVER,
            "--max_new_tokens", "3",
            "--temperature", "0.7",   # was 0.0; 0.7 often avoids "always MAYBE"
            "--timeout_s", "30",
        ],
        cwd=TINKER_CWD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )


def call_tinker(tinker_proc, text: str, timeout_s: float = 45.0) -> str:
    """
    Send one question to the persistent Tinker server, return YES/NO/MAYBE.
    Robust to server log lines being mixed into stdout, and supports:
      - "YES" / "NO" / "MAYBE"
      - "FINAL: YES" / etc
      - lines containing YES/NO/MAYBE somewhere
    Uses selectors to avoid blocking forever on readline().
    """
    assert tinker_proc.stdin and tinker_proc.stdout

    text = text.strip()
    if not text:
        return "MAYBE"

    # Send request
    t0 = time.time()
    tinker_proc.stdin.write(text + "\n")
    tinker_proc.stdin.flush()

    # Wait for output with timeout
    sel = selectors.DefaultSelector()
    sel.register(tinker_proc.stdout, selectors.EVENT_READ)

    while True:
        if (time.time() - t0) > timeout_s:
            print(f"[TINKER] timeout after {timeout_s:.0f}s → MAYBE", flush=True)
            return "MAYBE"

        events = sel.select(timeout=0.25)
        if not events:
            continue

        line = tinker_proc.stdout.readline()
        if not line:
            raise RuntimeError("Tinker server stopped unexpectedly.")

        s = line.strip()
        if not s:
            continue

        up = s.upper()

        # 1) exact label
        if up in YES_NO_MAYBE:
            dt = time.time() - t0
            print(f"[TINKER] took {dt:.1f}s", flush=True)
            return up

        # 2) FINAL: label
        m = TINKER_FINAL_RE.match(s)
        if m:
            cand = (m.group(1) or "").strip().upper()
            if cand in YES_NO_MAYBE:
                dt = time.time() - t0
                print(f"[TINKER] took {dt:.1f}s", flush=True)
                return cand

        # 3) label somewhere in the line (last resort)
        for tok in ("YES", "NO", "MAYBE"):
            if tok in up:
                dt = time.time() - t0
                print(f"[TINKER] took {dt:.1f}s", flush=True)
                return tok

        # Otherwise it's a log line
        print(f"[TINKER LOG] {s}", flush=True)


# ---------- Main ----------
def main():
    # Start Tinker once
    tinker_proc = start_tinker_server()

    # Warmup
    print("[WARMUP] Warming up Tinker (first call may be slow)...", flush=True)
    warm = call_tinker(tinker_proc, "warm up", timeout_s=120.0)
    print(f"[WARMUP] Done (got {warm}).\n", flush=True)

    # Start Whisper
    whisper = subprocess.Popen(
        [
            WHISPER_PY,
            WHISPER_SCRIPT,
            "--model", "base",
            "--record_timeout", "1",
            "--phrase_timeout", "1.2",
            "--energy_threshold", "200",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    last_fire = 0.0
    last_text, last_text_t = "", 0.0

    try:
        assert whisper.stdout is not None

        for line in whisper.stdout:
            line = line.rstrip("\n")

            # IMPORTANT: Don't print every Whisper line (it spams the full transcript)
            # Only print FINAL lines so your terminal stays clean.
            m = WHISPER_FINAL_RE.match(line)
            if not m:
                continue

            text = (m.group(1) or "").strip()
            now = time.time()

            # Skip empty/garbage finals
            if not text or len(text) < 3:
                continue

            # Optional: ignore non-questions (filters "You", "yeah", etc.)
            if not looks_like_question(text):
                # Uncomment to debug skipped finals:
                # print(f"[SKIP FINAL] {text!r}", flush=True)
                continue

            # Print the FINAL we accepted
            print(f"FINAL: {text}", flush=True)

            # Suppress duplicates within window
            if text == last_text and (now - last_text_t) < DUP_WINDOW:
                continue
            last_text, last_text_t = text, now

            # Cooldown so it doesn't double-trigger
            if (now - last_fire) < COOLDOWN:
                continue

            print(f"\n[QUESTION] {text}", flush=True)
            resp = call_tinker(tinker_proc, text, timeout_s=45.0)
            print(f"[RESPONSE] {resp}\n", flush=True)

            last_fire = time.time()

    except KeyboardInterrupt:
        pass
    finally:
        try:
            whisper.terminate()
        except Exception:
            pass
        try:
            tinker_proc.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    main()

