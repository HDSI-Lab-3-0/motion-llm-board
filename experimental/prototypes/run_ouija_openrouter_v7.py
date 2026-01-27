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

# =====================================================
# FINAL HYBRID + MORE RELIABLE TRANSCRIPTION (DRY RUN)
# =====================================================

# ---- Whisper / mic tuning ----
WHISPER_MODEL = "tiny"        # fast; switch to "base" for better accuracy
ENERGY_THRESHOLD = 1000
RECORD_TIMEOUT = 1.5          # longer chunk capture
PHRASE_TIMEOUT = 1.8          # longer silence to finalize phrases
FORCE_LANGUAGE = "en"         # prevent random language switching

# ---- Snappy vibe ----
PRE_RESPONSE_PAUSE = 0.25

# ---- Optional OpenRouter fallback (only for ambiguous mode) ----
MODEL_NAME = "z-ai/glm-4.5-air:free"
OPENROUTER_COMPLETIONS_URL = "https://openrouter.ai/api/v1/completions"

# ---- Buffering / stitching ----
BUFFER_MAX_SECONDS = 2.8

# =====================================================
# WORD POOLS (CONTROLLED MAGIC)
# =====================================================

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
# FRAGMENT STITCHING HELPERS
# =====================================================

def looks_like_fragment(t: str) -> bool:
    t = t.strip()
    if not t:
        return True

    # Very short and not a question
    if len(t.split()) <= 2 and not t.endswith("?"):
        return True

    # Cut-off endings
    if t.endswith(("-", "…", "...")):
        return True

    # Common partial starters
    low = t.lower().strip("?!. ")
    if low in {"what", "what should", "what should i", "will i", "should i"}:
        return True

    return False


def should_emit(t: str) -> bool:
    t = t.strip()
    if not t:
        return False
    # Emit if it looks like a full question, or enough words
    if t.endswith("?"):
        return True
    return len(t.split()) >= 4


# =====================================================
# OPTIONAL LLM MODE FALLBACK (DETERMINISTIC FIRST)
# =====================================================

def classify_mode(question: str) -> str:
    """
    Returns ONLY:
      - YES_NO_MAYBE
      - ONE_WORD

    Deterministic rules first (most accurate + fastest),
    then OpenRouter fallback only if needed.
    """
    q = question.lower().strip()

    # ---- HARD RULES (ALWAYS CORRECT FOR YOUR USE CASE) ----
    if q.startswith(("what should", "what do", "what is", "who")):
        return "ONE_WORD"

    if any(w in q for w in ["eat", "food", "hungry", "dinner", "lunch"]):
        return "ONE_WORD"

    if q.endswith("?"):
        return "YES_NO_MAYBE"

    # ---- LLM FALLBACK (RARE) ----
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
            txt = (r.json()["choices"][0]["text"] or "").upper()
            if "ONE_WORD" in txt:
                return "ONE_WORD"
    except Exception:
        pass

    return "YES_NO_MAYBE"


# =====================================================
# PYTHON WORD ORACLE (RELIABLE)
# =====================================================

def pick_one_word(question: str) -> str:
    q = question.lower()

    if any(w in q for w in ["eat", "food", "hungry", "dinner", "lunch"]):
        return random.choice(FOOD_WORDS)

    if any(w in q for w in ["do", "right now", "today", "tonight"]):
        return random.choice(ACTION_WORDS)

    return random.choice(GENERIC_WORDS)


# =====================================================
# MAIN LOOP (WHISPER + HYBRID ORACLE)
# =====================================================

def main():
    print("[FINAL HYBRID] Whisper + stitching + rules + Python oracle")
    print("[TARGET] ~3–6 seconds per answer (more reliable)")
    print(f"[WHISPER MODEL] {WHISPER_MODEL} | language={FORCE_LANGUAGE}")

    recognizer = sr.Recognizer()
    recognizer.energy_threshold = ENERGY_THRESHOLD
    recognizer.dynamic_energy_threshold = True  # helps fluctuating mic environments

    audio_q = queue.Queue()
    phrase_time = None
    phrase_audio = b""

    print("[WHISPER] Loading model...")
    model = whisper.load_model(WHISPER_MODEL)
    print("[WHISPER] Ready")

    mic = sr.Microphone(sample_rate=16000)
    with mic:
        recognizer.adjust_for_ambient_noise(mic)

    def callback(_, audio):
        audio_q.put(audio.get_raw_data())

    recognizer.listen_in_background(
        mic, callback, phrase_time_limit=RECORD_TIMEOUT
    )

    print("[MIC] Listening... (Ctrl+C to stop)")

    last_text = ""
    buffer_text = ""
    buffer_start = None

    try:
        while True:
            now = datetime.now(timezone.utc)

            if not audio_q.empty():
                phrase_complete = False

                if phrase_time and now - phrase_time > timedelta(seconds=PHRASE_TIMEOUT):
                    phrase_audio = b""
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

                # Force English to prevent random language switching
                text = model.transcribe(
                    audio_np,
                    fp16=False,
                    language=FORCE_LANGUAGE
                )["text"].strip()

                if phrase_complete and text and text.lower() != last_text.lower():
                    last_text = text

                    now_local = time.time()
                    if buffer_start is None:
                        buffer_start = now_local

                    # Stitch fragments into buffer
                    if looks_like_fragment(text):
                        buffer_text = (buffer_text + " " + text).strip()
                    else:
                        buffer_text = (buffer_text + " " + text).strip()

                    aged_out = (now_local - buffer_start) > BUFFER_MAX_SECONDS

                    if should_emit(buffer_text) or aged_out:
                        final_q = buffer_text.strip()
                        buffer_text = ""
                        buffer_start = None

                        print(f"\n[QUESTION] {final_q}")
                        time.sleep(PRE_RESPONSE_PAUSE)

                        mode = classify_mode(final_q)
                        print(f"[MODE] {mode}")

                        if mode == "YES_NO_MAYBE":
                            ans = random.choice(YES_NO_MAYBE)
                            print(f"[RESPONSE] {ans}")
                            print(f"[DRY RUN] MOVE → {ans}")
                        else:
                            word = pick_one_word(final_q)
                            print(f"[RESPONSE] {word}")
                            print(f"[DRY RUN] SPELL → {' '.join(word)}")

            else:
                time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n[EXIT] Stopped by user")


if __name__ == "__main__":
    main()

