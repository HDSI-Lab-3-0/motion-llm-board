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

# Load before importing speech settings; explicit shell variables take precedence.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from openrouter.pi_whispercpp_v4 import listen_question_near_realtime

from openrouter.wordbanks_spooky3 import (
    YES_NO,
    KEYWORDS,
    WORD_BANKS,
)

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
        self.flush_startup(timeout_s=15)

    def flush_startup(self, timeout_s=15):
        start = time.time()
        print("[HW] Reading Arduino startup output...")

        while time.time() - start < timeout_s:
            line = self.read_line()
            if line:
                print(f"[ARDUINO] {line}")

                if "READY_AT_CENTER" in line:
                    print("[HW] Arduino ready at center.")
                    return

                if "ERR AUTO_HOME_FAILED" in line:
                    print("[HW] Arduino auto-home failed.")
                    return

    def read_line(self):
        if not self.ser:
            return None

        raw = self.ser.readline()
        if not raw:
            return None

        return raw.decode(errors="ignore").strip()

    def send_command(self, command, wait_done=True, timeout_s=120):
        command = command.strip()

        if not command:
            return []

        print(f"[HW >>] {command}")
        self.ser.write((command + "\n").encode())

        responses = []
        start = time.time()

        while time.time() - start < timeout_s:
            line = self.read_line()

            if not line:
                continue

            print(f"[HW <<] {line}")
            responses.append(line)

            if line.startswith("ERR"):
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

        return responses

    def spell_text(self, text):
        word = sanitize_word(text)

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
    q = (question or "").lower().strip()

    # YES/NO questions should move directly to YES or NO.
    looks_yesno = q.endswith("?") or q.startswith((
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
    q = (question or "").lower().strip()

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

    out = ollama_completion(prompt, max_tokens=2, temperature=0.05)
    out_up = sanitize_word(out)

    if out_up == "YES":
        return "YES"

    if out_up == "NO":
        return "NO"

    # Absolute safety net: NEVER return MAYBE.
    return random.choice(YES_NO)


# =====================================================
# WORD ORACLE
# =====================================================

def pick_one_word(question: str) -> str:
    q = (question or "").lower()

    # Hard override: weather questions should always be simple and sensible.
    # Example: "hows the weather" -> GOOD
    weather_phrases = [
        "weather", "forecast", "temperature", "temp",
        "rain", "raining", "sunny", "cloudy", "windy",
        "storm", "fog", "cold", "hot", "outside"
    ]

    if any(w in q for w in weather_phrases):
        return "GOOD"

    # Score categories by keyword matches.
    # This prevents broad categories like "advice" from stealing questions like
    # "what should I eat" when "eat" clearly means food.
    category_scores = {}

    for cat, kws in KEYWORDS.items():
        score = 0
        for kw in kws:
            if kw in q:
                # Longer keyword phrases are more specific, so they get more weight.
                score += max(1, len(kw.split()))
        if score > 0:
            category_scores[cat] = score

    if category_scores:
        matched_category = max(category_scores, key=category_scores.get)
    else:
        matched_category = "generic"

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
        return out_up

    return random.choice(safe_bank)


# =====================================================
# MAIN
# =====================================================

def main():
    print(f"[LLM] Local Ollama: {MODEL_NAME} at {OLLAMA_URL}")
    print("[OUJIA] Press ENTER to listen.")
    print("       Type 'q' + ENTER to quit.")
    print("       Type 't' + ENTER for typed test mode.\n")

    hw = None

    if HARDWARE_ENABLED:
        try:
            print("[HW] Connecting...")
            hw = OuijaArduinoBridge(port=SERIAL_PORT, baud=SERIAL_BAUD)
            hw.connect()
            print("[HW] Ready")
        except Exception as e:
            print(f"[HW] FAILED: {e}")
            hw = None

    last_response = None

    try:
        while True:
            cmd = input("\n[READY] Press ENTER to listen, 't' to type, or 'q' to quit: ").strip().lower()

            if cmd == "q":
                break

            if cmd == "t":
                text = input("[TYPE QUESTION] ").strip()
                if not text:
                    continue
            else:
                print("[MIC] Listening...")

                try:
                    text = listen_question_near_realtime(
                        max_seconds=14.0,
                        chunk_s=2.0,
                        silence_chunks_to_stop=1,
                        calibrate_chunks=3,
                        min_speech_chunks=1,
                        debug_rms=True
                    )
                except Exception as e:
                    print(f"[MIC ERROR] {e}")
                    continue

                if not text:
                    print("[NO SPEECH] Try again.")
                    continue

            print(f"\n[QUESTION] {text}")
            time.sleep(PRE_RESPONSE_PAUSE)

            # Explicit spelling is an instruction, not a yes/no capability question.
            spell_target = extract_spell_target(text)
            if spell_target:
                print(f"[MODE] SPELL\n[RESPONSE] {spell_target}\n[SOURCE] rules")
                if hw:
                    try:
                        hw.spell_text(spell_target)
                        last_response = spell_target
                    except Exception as e:
                        print(f"[HW ERROR] {e}")
                continue

            policy_response = personal_or_presence_response(text)
            if policy_response == "WAIT":
                print("[MODE] PERSONAL_UNKNOWN\n[RESPONSE] WAIT\n[SOURCE] rules")
                if hw:
                    try:
                        hw.spell_text("WAIT")
                        last_response = "WAIT"
                    except Exception as e:
                        print(f"[HW ERROR] {e}")
                continue

            mode = "YES_NO" if policy_response == "YES" else classify_mode(text)
            print(f"[MODE] {mode}")

            if mode == "YES_NO":
                ans = answer_yes_no(text)
                print(f"[RESPONSE] {ans}")

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

                    except Exception as e:
                        print(f"[HW ERROR] {e}")

            else:
                word = pick_one_word(text)
                print(f"[RESPONSE] {word}")

                if hw:
                    try:
                        hw.spell_text(word)
                        last_response = word
                    except Exception as e:
                        print(f"[HW ERROR] {e}")

    except KeyboardInterrupt:
        print("\n[EXIT] Stopped by user")

    finally:
        if hw:
            hw.close()


if __name__ == "__main__":
    main()
