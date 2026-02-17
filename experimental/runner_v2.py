import os
import time
import json
import queue
import random
import requests
import numpy as np
import re
from collections import defaultdict
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

# (Optional) You can keep this for future use — not required for the algorithm below.
MODEL_NAME = "z-ai/glm-4.5-air:free"
OPENROUTER_COMPLETIONS_URL = "https://openrouter.ai/api/v1/completions"

# =====================================================
# ONE-WORD ONLY BANK (ALL CAPS, NO SPACES)
# You can expand these lists freely.
# =====================================================

WORD_BANK = {
    "FOOD": [
        "EGGS","RAMEN","PASTA","RICE","SOUP","SALAD","SUSHI","TOAST","PANCAKES",
        "TACOS","NOODLES","CURRY","PIZZA","DUMPLINGS","BURRITO"
    ],
    "ACTION": [
        "SLEEP","REST","WALK","TEXT","STUDY","BREATHE","CALL","CLEAN","CREATE",
        "PLAN","READ","WRITE","STRETCH","HYDRATE"
    ],
    "RELATIONSHIP": [
        "TEXT","CALL","WAIT","APOLOGIZE","LISTEN","TRUST","FORGIVE","DISTANCE"
    ],
    "SCHOOL": [
        "STUDY","REVIEW","FOCUS","PRACTICE","SUBMIT","PLAN"
    ],
    "MONEY": [
        "SAVE","BUDGET","WAIT","INVEST","SPEND","NEGOTIATE"
    ],
    "HEALTH": [
        "REST","HYDRATE","STRETCH","BREATHE","RECOVER","PAUSE"
    ],
    "TRAVEL": [
        "GO","WAIT","PLAN","BOOK","EXPLORE"
    ],
    "MOOD": [
        "RELAX","TRUST","BREATHE","RESET","PAUSE","GROUNDED"
    ],
    "DEFAULT": [
        "WAIT","TRUST","FOCUS","RELAX","LISTEN","PAUSE","RESET"
    ],
}

CATEGORY_KEYWORDS = {
    "FOOD": ["eat","food","hungry","dinner","lunch","breakfast","snack","restaurant","cook"],
    "ACTION": ["today","tonight","right now","later","this week","now"],
    "RELATIONSHIP": ["text","call","relationship","date","crush","boyfriend","girlfriend","friend","ex","him","her","them"],
    "SCHOOL": ["exam","midterm","final","homework","assignment","class","study","quiz","grade"],
    "MONEY": ["money","pay","rent","job","salary","buy","purchase","debt","credit","budget"],
    "HEALTH": ["sick","hurt","pain","ankle","stress","anxiety","sleep","tired","workout","gym","yoga"],
    "TRAVEL": ["trip","flight","hotel","travel","vacation","cabo","nyc","new york","plane"],
    "MOOD": ["sad","lonely","overwhelmed","burnt","burned","unmotivated","stuck","confused"],
}

YES_NO_MAYBE = ["YES", "NO", "MAYBE"]

# =====================================================
# OPTIONAL: LOAD A BIGGER WORD BANK FROM JSON
# Create data/word_bank.json if you want, example:
# {"FOOD":["RAMEN","SUSHI"],"DEFAULT":["WAIT","TRUST"]}
# =====================================================

def load_word_bank(path="data/word_bank.json"):
    global WORD_BANK
    try:
        with open(path, "r") as f:
            extra = json.load(f)
        for cat, words in extra.items():
            cleaned = []
            for w in (words or []):
                if not w:
                    continue
                w = str(w).strip().upper()
                if " " in w:
                    continue  # enforce one-word only
                if not re.fullmatch(r"[A-Z0-9\-]+", w):
                    continue  # keep it simple for spelling
                cleaned.append(w)
            if cleaned:
                # merge unique
                WORD_BANK[cat] = list(dict.fromkeys(WORD_BANK.get(cat, []) + cleaned))
    except Exception:
        pass

# =====================================================
# TEXT HELPERS
# =====================================================

def normalize_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s

def contains_any(q: str, phrases) -> bool:
    return any(p in q for p in phrases)

# =====================================================
# MODE CLASSIFICATION
# =====================================================

def classify_mode(question: str) -> str:
    q = normalize_text(question)

    # Open-ended → ONE_WORD (still one word only)
    if q.startswith(("what should", "what do", "what is", "who", "where", "when")):
        return "ONE_WORD"

    # Food cues → ONE_WORD
    if contains_any(q, CATEGORY_KEYWORDS["FOOD"]):
        return "ONE_WORD"

    # Binary wording / question mark → YES_NO_MAYBE
    if q.endswith("?") or q.startswith(("should", "is", "are", "will", "can", "do", "did")):
        return "YES_NO_MAYBE"

    return "YES_NO_MAYBE"

# =====================================================
# ONE-WORD ORACLE (KEYWORD-SCORED)
# =====================================================

def pick_one_word(question: str) -> str:
    q = normalize_text(question)
    scores = defaultdict(int)

    for cat, keys in CATEGORY_KEYWORDS.items():
        for k in keys:
            if k in q:
                scores[cat] += 2

    # Pattern boosts
    if "should i" in q:
        scores["ACTION"] += 2
    if contains_any(q, ["text", "call", "date", "crush", "ex"]):
        scores["RELATIONSHIP"] += 3
    if contains_any(q, ["exam", "midterm", "final", "assignment", "homework"]):
        scores["SCHOOL"] += 3
    if contains_any(q, ["sick", "hurt", "pain", "ankle"]):
        scores["HEALTH"] += 3

    best_cat = max(scores.items(), key=lambda x: x[1])[0] if scores else "DEFAULT"
    options = WORD_BANK.get(best_cat, WORD_BANK["DEFAULT"])
    return random.choice(options)

# =====================================================
# YES/NO/MAYBE ORACLE (HEURISTIC SCORING)
# =====================================================

NEGATIVE = ["quit","break up","leave","cancel","skip","give up","drop","stop","ghost"]
RISKY = ["drunk","drive","drug","fight","steal","cheat","gamble","danger","hurt"]
URGENT = ["right now","tonight","today","immediately","asap"]
UNCERTAIN = ["maybe","not sure","idk","confused","unclear","mixed"]
SELFCARE = ["rest","sleep","recover","breathe","pause","break","hydrate","stretch"]
POSITIVE = ["apply","try","start","go","ask","practice","study","workout","clean","submit"]

def pick_yes_no_maybe(question: str) -> str:
    q = normalize_text(question)
    yes_score = 0
    no_score = 0

    # High risk → NO
    if any(w in q for w in RISKY):
        no_score += 5

    # Negative / avoidant verbs → NO-ish
    if any(w in q for w in NEGATIVE):
        no_score += 2

    # Self-care → YES-ish
    if any(w in q for w in SELFCARE):
        yes_score += 3

    # Positive actions → small YES
    if any(w in q for w in POSITIVE):
        yes_score += 1

    # Urgency → less confident
    if any(w in q for w in URGENT):
        no_score += 1  # "don't rush" nudge

    # If user expresses uncertainty → MAYBE
    if any(w in q for w in UNCERTAIN):
        return "MAYBE"

    # Future-telling ("will ...") → often MAYBE unless strongly biased
    if q.startswith("will ") or "will i" in q:
        if abs(yes_score - no_score) < 4:
            return "MAYBE"
        return "YES" if yes_score > no_score else "NO"

    # Close scores → MAYBE
    if abs(yes_score - no_score) <= 1:
        return "MAYBE"

    return "YES" if yes_score > no_score else "NO"

# =====================================================
# RECORD ONE UTTERANCE (PRESS-TO-START)
# =====================================================

def record_one_question(recognizer, mic, model) -> str:
    """
    Records audio only after user presses ENTER, then returns one transcribed question.
    Uses your PHRASE_TIMEOUT silence rule to decide when the question is finished.
    """
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
                    np.frombuffer(phrase_audio, np.int16).astype(np.float32) / 32768
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
    print()

    # Load optional external word bank
    load_word_bank()

    # ---------- Hardware connect ----------
    hw = None
    if HARDWARE_ENABLED:
        try:
            print("[HW] Connecting...")
            hw = OuijaHardware(port=SERIAL_PORT, baud=SERIAL_BAUD)
            hw.connect()
            hw.rest()
            print("[HW] Ready")
        except Exception as e:
            print(f"[HW] FAILED to connect: {e}")
            print("[HW] Continuing in NO-HARDWARE mode.")
            hw = None

    # ---------- Whisper / mic ----------
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = ENERGY_THRESHOLD
    recognizer.dynamic_energy_threshold = False

    print("[WHISPER] Loading model...")
    model = whisper.load_model(WHISPER_MODEL)
    print("[WHISPER] Ready")

    mic = sr.Microphone(sample_rate=16000)
    with mic:
        recognizer.adjust_for_ambient_noise(mic)

    try:
        while True:
            cmd = input("\n[READY] Press ENTER to listen (or 'q' to quit): ").strip().lower()
            if cmd == "q":
                break

            print("[MIC] Listening... speak now")
            text = record_one_question(recognizer, mic, model)

            if not text:
                print("[NO SPEECH] Didn't catch that. Press ENTER to try again.")
                continue

            print(f"\n[QUESTION] {text}")

            time.sleep(PRE_RESPONSE_PAUSE)

            mode = classify_mode(text)
            print(f"[MODE] {mode}")

            if mode == "YES_NO_MAYBE":
                ans = pick_yes_no_maybe(text)   # <-- smarter than random
                print(f"[RESPONSE] {ans}")

                if hw:
                    try:
                        if ans in ("YES", "NO"):
                            hw.move_to(ans)
                        else:
                            hw.spell_text("MAYBE")  # no dedicated MAYBE spot
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

