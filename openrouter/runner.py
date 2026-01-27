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

FOOD_WORDS = [
    "EGGS", "RAMEN", "PASTA", "RICE", "SOUP",
    "SALAD", "SUSHI", "TOAST", "PANCAKES"
]
ACTION_WORDS = [
    "SLEEP", "REST", "WALK", "TEXT",
    "STUDY", "BREATHE", "CALL"
]
GENERIC_WORDS = [
    "WAIT", "TRUST", "GO", "STAY",
    "LISTEN", "RELAX", "FOCUS"
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

    if any(w in q for w in ["eat", "food", "hungry", "dinner", "lunch"]):
        return random.choice(FOOD_WORDS)

    if any(w in q for w in ["do", "right now", "today", "tonight"]):
        return random.choice(ACTION_WORDS)

    return random.choice(GENERIC_WORDS)

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

    # Start background listening only for this one question
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

                # Update live (optional)
                if text and text.lower() != last_text.lower():
                    last_text = text

                if phrase_complete:
                    question = text.strip()
                    break
            else:
                time.sleep(0.05)

    finally:
        # IMPORTANT: stop the background thread for this question
        stop_listening(wait_for_stop=False)

    return question

# =====================================================
# MAIN
# =====================================================

def main():
    print("[OUJIA] Press ENTER to start listening for ONE question.")
    print("       Type 'q' + ENTER to quit.")
    print()

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
                ans = random.choice(YES_NO_MAYBE)
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

