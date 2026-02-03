import os
import time
import json
import random
import requests

from ouija_hardware import OuijaHardware
from openrouter.pi_whispercpp import listen_question_near_realtime

# =====================================================
# CONFIG
# =====================================================

HARDWARE_ENABLED = True
SERIAL_PORT = "/dev/ttyACM0"   # <-- CHANGE if needed on Pi
SERIAL_BAUD = 115200

MODEL_NAME = "z-ai/glm-4.5-air:free"
OPENROUTER_COMPLETIONS_URL = "https://openrouter.ai/api/v1/completions"

PRE_RESPONSE_PAUSE = 0.25

# =====================================================
# WORD POOLS
# =====================================================

FOOD_WORDS = [
    "RAMEN", "PASTA", "RICE", "SOUP", "SALAD", "SUSHI", "TOAST",
    "BURRITO", "TACOS", "PIZZA", "CURRY", "NOODLES", "SANDWICH",
    "DUMPLINGS", "PHO", "BIBIMBAP", "UDON", "POKE",
    "FRUIT", "YOGURT", "COFFEE", "TEA", "SMOOTHIE"
]

ACTION_WORDS = [
    "SLEEP", "REST", "WALK", "TEXT", "STUDY", "BREATHE",
    "WRITE", "CLEAN", "STRETCH", "SHOWER", "PLAN",
    "READ", "DANCE", "CREATE", "RESET"
]

GENERIC_WORDS = [
    "WAIT", "TRUST", "GO", "STAY", "LISTEN", "RELAX",
    "FOCUS", "GROW", "HEAL", "PAUSE", "MOVE", "CHOOSE"
]

RELATIONSHIP_WORDS = [
    "HONESTY", "BOUNDARIES", "APOLOGY", "CLOSURE",
    "PATIENCE", "LOYALTY", "SPACE", "CLARITY"
]

SCHOOL_WORK_WORDS = [
    "START", "REVISE", "SUBMIT", "OUTLINE",
    "PRACTICE", "EMAIL", "DEADLINE"
]

YES_NO_MAYBE = ["YES", "NO", "MAYBE"]

# =====================================================
# MODE CLASSIFICATION
# =====================================================

def classify_mode(question: str) -> str:
    q = question.lower().strip()

    if q.startswith(("what should", "what do", "what is", "who", "where", "when")):
        return "ONE_WORD"

    if any(w in q for w in [
        "eat", "food", "hungry", "dinner", "lunch",
        "breakfast", "snack", "drink", "cook"
    ]):
        return "ONE_WORD"

    if q.endswith("?"):
        return "YES_NO_MAYBE"

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return "YES_NO_MAYBE"

    prompt = f"""
Classify how a mystical ouija board should answer.

Return ONLY one of these:
YES_NO_MAYBE
ONE_WORD

Question:
{question.strip()}
""".strip()

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "max_tokens": 4,
        "temperature": 0.2,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "OuijaBoard-Pi",
    }

    try:
        r = requests.post(
            OPENROUTER_COMPLETIONS_URL,
            headers=headers,
            data=json.dumps(payload),
            timeout=30,
        )
        if r.status_code == 200:
            text = (r.json()["choices"][0]["text"] or "").upper()
            if "ONE_WORD" in text:
                return "ONE_WORD"
    except:
        pass

    return "YES_NO_MAYBE"

# =====================================================
# WORD ORACLE
# =====================================================

def pick_one_word(question: str) -> str:
    q = question.lower()

    if any(w in q for w in ["eat", "food", "hungry", "dinner", "lunch", "breakfast"]):
        return random.choice(FOOD_WORDS)

    if any(w in q for w in ["love", "date", "crush", "relationship", "text"]):
        return random.choice(RELATIONSHIP_WORDS)

    if any(w in q for w in ["study", "exam", "class", "work", "job", "assignment"]):
        return random.choice(SCHOOL_WORK_WORDS + ACTION_WORDS)

    if any(w in q for w in ["do", "today", "tonight", "now"]):
        return random.choice(ACTION_WORDS + GENERIC_WORDS)

    return random.choice(GENERIC_WORDS)

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

            try:
                text = listen_question_near_realtime(
                    max_seconds=12.0,
                    chunk_s=1.6,
                    silence_chunks_to_stop=2,
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
                ans = random.choice(YES_NO_MAYBE)
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

