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

# NEW: wordbanks live in separate file now
from openrouter.wordbanks import (
    YES_NO_MAYBE,
    FOOD_WORDS,
    DRINK_WORDS,
    ACTION_WORDS,
    GENERIC_WORDS,
    RELATIONSHIP_WORDS,
    COMMUNICATION_WORDS,
    FAMILY_WORDS,
    BOUNDARY_WORDS,
    SCHOOL_WORK_WORDS,
    CAREER_WORDS,
    TECH_WORDS,
    ANXIETY_WORDS,
    CONFIDENCE_WORDS,
    REFLECTION_WORDS,
    LUCK_WORDS,
    HEALTH_WORDS,
    FITNESS_WORDS,
    MONEY_WORDS,
    TRAVEL_WORDS,
    CREATIVITY_WORDS,
    SLEEP_WORDS,
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
# MODE CLASSIFICATION (FIXED ROUTING)
# =====================================================

def classify_mode(question: str) -> str:
    """
    Return:
      - "YES_NO_MAYBE"
      - "ONE_WORD"
    """
    q = (question or "").lower().strip()

    # 1) "what should..." style prompts should ALWAYS be ONE_WORD
    if any(q.startswith(x) for x in (
        "what should", "what do", "how should", "which", "pick", "choose"
    )):
        return "ONE_WORD"

    # 2) Keyword-driven ONE_WORD triggers
    if any(w in q for w in ("eat", "hungry", "dinner", "lunch", "breakfast", "snack", "cook", "restaurant", "meal")):
        return "ONE_WORD"
    if any(w in q for w in ("drink", "thirsty", "coffee", "tea", "matcha", "boba", "smoothie", "water")):
        return "ONE_WORD"
    if any(w in q for w in ("study", "exam", "class", "assignment", "homework", "project", "deadline")):
        return "ONE_WORD"
    if any(w in q for w in ("relationship", "boyfriend", "girlfriend", "partner", "crush", "date", "text", "apologize")):
        return "ONE_WORD"
    if any(w in q for w in ("anxious", "overthink", "stressed", "panic", "worry", "cry", "sad")):
        return "ONE_WORD"
    if any(w in q for w in ("job", "intern", "internship", "resume", "interview", "career", "apply")):
        return "ONE_WORD"

    # 3) YES/NO only if it STARTS like a yes/no question
    # (do NOT use q.endswith("?") because Whisper transcripts are unreliable)
    YESNO_STARTERS = (
        "is ", "are ", "am ",
        "do ", "does ", "did ",
        "should ", "can ", "could ",
        "will ", "would ",
        "was ", "were "
    )
    if q.startswith(YESNO_STARTERS):
        return "YES_NO_MAYBE"

    # 4) If OpenRouter key exists, ask LLM to decide the mode
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

    if out_up == "YES":
        return "YES"
    if out_up == "NO":
        return "NO"
    if out_up == "MAYBE":
        return "MAYBE"

    tok = out_up.split()[0] if out_up else ""
    if tok in ("YES", "NO", "MAYBE"):
        return tok

    return random.choice(YES_NO_MAYBE)


# =====================================================
# WORD ORACLE (FIXED COOK/DRINK BEHAVIOR)
# =====================================================

def pick_one_word(question: str) -> str:
    q = (question or "").lower()

    # HARD RULES FIRST: prevents "cook" returning drinks, etc.
    if "cook" in q:
        return random.choice(FOOD_WORDS)
    if "drink" in q or "thirst" in q:
        return random.choice(DRINK_WORDS)

    # Food / hunger
    if any(w in q for w in ["eat", "hungry", "dinner", "lunch", "breakfast", "snack", "food", "meal", "restaurant"]):
        return random.choice(FOOD_WORDS)

    # Relationships / communication
    if any(w in q for w in ["apologize", "sorry", "text", "message", "talk", "communicate", "misunderstand"]):
        return random.choice(COMMUNICATION_WORDS + RELATIONSHIP_WORDS)

    if any(w in q for w in ["love", "date", "crush", "relationship", "boyfriend", "girlfriend", "partner", "breakup"]):
        return random.choice(RELATIONSHIP_WORDS)

    # School / work
    if any(w in q for w in ["study", "exam", "class", "assignment", "homework", "project", "deadline"]):
        return random.choice(SCHOOL_WORK_WORDS + ACTION_WORDS)

    # Career
    if any(w in q for w in ["career", "major", "intern", "internship", "resume", "interview", "apply", "linkedin"]):
        return random.choice(CAREER_WORDS + ACTION_WORDS)

    # Anxiety / stress
    if any(w in q for w in ["anxious", "anxiety", "overthink", "stressed", "stress", "panic", "worry", "cry", "sad"]):
        return random.choice(ANXIETY_WORDS)

    # Confidence / self-worth
    if any(w in q for w in ["confidence", "confident", "brave", "courage", "insecure", "imposter"]):
        return random.choice(CONFIDENCE_WORDS)

    # Health / fitness
    if any(w in q for w in ["hurt", "pain", "injury", "health", "sick", "recover"]):
        return random.choice(HEALTH_WORDS)
    if any(w in q for w in ["workout", "gym", "yoga", "pilates", "run", "hike", "surf", "lift"]):
        return random.choice(FITNESS_WORDS)

    # Money
    if any(w in q for w in ["money", "budget", "save", "rent", "pay", "debt", "broke"]):
        return random.choice(MONEY_WORDS)

    # Travel
    if any(w in q for w in ["travel", "trip", "vacation", "flight", "hotel", "beach"]):
        return random.choice(TRAVEL_WORDS)

    # Creativity
    if any(w in q for w in ["creative", "draw", "art", "music", "guitar", "piano", "write", "paint", "design"]):
        return random.choice(CREATIVITY_WORDS)

    # Family
    if any(w in q for w in ["mom", "dad", "parents", "family", "cousin", "home"]):
        return random.choice(FAMILY_WORDS + BOUNDARY_WORDS)

    # Tech
    if any(w in q for w in ["python", "error", "bug", "debug", "install", "module", "import", "raspberry", "arduino", "serial", "github", "git"]):
        return random.choice(TECH_WORDS)

    # Sleep
    if any(w in q for w in ["sleep", "tired", "insomnia", "nap", "bed", "dream"]):
        return random.choice(SLEEP_WORDS)

    # “What should I do…” even if Whisper trimmed it down
    if any(w in q for w in ["do", "today", "tonight", "now", "this week", "tomorrow"]):
        return random.choice(ACTION_WORDS + GENERIC_WORDS)

    # Fallback
    return random.choice(GENERIC_WORDS)


# =====================================================
# MAIN (UNCHANGED HARDWARE + WHISPER)
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

