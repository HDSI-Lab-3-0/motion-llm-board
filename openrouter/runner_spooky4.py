#!/usr/bin/env python3
"""
Maintained Pi runtime (package name retained for compatibility).

Updated for new Arduino hardware firmware.

Arduino now accepts commands like:
- SPELL HELLO
- YES
- NO
- CENTER
- WHERE

Pipeline:
speech -> Whisper -> local Ollama / wordbank -> Arduino command
"""

import os
import argparse
import signal
import time
from pathlib import Path
import random
import re
import requests
import serial
from serial.tools import list_ports
from dotenv import load_dotenv
from openrouter.spelling import extract_spell_target
from openrouter.response_policy import personal_or_presence_response
from openrouter.routing import direct_response, normalize, select_bank, matches, offered_choices
from contextlib import nullcontext

# Load before importing speech settings; explicit shell variables take precedence.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from openrouter.pi_whispercpp_v4 import listen_question_near_realtime
from openrouter import pi_whispercpp_v4 as audio
from openrouter.status import publish_status as write_status, status_heartbeat, publish_progress
from openrouter.gpio_status_led import create_status_led

from openrouter.wordbanks_spooky3 import (
    YES_NO,
    KEYWORDS,
    WORD_BANKS,
)

_response_source = ""


def publish_status(status, **fields):
    global _response_source
    if status in {"THINKING", "LISTENING", "STARTING"}:
        _response_source = ""
    if status in {"READY", "LISTENING", "RESPONSE_READY", "MOVING", "THINKING", "ERROR", "STOPPED"}:
        status_led = globals().get("_active_status_led")
        if status_led:
            status_led.set_status(status)
    write_status(status, source=_response_source, **fields)


# =====================================================
# CONFIG
# =====================================================

HARDWARE_ENABLED = os.getenv("OUIJA_HARDWARE_ENABLED", "true").lower() in ("true", "1", "yes")

# On Mac this is usually /dev/cu.usbmodemXXXX.
# On Raspberry Pi this may be /dev/ttyACM0.
SERIAL_PORT = os.getenv("OUIJA_SERIAL_PORT", "/dev/ttyACM0")
SERIAL_BAUD = 115200

MODEL_NAME = os.getenv("OUIJA_LOCAL_MODEL", "llama3.2:3b")
OLLAMA_URL = os.getenv("OUIJA_OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_TIMEOUT = float(os.getenv("OUIJA_OLLAMA_TIMEOUT", "180"))
OLLAMA_CONTEXT = int(os.getenv("OUIJA_OLLAMA_CONTEXT", "2048"))

PRE_RESPONSE_PAUSE = 0.25


# =====================================================
# NEW HARDWARE BRIDGE
# =====================================================

def find_arduino_port():
    ports = list(list_ports.comports())

    for port in ports:
        name = port.device
        desc = (port.description or "").lower()

        if (
            "arduino" in desc
            or "usb serial" in desc
            or "usbmodem" in name
            or "usbserial" in name
            or "ch340" in desc
        ):
            return name

    return None


class OuijaArduinoBridge:
    def __init__(self, port=None, baud=115200):
        self.port = port or find_arduino_port()
        self.baud = baud
        self.ser = None

        if not self.port:
            raise RuntimeError("Arduino serial port not found.")

    def connect(self):
        print(f"[HW] Opening serial port: {self.port}")
        self.ser = serial.Serial(self.port, self.baud, timeout=1)

        # Opening serial often resets Arduino.
        # Your Arduino auto-runs HOMEALL on startup, so wait for it.
        time.sleep(2)
        self.ready = self.flush_startup(timeout_s=120 if getattr(self, "strict_automatic", False) else 15)

    def flush_startup(self, timeout_s=15):
        start = time.time()
        print("[HW] Reading Arduino startup output...")

        while time.time() - start < timeout_s:
            line = self.read_line()
            if line:
                print(f"[ARDUINO] {line}")

                if "READY_AT_CENTER" in line:
                    print("[HW] Arduino ready at center.")
                    return True

                if "ERR AUTO_HOME_FAILED" in line:
                    print("[HW] Arduino auto-home failed.")
                    return False

    def read_line(self):
        if not self.ser:
            return None

        raw = self.ser.readline()
        if not raw:
            return None

        return raw.decode(errors="ignore").strip()

    def send_command(self, command, wait_done=True, timeout_s=900):
        command = command.strip()

        if not command:
            return []

        print(f"[HW >>] {command}")
        if getattr(self, "strict_automatic", False):
            publish_progress("Command sent: " + command + " · awaiting completion")
        self.ser.write((command + "\n").encode())

        responses = []
        start = time.time()

        while time.time() - start < timeout_s:
            line = self.read_line()

            if not line:
                continue

            print(f"[HW <<] {line}")
            responses.append(line)
            if getattr(self, "strict_automatic", False):
                publish_progress("Arduino: " + line)

            if line.startswith("ERR"):
                if getattr(self, "strict_automatic", False):
                    raise RuntimeError(f"Arduino rejected command: {line}")
                break

            if not wait_done:
                break

            # SPELL ends with OK SPELL_DONE
            if command.upper().startswith("SPELL"):
                if line == "OK SPELL_DONE":
                    break

            # YES / NO / CENTER / GOTO usually produce DONE
            elif line.startswith("DONE"):
                break

            elif line in ("READY_AT_CENTER", "OK HOMEALL"):
                break

        # AUTOMATIC START: uncertain completion must not be treated as success.
        if getattr(self, "strict_automatic", False) and wait_done:
            completed = any(line == "OK SPELL_DONE" for line in responses) if command.upper().startswith("SPELL") else any(line.startswith("DONE") or line in ("READY_AT_CENTER", "OK HOMEALL") for line in responses)
            if not completed:
                raise TimeoutError("Arduino command completion not confirmed; command will not be replayed")
        return responses

    def spell_text(self, text):
        word = re.sub(r"[^A-Za-z0-9 ]", "", text or "").strip().upper()

        if not word:
            print("[HW] No valid word to spell.")
            return

        # Arduino special-cases SPELL YES / SPELL NO
        self.send_command(f"SPELL {word}", wait_done=True)

    def move_to_yes(self):
        self.send_command("YES", wait_done=True)

    def move_to_no(self):
        self.send_command("NO", wait_done=True)

    def center(self):
        self.send_command("CENTER", wait_done=True)

    def close(self):
        if self.ser:
            self.ser.close()
            self.ser = None


def sanitize_word(text):
    """
    Keep letters AND numbers and uppercase.
    YES and NO still stay YES/NO.
    """
    clean = re.sub(r"[^A-Za-z0-9]", "", text or "")
    return clean.upper()

# =====================================================
# LOCAL OLLAMA HELPER
# =====================================================

def ollama_completion(prompt: str, max_tokens: int = 8, temperature: float = 0.2, timeout_s: float = OLLAMA_TIMEOUT) -> str:
    """Return local generated text, or empty text for the existing fallbacks."""
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": temperature,
            "num_ctx": OLLAMA_CONTEXT,
        },
    }

    try:
        r = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=timeout_s,
        )
        if r.status_code != 200:
            print(f"[OLLAMA ERROR] status={r.status_code} body={r.text[:300]}; using existing fallback")
            return ""
        body = r.json()
        if not isinstance(body, dict) or not isinstance(body.get("response"), str):
            raise ValueError("Expected an Ollama JSON object with a string response")
        out = body["response"].strip()
        print(f"[OLLAMA RAW] {out!r} (validated by host decision layer)")
        return out
    except (requests.RequestException, ValueError) as e:
        print(f"[OLLAMA ERROR] {e}; using existing fallback")
        return ""


# =====================================================
# MODE CLASSIFICATION
# =====================================================

def classify_mode(question: str) -> str:
    q = normalize(question or "")
    if offered_choices(q):
        return "ONE_WORD"

    # YES/NO questions should move directly to YES or NO.
    looks_yesno = q.startswith((
        "is ", "are ", "am ", "do ", "does ", "did ",
        "should ", "can ", "could ", "will ", "would ",
        "was ", "were ", "have ", "has "
    ))

    # Open-ended questions should spell one word.
    open_question_starts = (
        "what ", "who ", "where ", "when ", "why ", "how ",
        "which ", "name "
    )

    if q.startswith(open_question_starts):
        return "ONE_WORD"

    if looks_yesno:
        return "YES_NO"

    # If the user says a topic phrase without a clear question, still give one spooky word.
    for cat, kws in KEYWORDS.items():
        if any(w in q for w in kws):
            return "ONE_WORD"

    # Fallback: ask the LLM to classify.
    prompt = f"""
Classify how a spooky classic Ouija board should answer.

Return ONLY one of these:
YES_NO
ONE_WORD

YES_NO = the answer should be exactly YES or NO.
ONE_WORD = the answer should be one short word.

Question:
{question.strip()}
""".strip()

    out = ollama_completion(prompt, max_tokens=4, temperature=0.1)
    out_up = (out or "").upper()

    if "ONE_WORD" in out_up:
        return "ONE_WORD"
    if "YES_NO" in out_up:
        return "YES_NO"

    return "ONE_WORD"


# =====================================================
# YES / NO ANSWER
# =====================================================

def answer_yes_no(question: str) -> str:
    global _response_source
    _response_source = "Rule · Yes/No"
    q = normalize(question or "")

    # Hard-coded spooky defaults so common Ouija questions feel intentional.
    yes_patterns = [
        "is anyone here",
        "is someone here",
        "is somebody here",
        "are you here",
        "are the spirits here",
        "spirit here",
        "ghost here",
        "with us",
        "in this room",
        "are you real",
        "can you hear me",
        "do you hear me",
        "are you watching",
    ]

    if any(p in q for p in yes_patterns):
        return "YES"

    no_patterns = [
        "should we stop",
        "should i stop",
        "are we alone",
        "is this fake",
        "are you fake",
    ]

    if any(p in q for p in no_patterns):
        return "NO"

    prompt = f"""
You are an oracle controlling a physical Ouija board.

Answer the user's question with EXACTLY ONE token:
YES
NO

Rules:
- You are NOT allowed to answer MAYBE.
- You must choose either YES or NO, even if the question is ambiguous.
- For classic Ouija presence questions like "is anyone here?" or "are the spirits here?", prefer YES.
- For spooky/paranormal questions, answer in a mysterious but decisive way.
- Do not add punctuation.
- Do not add extra words.

Question: {question.strip()}
""".strip()

    _response_source = "LLM · Yes/No"
    out = ollama_completion(prompt, max_tokens=2, temperature=0.05)
    out_up = sanitize_word(out)

    if out_up == "YES":
        return "YES"

    if out_up == "NO":
        return "NO"

    # Absolute safety net: NEVER return MAYBE.
    _response_source = "Random Yes/No · fallback"
    return random.choice(YES_NO)


# =====================================================
# WORD ORACLE
# =====================================================

def pick_one_word(question: str) -> str:
    global _response_source
    direct = direct_response(question)
    if direct:
        word, _response_source = direct
        return word
    q = (question or "").lower()

    # Hard override: weather questions should always be simple and sensible.
    # Example: "hows the weather" -> GOOD
    weather_phrases = [
        "weather", "forecast", "temperature", "temp",
        "rain", "raining", "sunny", "cloudy", "windy",
        "storm", "fog", "cold", "hot", "outside"
    ]

    if any(matches(q, w) for w in weather_phrases):
        _response_source = "Rule · Weather"
        return "GOOD"

    matched_category = select_bank(question)

    bank = WORD_BANKS.get(matched_category) or WORD_BANKS["generic"]

    # Ask the LLM to choose from the matched bank, not invent something too long/weird.
    # This keeps it spooky while still physically spellable.
    bank_text = ", ".join(bank)
    prompt = f"""
You are a classic Ouija board oracle.

Pick EXACTLY ONE word from this allowed list:
{bank_text}

Rules:
- Return only one word from the list.
- No punctuation.
- No explanations.
- Never return MAYBE.
- Pick a word that answers the user's actual topic.
- Keep it classic spooky, but if the user asks a normal question like food, choose a useful answer from that category.

Question: {question.strip()}
""".strip()

    out = ollama_completion(prompt, max_tokens=4, temperature=0.35)
    out_up = sanitize_word(out)

    safe_bank = [sanitize_word(w) for w in bank if sanitize_word(w) != "MAYBE"]

    if out_up in safe_bank:
        _response_source = "LLM · " + matched_category.title() + " bank"
        return out_up

    _response_source = "Word bank · " + matched_category.title() + " · fallback"
    return random.choice(safe_bank)


# =====================================================
# MAIN
# =====================================================

def check_automatic_dependencies():
    # AUTOMATIC START: service ordering alone does not mean the model is ready.
    cli = Path(audio.WHISPERCPP_DIR) / "build/bin/whisper-cli"
    if not cli.is_file() or not Path(audio.MODEL_PATH).is_file():
        raise RuntimeError("Whisper executable or model is missing")
    import webrtcvad  # Fail clearly before claiming readiness if not installed.
    url = OLLAMA_URL.rsplit("/api/", 1)[0] + "/api/tags"
    reply = requests.get(url, timeout=10)
    reply.raise_for_status()
    names = {m.get("name") for m in reply.json().get("models", [])}
    if MODEL_NAME not in names:
        raise RuntimeError(f"Ollama model not installed: {MODEL_NAME}")


def stop_automatic_service(signum, frame):
    # AUTOMATIC START: unwind capture's finally blocks on systemctl stop.
    raise KeyboardInterrupt


def main(auto_listen=False):
    # AUTOMATIC START: exclusive ownership applies to manual and service launches.
    lock = None
    if os.name == "posix":
        import fcntl
        lock = open(Path(__file__).resolve().parents[1] / ".ouija.lock", "a")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    previous_handler = None
    try:
        if auto_listen:
            previous_handler = signal.signal(signal.SIGTERM, stop_automatic_service)
        try:
            with status_heartbeat() if auto_listen else nullcontext():
                if auto_listen:
                    publish_status("STARTING", detail="Checking dependencies")
                    check_automatic_dependencies()
                _run_board(auto_listen)
        except Exception as exc:
            if auto_listen:
                publish_status("ERROR", board="UNKNOWN", detail=str(exc))
            raise
    finally:
        if previous_handler is not None:
            signal.signal(signal.SIGTERM, previous_handler)
        if lock:
            lock.close()


def _run_board(auto_listen):
    global _response_source, _active_status_led
    status_led = create_status_led()
    _active_status_led = status_led
    if auto_listen:
        publish_status("STARTING", board="CHECKING", detail="Starting automatic listener")
    if auto_listen:
        print(f"[AUTO START] Microphone: {audio.USB_MIC_ALSA}", flush=True)
    print(f"[LLM] Local Ollama: {MODEL_NAME} at {OLLAMA_URL}")
    if not auto_listen:
        print("[OUJIA] Press ENTER to listen; 'q' to quit; 't' for typed mode.")

    hw = None

    if HARDWARE_ENABLED:
        try:
            print("[HW] Connecting...")
            hw = OuijaArduinoBridge(port=SERIAL_PORT, baud=SERIAL_BAUD)
            hw.strict_automatic = auto_listen
            hw.connect()
            # AUTOMATIC START: require positive homing acknowledgement.
            if auto_listen and not hw.ready:
                raise RuntimeError("Arduino did not confirm READY_AT_CENTER")
            print("[HW] Ready")
            if auto_listen:
                publish_status("READY", board="READY", detail="Arduino homed")
                status_led.set_status("READY")
        except Exception as e:
            print(f"[HW] FAILED: {e}")
            if hw:
                hw.close()
            if auto_listen:
                raise
            hw = None

    last_response = None

    try:
        noise_log_at = 0.0
        calibration_state = {}
        while True:
            # AUTOMATIC START: no stdin, no terminal, and no listening during movement.
            if auto_listen:
                time.sleep(float(os.getenv("OUIJA_AUTO_SETTLE_SECONDS", "1")))
            cmd = "" if auto_listen else input("\n[READY] Press ENTER to listen, 't' to type, or 'q' to quit: ").strip().lower()

            if cmd == "q":
                break

            if cmd == "t":
                text = input("[TYPE QUESTION] ").strip()
                if not text:
                    continue
            else:
                if auto_listen:
                    publish_status("LISTENING", board="READY")
                    status_led.set_status("LISTENING")
                try:
                    text = listen_question_near_realtime(
                        max_seconds=14.0,
                        chunk_s=0.25,
                        silence_chunks_to_stop=4,
                        calibrate_chunks=4,
                        max_total_chunks=56,
                        min_speech_chunks=1,
                        debug_rms=False,
                        automatic=auto_listen,
                        calibration_state=calibration_state,
                    )
                except Exception as e:
                    print(f"[MIC ERROR] {e}")
                    if auto_listen:
                        publish_status("ERROR", board="READY", detail=str(e))
                        status_led.set_status("ERROR")
                        raise  # Service retries with a delay; a broken mic is not silence.
                    continue

                if auto_listen:
                    if text.status != "SPEECH":
                        display_status = {
                            "SILENCE": "LISTENING",
                            "BACKGROUND_NOISE": "BACKGROUND_NOISE",
                            "TRANSCRIPTION_ERROR": "ERROR",
                        }.get(text.status, "ERROR")
                        publish_status(display_status, board="READY", detail=text.reason)
                        status_led.set_status(display_status)
                        if time.monotonic() - noise_log_at >= 10:
                            print(f"[AUDIO] {text.status}: {text.reason}", flush=True)
                            noise_log_at = time.monotonic()
                        if text.status == "TRANSCRIPTION_ERROR":
                            time.sleep(5)
                        continue
                    text = text.text

                if auto_listen:
                    publish_status("THINKING", heard=text, board="READY")
                    status_led.set_status("THINKING")

                if not text:
                    print("[NO SPEECH] Try again.")
                    continue

            print(f"\n[QUESTION] {text}")
            time.sleep(PRE_RESPONSE_PAUSE)

            # Explicit spelling is an instruction, not a yes/no capability question.
            spell_target = extract_spell_target(text)
            if spell_target:
                _response_source = "Rule · Spelling"
                print(f"[MODE] SPELL\n[RESPONSE] {spell_target}\n[SOURCE] rules")
                if auto_listen:
                    publish_status("MOVING", heard=text, response=spell_target, board="MOVING")
                    status_led.set_status("MOVING")
                if hw:
                    try:
                        hw.spell_text(spell_target)
                        last_response = spell_target
                        if auto_listen:
                            publish_status("RESPONSE_READY", heard=text, response=spell_target, board="READY")
                            status_led.set_status("RESPONSE_READY")
                    except Exception as e:
                        print(f"[HW ERROR] {e}")
                        if auto_listen:
                            raise
                continue

            policy_response = personal_or_presence_response(text)
            if policy_response == "WAIT":
                _response_source = "Rule · Personal unknown"
                print("[MODE] PERSONAL_UNKNOWN\n[RESPONSE] WAIT\n[SOURCE] rules")
                if auto_listen:
                    publish_status("MOVING", heard=text, response="WAIT", board="MOVING")
                    status_led.set_status("MOVING")
                if hw:
                    try:
                        hw.spell_text("WAIT")
                        last_response = "WAIT"
                        if auto_listen:
                            publish_status("RESPONSE_READY", heard=text, response="WAIT", board="READY")
                    except Exception as e:
                        print(f"[HW ERROR] {e}")
                        if auto_listen:
                            raise
                continue

            direct = direct_response(text) if policy_response is None else None
            mode = "ONE_WORD" if direct else ("YES_NO" if policy_response == "YES" else classify_mode(text))
            print(f"[MODE] {mode}")

            if mode == "YES_NO":
                ans = answer_yes_no(text)
                print(f"[RESPONSE] {ans}")
                if auto_listen:
                    publish_status("MOVING", heard=text, response=ans, board="MOVING")

                if hw:
                    try:
                        # If the same YES/NO answer repeats, move to center first
                        # so the board visibly answers again instead of staying still.
                        if ans in ("YES", "NO") and ans == last_response:
                            print("[REPEAT ANSWER] Moving to CENTER before repeating answer.")
                            hw.center()
                            time.sleep(0.4)

                        # Arduino handles SPELL YES and SPELL NO as special direct targets.
                        hw.spell_text(ans)
                        last_response = ans
                        if auto_listen:
                            publish_status("RESPONSE_READY", heard=text, response=ans, board="READY")
                            status_led.set_status("RESPONSE_READY")

                    except Exception as e:
                        print(f"[HW ERROR] {e}")
                        if auto_listen:
                            raise

            else:
                if direct:
                    word, _response_source = direct
                else:
                    word = pick_one_word(text)
                print(f"[RESPONSE] {word}")
                if auto_listen:
                    publish_status("MOVING", heard=text, response=word, board="MOVING")
                    status_led.set_status("MOVING")

                if hw:
                    try:
                        hw.spell_text(word)
                        last_response = word
                        if auto_listen:
                            publish_status("RESPONSE_READY", heard=text, response=word, board="READY")
                            status_led.set_status("RESPONSE_READY")
                    except Exception as e:
                        print(f"[HW ERROR] {e}")
                        if auto_listen:
                            raise

    except KeyboardInterrupt:
        print("\n[EXIT] Stopped by user")
        if auto_listen:
            publish_status("STOPPED", board="UNKNOWN", detail="Listener stopped")

    finally:
        status_led.close()
        if hw:
            hw.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto-listen", action="store_true", help="AUTOMATIC START: listen without keyboard input")
    main(auto_listen=parser.parse_args().auto_listen)
