"""Recognize explicit single-word spelling without changing question routing."""
import re


def extract_spell_target(question):
    text = question.replace('\u2019', "'")
    text = re.sub(r'\b(can|could|would|will)\s+u\b', r'\1 you', text, flags=re.I)
    clauses = [c.strip() for c in re.split(r'[!?;.\n]+', text) if c.strip()]
    # Do not extract a positive instruction from a conflicting/negated utterance.
    if any(re.search(r"\b(?:not|don't|never)\b.*\bspell\b", c, re.I) for c in clauses):
        return None
    targets = []
    for clause in clauses:
        match = re.fullmatch(
            r'(?:please\s+)?(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?)?'
            r'spell\s+(?:(?:out|the\s+word)\s+)?'
            r'(?:"([A-Za-z]{1,19})"|\'([A-Za-z]{1,19})\'|([A-Za-z]{1,19}))'
            r'(?:,?\s+please)?', clause, re.I)
        if match:
            target = next(g for g in match.groups() if g).upper()
            if target not in {'WORD', 'WORDS', 'SOMETHING', 'ANYTHING', 'IT', 'THAT', 'THIS'}:
                targets.append(target)
    return targets[0] if len(set(targets)) == 1 else None
