import json
import random
from pathlib import Path

OUT_PATH = Path("data/manual_additions.jsonl")
N = 1000

ALLOWED = ["YES", "NO", "MAYBE"]

# --- “Manual-style” question patterns (more natural, less templated) ---
YES_PATTERNS = [
    "Should I {action} {time}?",
    "Is it a good idea to {action} {time}?",
    "Will it help if I {action} {time}?",
    "Is {option} the right move {time}?",
    "Would I benefit from {action} {time}?",
    "Should I say yes to {option} {time}?",
    "Is now a good time to {action}?",
    "Should I lean into {option}?",
    "Will I feel better if I {action}?",
    "Should I follow through with {option}?",
]

NO_PATTERNS = [
    "Should I {risky_action} {time}?",
    "Is it smart to {risky_action} {time}?",
    "Will I regret {risky_action} {time}?",
    "Should I ignore the red flags {time}?",
    "Is it worth {risky_action} {time}?",
    "Should I rush into {risky_action} {time}?",
    "Should I spend money I don’t have {time}?",
    "Should I skip {responsibility} {time}?",
    "Is it safe to {risky_action} {time}?",
    "Should I do something impulsive {time}?",
]

MAYBE_PATTERNS = [
    "Will {uncertain_event} {time}?",
    "Is {uncertain_topic} going to work out {time}?",
    "Should I wait before I {action}?",
    "Is it too soon to {action}?",
    "Will I hear back {time}?",
    "Is {person} being honest {time}?",
    "Is this a sign {time}?",
    "Will things improve {time}?",
    "Should I keep my options open {time}?",
    "Is it better to pause and think {time}?",
]

# --- Phrase banks ---
TIMES = ["today", "tonight", "tomorrow", "this week", "soon", "next week", "this month", "in the next few days", ""]
ACTIONS = [
    "go out", "stay in", "study", "rest", "text them", "call my friend", "apply for that role",
    "start a new routine", "try again", "ask for help", "be honest", "set a boundary",
    "take a break", "focus on myself", "go for a walk", "journal", "sleep early",
    "practice guitar", "finish my assignment", "clean my room", "plan my week",
    "say what I really feel", "stop overthinking", "give it one more try", "be patient",
    "book that appointment", "reach out first", "follow up", "commit to it",
]
OPTIONS = [
    "that plan", "a new opportunity", "a fresh start", "the safer choice", "the bold choice",
    "a change of direction", "a different approach", "something new", "the next step",
    "a calmer path", "a risk that scares me", "the thing I keep avoiding",
]
RISKY_ACTIONS = [
    "text them again even though they haven’t replied",
    "quit without a plan",
    "stay up all night and wing it",
    "say yes just to please someone",
    "make a big purchase impulsively",
    "ignore my gut feeling",
    "rush a major decision",
    "accept something that feels wrong",
    "overcommit and burn out",
    "avoid the hard conversation",
]
RESPONSIBILITIES = [
    "class", "work", "my deadlines", "sleep", "eating", "taking care of myself",
    "responding to something important", "preparing for my exam",
]
UNCERTAIN_EVENTS = [
    "something good happen", "I get good news", "I run into them", "things feel clearer",
    "I get the answer I want", "I get an opportunity", "I feel calmer", "I feel confident again",
]
UNCERTAIN_TOPICS = [
    "this situation", "this relationship", "this plan", "this decision", "this new path",
    "my next step", "the thing I’m hoping for", "the outcome I want",
]
PEOPLE = ["they", "my friend", "my teammate", "my family", "my boss", "someone close to me", "that person"]

def clean_time(t: str) -> str:
    t = t.strip()
    return t if t else "soon"

def render(pattern: str) -> str:
    return pattern.format(
        time=clean_time(random.choice(TIMES)),
        action=random.choice(ACTIONS),
        option=random.choice(OPTIONS),
        risky_action=random.choice(RISKY_ACTIONS),
        responsibility=random.choice(RESPONSIBILITIES),
        uncertain_event=random.choice(UNCERTAIN_EVENTS),
        uncertain_topic=random.choice(UNCERTAIN_TOPICS),
        person=random.choice(PEOPLE),
    )

def make_examples(n: int):
    # Balanced labels (roughly equal)
    per = n // 3
    labels = (["YES"] * per) + (["NO"] * per) + (["MAYBE"] * (n - 2 * per))
    random.shuffle(labels)

    seen = set()
    rows = []
    attempts = 0
    max_attempts = n * 50

    for label in labels:
        attempts += 1
        if attempts > max_attempts:
            break

        if label == "YES":
            pat = random.choice(YES_PATTERNS)
        elif label == "NO":
            pat = random.choice(NO_PATTERNS)
        else:
            pat = random.choice(MAYBE_PATTERNS)

        q = render(pat)

        # light dedupe (won’t hang)
        if q in seen:
            continue
        seen.add(q)

        rows.append({"input": q, "output": label})

    # If dedupe trimmed too much, fill the rest without dedupe
    while len(rows) < n:
        label = random.choice(ALLOWED)
        if label == "YES":
            pat = random.choice(YES_PATTERNS)
        elif label == "NO":
            pat = random.choice(NO_PATTERNS)
        else:
            pat = random.choice(MAYBE_PATTERNS)
        q = render(pat)
        rows.append({"input": q, "output": label})

    return rows[:n]

def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = make_examples(N)

    # Append mode so you can keep adding later
    with OUT_PATH.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Appended {len(rows)} examples to {OUT_PATH}")

if __name__ == "__main__":
    main()

