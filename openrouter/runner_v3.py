import os
import time
import json
import queue
import random
import requests
import numpy as np
import speech_recognition as sr
import whisper
from datetime import datetime, timedelta, timezone

from ouija_hardware import OuijaHardware

# =====================================================
# CONFIG
# =====================================================

WHISPER_MODEL = "tiny"
ENERGY_THRESHOLD = 1000
RECORD_TIMEOUT = 1.5
PHRASE_TIMEOUT = 1.8
PRE_RESPONSE_PAUSE = 0.25

HARDWARE_ENABLED = True
SERIAL_PORT = "/dev/cu.usbmodem1101"
SERIAL_BAUD = 115200

MODEL_NAME = "z-ai/glm-4.5-air:free"
OPENROUTER_COMPLETIONS_URL = "https://openrouter.ai/api/v1/completions"

# =====================================================
# WORD POOLS (BIG + VARIED)
# =====================================================

FOOD_WORDS = [
    "RAMEN", "PASTA", "RICE", "SOUP", "SALAD", "SUSHI", "TOAST", "PANCAKES",
    "BURRITO", "TACOS", "PIZZA", "CURRY", "NOODLES", "SANDWICH", "DUMPLINGS",
    "FRIED RICE", "PHO", "BIBIMBAP", "KATSU", "UDON", "POKE", "SHAWARMA",
    "FALAFEL", "QUESADILLA", "RISOTTO", "STIR FRY", "BOWL",
    "FRUIT", "YOGURT", "GRANOLA", "COOKIES", "CHOCOLATE", "ICE CREAM",
    "BROWNIE", "MUFFIN", "BAGEL", "CHIPS", "POPCORN",
    "WATER", "TEA", "COFFEE", "SMOOTHIE"
]

ACTION_WORDS = [
    "SLEEP", "REST", "WALK", "TEXT", "STUDY", "BREATHE", "CALL",
    "WRITE", "CLEAN", "STRETCH", "SHOWER", "COOK", "PLAN", "JOURNAL",
    "READ", "DANCE", "DRIVE", "CREATE", "APOLOGIZE", "FORGIVE",
    "DECLUTTER", "GO OUT", "STAY IN", "LOG OFF", "RESET"
]

GENERIC_WORDS = [
    "WAIT", "TRUST", "GO", "STAY", "LISTEN", "RELAX", "FOCUS",
    "SHIFT", "GROW", "HEAL", "LEARN", "ASK", "ACCEPT", "RELEASE",
    "RETURN", "BEGIN", "PAUSE", "MOVE", "CHOOSE", "PROTECT",
    "DETACH", "COMMIT", "OBSERVE", "SIMPLIFY", "BELIEVE"
]

MOOD_WORDS = [
    "CALM", "BOLD", "SOFT", "BRAVE", "TIRED", "HOPEFUL", "CURIOUS",
    "CONFIDENT", "ANXIOUS", "STEADY", "PLAYFUL", "SERIOUS"
]

RELATIONSHIP_WORDS = [
    "HONESTY", "BOUNDARIES", "FLIRT", "APOLOGY", "CLOSURE", "PATIENCE",
    "LOYALTY", "SPACE", "COMPROMISE", "CLARITY", "KINDNESS"
]

SCHOOL_WORK_WORDS = [
    "START", "REVISE", "SUBMIT", "OUTLINE", "PRACTICE", "EMAIL",
    "MEETING", "DEADLINE", "PRIORITY", "CONSISTENCY", "DISCIPLINE"
]

MONEY_WORDS = [
    "SAVE", "SPEND", "BUDGET", "INVEST", "NEGOTIATE", "WAIT",
    "CONFIRM", "CANCEL", "CHARGE", "REFUND"
]

TRAVEL_WORDS = [
    "GO", "BOOK", "PACK", "WANDER", "EXPLORE", "BEACH", "MOUNTAINS",
    "CITY", "ADVENTURE", "MAP"
]

YES_NO_MAYBE = ["YES", "NO", "MAYBE"]

# =====================================================
# MODE CLASSIFICATION
# =====================================================

def classify_mode(question: str) -> str:
    q = question.lower().strip()

    if q.startswith(("what should", "what do", "what is", "who")):
        return "ONE_WORD"

    if any(w in q for w in ["eat", "food", "hungry", "dinner", "lunch"]):
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
        "X-Title": "OuijaBoard-Hybrid",
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

    if any(w in q for w in ["eat", "food", "hungry", "dinner", "lunch", "snack", "drink"]):
        return random.choice(FOOD_WORDS)

    if any(w in q for w in ["crush", "love", "date", "boyfriend", "girlfriend", "relationship", "miss", "breakup"]):
        return random.choice(RELATIONSHIP_WORDS)

    if any(w in q for w in ["study", "exam", "quiz", "assignment", "homework", "class", "work", "job", "internship", "interview"]):
        return random.choice(SCHOOL_WORK_WORDS + ACTION_WORDS)

    if any(w in q for w in ["money", "pay", "refund", "tax", "rent", "bill", "budget", "buy"]):
        return random.choice(MONEY_WORDS)

    if any(w in q for w in ["travel", "trip", "flight", "hotel", "vacation", "beach"]):
        return random.choice(TRAVEL_WORDS)

    if any(w in q for w in ["do", "right now", "today", "tonight"]):
        return random.choice(ACTION_WORDS + GENERIC_WORDS)

    return random.choice(GENERIC_WORDS + MOOD_WORDS)

# =====================================================
# RECORD ONE UTTERANCE
# =====================================================

def record_one_question(recognizer, mic, model) -> str:
    audio_q = queue.Queue()
    phrase_time = None
    phrase_audio = b""

    def callback(_, audio):
        audio_q.put(audio.get_raw_data())

    stop_listening = recognizer.listen_in_background(
        mic, callback, phrase_time_limit=RECORD_TIMEOUT
    )

    last_text = ""
    question = ""

    try:
        while True:
            now = datetime.now(timezone.utc)

            if not audio_q.empty():
                phrase_complete = False

                if phrase_time and now - phrase_time > timedelta(seconds=PHRASE_TIMEOUT):
                    phrase_complete = True

                phrase_time = now

                data = b"".join(list(audio_q.queue))
                with audio_q.mutex:
                    audio_q.queue.clear()

                phrase_audio += data

                audio_np = (
                    np.frombuffer(phrase_audio, np.int16)
                    .astype(np.float32) / 32768
                )

                text = model.transcribe(audio_np, fp16=False, language="en")["text"].strip()

                if text and text.lower() != last_text.lower():
                    last_text = text

                if phrase_complete:
                    question = text.strip()
                    break
            else:
                time.sleep(0.05)
    finally:
        stop_listening(wait_for_stop=False)

    return question

# =====================================================
# MAIN
# =====================================================

def main():
    print("[OUJIA] Press ENTER to start listening for ONE question.")
    print("       Type 'q' + ENTER to quit.")

    hw = None
    if HARDWARE_ENABLED:
        try:
            hw = OuijaHardware(port=SERIAL_PORT, baud=SERIAL_BAUD)
            hw.connect()
            hw.rest()
        except Exception as e:
            print(f"[HW] Failed: {e}")
            hw = None

    recognizer = sr.Recognizer()
    recognizer.energy_threshold = ENERGY_THRESHOLD
    recognizer.dynamic_energy_threshold = False

    model = whisper.load_model(WHISPER_MODEL)

    mic = sr.Microphone(sample_rate=16000)
    with mic:
        recognizer.adjust_for_ambient_noise(mic)

    try:
        while True:
            cmd = input("\n[READY] Press ENTER to listen (or 'q'): ").strip().lower()
            if cmd == "q":
                break

            print("[MIC] Listening...")
            text = record_one_question(recognizer, mic, model)

            if not text:
                print("[NO SPEECH]")
                continue

            print(f"[QUESTION] {text}")
            time.sleep(PRE_RESPONSE_PAUSE)

            mode = classify_mode(text)
            print(f"[MODE] {mode}")

            if mode == "YES_NO_MAYBE":
                ans = random.choice(YES_NO_MAYBE)
                print(f"[RESPONSE] {ans}")
                if hw:
                    hw.move_to(ans) if ans in ("YES", "NO") else hw.spell_text("MAYBE")
                    hw.rest()
            else:
                word = pick_one_word(text)
                print(f"[RESPONSE] {word}")
                if hw:
                    hw.spell_text(word)
                    hw.rest()

    finally:
        if hw:
            hw.close()

if __name__ == "__main__":
    main()

