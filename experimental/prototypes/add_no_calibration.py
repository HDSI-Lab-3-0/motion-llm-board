import json
from pathlib import Path

OUT = Path("data/manual_additions.jsonl")

NO_EXAMPLES = [
    "Should I text them again even though they ignored me?",
    "Should I quit my job today with no backup plan?",
    "Should I spend money I don't have right now?",
    "Should I ignore clear red flags and continue anyway?",
    "Should I drive if I'm too tired to focus?",
    "Should I skip sleep again to cram all night?",
    "Should I lie to make this easier?",
    "Should I make a big decision while I'm emotional?",
    "Should I say yes just because I feel guilty?",
    "Should I ghost them instead of communicating?",
    "Should I overpromise when I can't deliver?",
    "Should I rush into a commitment after one good day?",
    "Should I avoid the hard conversation forever?",
    "Should I post something petty online?",
    "Should I keep chasing someone who doesn't respect me?",
    "Should I risk my grades for short-term fun tonight?",
    "Should I sign something I haven't read?",
    "Should I take on more work when I'm already burned out?",
    "Should I sabotage this because I'm scared?",
    "Should I make a purchase just to feel better?",
]

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)

    # repeat variations by adding light prefixes/suffixes
    rows = []
    for base in NO_EXAMPLES:
        rows.append({"input": base, "output": "NO"})
        rows.append({"input": base.replace("Should I", "Is it smart to"), "output": "NO"})
        rows.append({"input": base.replace("Should I", "Would it be a bad idea to"), "output": "NO"})
        rows.append({"input": base + " Be honest.", "output": "NO"})
        rows.append({"input": base + " Quick answer only.", "output": "NO"})

    with OUT.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Appended {len(rows)} NO calibration examples to {OUT}")

if __name__ == "__main__":
    main()

