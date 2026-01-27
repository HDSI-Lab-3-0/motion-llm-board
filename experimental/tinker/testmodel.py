import json
import random
import tinker
from tinker import types

# --- Load adapter path saved by train_and_test.py ---
ADAPTER_PATH_FILE = "data/adapter_path.txt"
with open(ADAPTER_PATH_FILE, "r", encoding="utf-8") as f:
    model_path = f.read().strip()

print("Loading adapter from:", model_path)

# --- Setup clients ---
service_client = tinker.ServiceClient()
sampling_client = service_client.create_sampling_client(model_path=model_path)

# Tokenizer (same base model you trained)
base_model = "meta-llama/Llama-3.1-8B-Instruct"
training_client = service_client.create_lora_training_client(base_model=base_model)
tokenizer = training_client.get_tokenizer()

ALLOWED = {"YES", "NO", "MAYBE"}

def ask_board(question: str, debug_raw: bool = False) -> str:
    prompt_text = (
        "You are a Ouija board classifier.\n"
        "Reply with EXACTLY ONE label: YES, NO, or MAYBE.\n"
        "No extra text.\n\n"
        f"Question: {question}\n"
        "Answer:"
    )

    prompt = types.ModelInput.from_ints(tokenizer.encode(prompt_text))

    params = types.SamplingParams(
        max_tokens=4,
        temperature=0.8,
        stop=["\n"],
    )

    res = sampling_client.sample(prompt=prompt, sampling_params=params, num_samples=1).result()
    raw = tokenizer.decode(res.sequences[0].tokens).strip()

    if debug_raw:
        print("RAW:", raw)

    label = raw.split()[0].upper()
    if label.startswith("MAY"):
        label = "MAYBE"
    if label not in ALLOWED:
        label = "MAYBE"
    return label


# ----------- REAL TESTS -----------

def quick_batch_test():
    questions = [
        "Will tomorrow be good?",
        "Should I text them tonight?",
        "Is someone thinking about me?",
        "Am I on the right path?",
        "Will I get good news soon?",
        "Should I stay in tonight?",
        "Is next week going to be stressful?",
        "Should I take a break today?",
    ]

    print("\n--- Quick Batch Test ---")
    for q in questions:
        print(f"{q} -> {ask_board(q, debug_raw=True)}")


def stress_test(n=100):
    starters = ["Should I", "Will I", "Is it", "Am I", "Will", "Is", "Should"]
    verbs = ["go out", "study", "rest", "text them", "take the risk", "wait", "commit", "start over", "change plans"]
    times = ["today", "tonight", "tomorrow", "this week", "soon", "next week"]

    counts = {"YES": 0, "NO": 0, "MAYBE": 0}
    bad = []

    print(f"\n--- Stress Test ({n}) ---")
    for _ in range(n):
        q = f"{random.choice(starters)} {random.choice(verbs)} {random.choice(times)}?"
        label = ask_board(q)
        if label in counts:
            counts[label] += 1
        else:
            bad.append((q, label))

    print("Counts:", counts)
    print("Bad outputs:", len(bad))
    if bad:
        print("First 10 bad:")
        for q, l in bad[:10]:
            print(q, "->", l)


def eval_on_testset(path="data/test.jsonl"):
    """
    Optional: create data/test.jsonl with ~50 hand-labeled examples:
    {"input":"Should I go out tonight?","output":"YES"}
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        print(f"\n(No {path} found — skipping eval_on_testset)")
        return

    correct = 0
    total = 0

    print(f"\n--- Eval on {path} ---")
    for ex in rows:
        q = ex["input"]
        y = ex["output"].strip().upper()
        pred = ask_board(q)
        total += 1
        correct += int(pred == y)

    print(f"Accuracy: {correct}/{total} = {correct/total:.2%}")


if __name__ == "__main__":
    quick_batch_test()
    stress_test(100)
    eval_on_testset("data/test.jsonl")

