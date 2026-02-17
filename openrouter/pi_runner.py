#!/usr/bin/env python3
"""
openrouter/pi_runner.py

- Records a question from a USB mic via whisper.cpp near-realtime listener
- Uses OpenRouter LLM for:
  (1) mode classification: YES_NO_MAYBE vs ONE_WORD
  (2) YES/NO/MAYBE answering (no longer random for fact questions)
- Sends answer to Arduino-controlled Ouija hardware (optional)

Run:
  python -m openrouter.pi_runner
or:
  python openrouter/pi_runner.py
"""

import os
import time
import json
import random
import requests

from openrouter.ouija_hardware import OuijaHardware
from openrouter.pi_whispercpp_v4 import listen_question_near_realtime

# NEW: import wordbanks from separate file
from openrouter.wordbanks import (
    YES_NO_MAYBE,
    KEYWORDS,
    WORD_BANKS,
)

# =====================================================
# CONFIG
# =====================================================

HARDWARE_ENABLED = True
SERIAL_PORT = "/dev/ttyACM0"   # change if needed on Pi
SERIAL_BAUD = 115200

# OpenRouter
MODEL_NAME = "z-ai/glm-4.5-air:free"
OPENROUTER_COMPLETIONS_URL = "https://openrouter.ai/api/v1/completions"

# Small pause so logs don't smash together
PRE_RESPONSE_PAUSE = 0.25


# =====================================================
# OPENROUTER HELPERS
# =====================================================

def _openrouter_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "OuijaBoard-Pi",
    }


def openrouter_completion(prompt: str, max_tokens: int = 8, temperature: float = 0.2, timeout_s: int = 30) -> str:
    """
    Calls OpenRouter Completions API (text-in, text-out). Returns raw text.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return ""

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    try:
        r = requests.post(
            OPENROUTER_COMPLETIONS_URL,
            headers=_openrouter_headers(api_key),
            data=json.dumps(payload),
            timeout=timeout_s,
        )
        if r.status_code != 200:
            return ""
        return (r.json().get("choices", [{}])[0].get("text") or "").strip()
    except Exception:
        return ""


# =====================================================
# MODE CLASSIFICATION
# =====================================================

def classify_mode(question: str) -> str:
    """
    Return:
      - "YES_NO_MAYBE"
      - "ONE_WORD"
    """
    q = (question or "").lower().strip()

    # cheap heuristics first (fast, predictable)
    if any(q.startswith(x) for x in ("what should", "what do", "what is", "who", "where", "when", "how do", "how should")):
        return "ONE_WORD"

    # If it contains any "one-word" category keywords, return ONE_WORD
    # (except if it clearly looks like a yes/no question)
    looks_yesno = q.endswith("?") or q.startswith(("is ", "are ", "am ", "do ", "does ", "did ", "should ", "can ", "could ", "will ", "would ", "was ", "were "))
    if not looks_yesno:
        for cat, kws in KEYWORDS.items():
            if any(w in q for w in kws):
                return "ONE_WORD"

    # if it looks like a yes/no question, keep it yes/no (but answer via LLM)
    if looks_yesno:
        return "YES_NO_MAYBE"

    # If OpenRouter key exists, ask LLM to decide the mode
    prompt = f"""
Classify how a mystical ouija board should answer.

Return ONLY one of these:
YES_NO_MAYBE
ONE_WORD

Question:
{question.strip()}
""".strip()

    out = openrouter_completion(prompt, max_tokens=4, temperature=0.1)
    out_up = (out or "").upper()

    if "ONE_WORD" in out_up:
        return "ONE_WORD"
    if "YES_NO_MAYBE" in out_up:
        return "YES_NO_MAYBE"

    # fallback
    return "YES_NO_MAYBE"


# =====================================================
# YES / NO / MAYBE ANSWER (LLM, not random)
# =====================================================

def answer_yes_no_maybe(question: str) -> str:
    """
    Uses LLM for YES/NO/MAYBE so basic factual questions don't feel broken.
    Falls back to random if no API key / error.
    """
    prompt = f"""
You are an oracle controlling a physical ouija board.

Answer the user's question with EXACTLY ONE token:
YES
NO
MAYBE

Rules:
- Use common knowledge when applicable.
- If the question is ambiguous, subjective, or not answerable with certainty, return MAYBE.
- Do not add punctuation or extra words.

Question: {question.strip()}
""".strip()

    out = openrouter_completion(prompt, max_tokens=2, temperature=0.1)
    out_up = (out or "").strip().upper()

    # strict normalize
    if out_up == "YES":
        return "YES"
    if out_up == "NO":
        return "NO"
    if out_up == "MAYBE":
        return "MAYBE"

    # sometimes models return extra whitespace or newline; try first token
    tok = out_up.split()[0] if out_up else ""
    if tok in ("YES", "NO", "MAYBE"):
        return tok

    return random.choice(YES_NO_MAYBE)


# =====================================================
# WORD ORACLE
# =====================================================

def pick_one_word(question: str) -> str:
    q = (question or "").lower()

    # Pick a category by keyword match (first match wins, ordered by KEYWORDS insertion order)
    matched_category = None
    for cat, kws in KEYWORDS.items():
        if any(w in q for w in kws):
            matched_category = cat
            break

    # Fallback categories if nothing matches
    if not matched_category:
        # "do / now / today" style prompts -> action-ish
        if any(w in q for w in ("do", "today", "tonight", "now", "this week", "tomorrow")):
            matched_category = "actions"
        else:
            matched_category = "generic"

    bank = WORD_BANKS.get(matched_category) or WORD_BANKS["generic"]
    return random.choice(bank)


# =====================================================
# MAIN
# =====================================================

def main():
    print("[OUJIA] Press ENTER to listen.")
    print("       Type 'q' + ENTER to quit.\n")

    # ---------- Hardware ----------
    hw = None
    if HARDWARE_ENABLED:
        try:
            print("[HW] Connecting...")
            hw = OuijaHardware(port=SERIAL_PORT, baud=SERIAL_BAUD)
            hw.connect()
            hw.rest()
            print("[HW] Ready")
        except Exception as e:
            print(f"[HW] FAILED: {e}")
            hw = None

    try:
        while True:
            cmd = input("\n[READY] Press ENTER to listen (or 'q' to quit): ").strip().lower()
            if cmd == "q":
                break

            print("[MIC] Listening...")

            # NOTE: these params are chosen to be more stable on USB mics
            # - chunk_s=2.0 makes RMS less jittery
            # - silence_chunks_to_stop=1 means ~2 seconds of silence stops capture
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

            mode = classify_mode(text)
            print(f"[MODE] {mode}")

            if mode == "YES_NO_MAYBE":
                ans = answer_yes_no_maybe(text)
                print(f"[RESPONSE] {ans}")

                if hw:
                    try:
                        if ans in ("YES", "NO"):
                            hw.move_to(ans)
                        else:
                            hw.spell_text("MAYBE")
                        hw.rest()
                    except Exception as e:
                        print(f"[HW ERROR] {e}")

            else:
                word = pick_one_word(text)
                print(f"[RESPONSE] {word}")

                if hw:
                    try:
                        hw.spell_text(word)
                        hw.rest()
                    except Exception as e:
                        print(f"[HW ERROR] {e}")

    except KeyboardInterrupt:
        print("\n[EXIT] Stopped by user")
    finally:
        if hw:
            hw.close()


if __name__ == "__main__":
    main()

