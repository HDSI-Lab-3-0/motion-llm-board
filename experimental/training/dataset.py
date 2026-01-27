import json
import random
from pathlib import Path

OUT = Path("data/ouija_train.jsonl")
N = 900  # set anywhere 500–1500

# Keep the label-space tight at first.
LABELS = ["YES", "NO", "MAYBE"]

# Templates that look like real user questions
TEMPLATES = [
    "Should I {verb} {thing}?",
    "Will {subject} happen {time}?",
    "Is {person} thinking about me?",
    "Am I going to {outcome}?",
    "Will I {verb} {thing} {time}?",
    "Is {time} going to be {adj}?",
    "Should I take the {option}?",
    "Is it a good idea to {verb} {thing}?",
    "Will my {thing} get better?",
    "Is {person} going to message me?",
    "Will I regret {thing}?",
]

VERBS = ["go out", "study", "rest", "text them", "apply", "travel", "switch majors", "start early", "wait", "take a risk"]
THINGS = ["tonight", "this weekend", "tomorrow", "today", "next week", "soon", "in January", "after class", "before bed"]
SUBJECTS = ["something good", "something unexpected", "a change", "good news", "a surprise", "a setback", "an opportunity"]
TIMES = ["tonight", "tomorrow", "this week", "next week", "soon", "in the next few days"]
ADJS = ["stressful", "peaceful", "exciting", "chaotic", "lucky", "weird", "quiet"]
PERSONS = ["someone", "they", "my friend", "my crush", "my parents", "my professor"]
OPTIONS = ["safe route", "bold choice", "new path", "offer", "trip", "job"]

# Simple heuristic labeling (you can refine later)
def choose_label(question: str) -> str:
    q = question.lower()
    if "stressful" in q or "setback" in q or "regret" in q:
        return random.choices(["NO", "MAYBE"], weights=[0.6, 0.4])[0]
    if "good news" in q or "opportunity" in q or "exciting" in q:
        return random.choices(["YES", "MAYBE"], weights=[0.6, 0.4])[0]
    # default mixed
    return random.choices(LABELS, weights=[0.4, 0.3, 0.3])[0]

def render():
    t = random.choice(TEMPLATES)
    question = t.format(
        verb=random.choice(VERBS),
        thing=random.choice(THINGS),
        subject=random.choice(SUBJECTS),
        time=random.choice(TIMES),
        adj=random.choice(ADJS),
        person=random.choice(PERSONS),
        option=random.choice(OPTIONS),
        outcome=random.choice(["pass my exam", "be okay", "get good news", "fail", "meet someone", "feel better"]),
    )
    # normalize spacing/punctuation
    question = question.replace("??", "?").replace("  ", " ").strip()
    return question

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for _ in range(N):
    	q = render()
    	rows.append({"input": q, "output": choose_label(q)})

    with OUT.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Wrote {len(rows)} examples to {OUT}")

if __name__ == "__main__":
    main()

