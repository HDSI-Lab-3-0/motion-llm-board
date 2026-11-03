"""Deterministic policy for unknowable personal facts and fictional presence."""
import re
from .wordbanks_spooky3 import WORD_BANKS


def personal_or_presence_response(question):
    text = question.lower().replace('\u2019', "'")
    # Personal factual questions outrank presence in mixed utterances.
    personal = (
        r'\bmy\b', r'\bour\s+(?:age|name|address|birthday|future|family|secret)\b',
        r'\bhow old\b.*\b(?:i|we|am|are)\b',
        r'\b(?:who|where|when)\s+(?:am|was|were|are)\s+(?:i|we)\b',
        r'\b(?:will|would|did|do|have|had|am|was|can|could|should)\s+i\b',
        r'\bdo you (?:know|remember|recognize)\b.*\b(?:me|us|i|we)\b',
        r'\b(?:does|did|will)\b.*\b(?:love|like|marry|hate)\s+me\b',
    )
    # Advice asks for a suggestion, rather than a claim about hidden personal facts.
    advice = re.search(r'\b(?:(?:what|where)(?:\s+\w+)?\s+should i\b|what do i do\b)', text)
    if any(re.search(pattern, text) for pattern in personal) and not advice:
        return next(word for word in WORD_BANKS['generic'] if word == 'WAIT')
    presence = r'\b(?:are you here|is anyone here|is someone here|is somebody here|are the spirits here|can you hear (?:me|us)|do you hear (?:me|us))\b'
    if re.search(presence, text):
        return 'YES'
    return None

