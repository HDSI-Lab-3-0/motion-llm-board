"""Specific question routes and explainable word-bank selection."""
import random
import re

from .wordbanks_spooky3 import KEYWORDS, WORD_BANKS

_previous = {}


def normalize(question):
    text = question.lower().replace("’", "'")
    text = re.sub(r"\bur\b", "your", text)
    text = re.sub(r"\bu\b", "you", text)
    return re.sub(r"\s+", " ", text).strip()


def matches(text, phrase):
    return re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text) is not None


def varied_choice(key, values):
    options = [v for v in values if v != _previous.get(key)] or list(values)
    answer = random.choice(options)
    _previous[key] = answer
    return answer


def offered_choices(question):
    text = normalize(question).strip(" ?.! ")
    # Restrict extraction to explicit preference/selection frames or short lists.
    frame = re.match(r"^(?:do you (?:like|prefer|want)|would you (?:like|prefer|choose)|(?:which|what) (?:do|would) you (?:like|prefer|choose)|(?:choose|pick)(?: between)?)\s+(.+)$", text)
    body = frame.group(1) if frame else text
    if not frame and re.match(r"^(?:is|are|do|does|can|have|will|should|would)\b", text):
        return []
    if not re.search(r"\s+or\s+", body):
        return []
    parts = re.split(r",\s*(?:or\s+)?|\s+or\s+", body)
    parts = [re.sub(r"^(?:a|an|the)\s+", "", p.strip()) for p in parts if p.strip()]
    if not 2 <= len(parts) <= 5:
        return []
    if any(not re.fullmatch(r"[a-z0-9]+(?: [a-z0-9]+){0,2}", p) for p in parts):
        return []
    if any(re.search(r"\b(?:is|are|do|does|have|any|not|nobody|you|i|we)\b", p) for p in parts):
        return []
    return [p.upper() for p in parts]


def direct_response(question):
    text = normalize(question)
    if re.search(r"\b(?:your name|who (?:are you|is this)|who am i talking to|identify yourself)\b", text):
        return varied_choice("names", WORD_BANKS["names"]), "Word bank · Names"
    choices = offered_choices(text)
    if choices:
        return varied_choice(tuple(choices), choices), "Random choice · " + " / ".join(choices)
    return None


def select_bank(question):
    text = normalize(question)
    scores = {category: sum(max(1, len(kw.split())) for kw in words if matches(text, kw))
              for category, words in KEYWORDS.items()}
    # Explicit tie priority; names and specific topics precede broad spirit/advice.
    priority = ["names", "food", "tech", "numbers", "goodbye", "dreams", "afterlife",
                "relationships", "future", "time", "places", "warning", "presence", "spirit", "advice"]
    category = max(priority, key=lambda cat: scores.get(cat, 0))
    return category if scores.get(category, 0) else "generic"
