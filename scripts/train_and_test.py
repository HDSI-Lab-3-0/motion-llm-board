import json
import numpy as np
import tinker
from tinker import types
from datetime import datetime

# --- Setup ---
service_client = tinker.ServiceClient()

print("Available models:")
for m in service_client.get_server_capabilities().supported_models:
    print("-", m)

base_model = "meta-llama/Llama-3.1-8B-Instruct"
training_client = service_client.create_lora_training_client(base_model=base_model)
ADAPTER_NAME = "answer-board-balanced-" + datetime.now().strftime("%Y%m%d-%H%M")
# --- Data ---
DATA_PATH = "data/ouija_train.jsonl"  # <-- put your file here

ALLOWED_LABELS = {"YES", "NO", "MAYBE"}

def load_jsonl(path: str):
    examples = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)

            # Support either {"input","output"} OR {"Question","Answer"}
            if "input" in obj and "output" in obj:
                q = obj["input"]
                a = obj["output"]
            elif "Question" in obj and "Answer" in obj:
                q = obj["Question"]
                a = obj["Answer"]
            else:
                raise ValueError(f"Bad JSONL format at line {line_num}. Keys: {list(obj.keys())}")

            q = str(q).strip()
            a = str(a).strip().upper()

            if a not in ALLOWED_LABELS:
                raise ValueError(f"Invalid label at line {line_num}: '{a}' (allowed: {sorted(ALLOWED_LABELS)})")

            examples.append({"input": q, "output": a})
    return examples

examples = load_jsonl(DATA_PATH) + load_jsonl("data/manual_additions.jsonl")
print(f"Loaded {len(examples)} examples from {DATA_PATH}")

# --- Tokenizer ---
tokenizer = training_client.get_tokenizer()

def process_example(example, tokenizer):
    prompt = f"Question: {example['input']}\nAnswer:"
    prompt_tokens = tokenizer.encode(prompt, add_special_tokens=True)
    prompt_weights = [0] * len(prompt_tokens)

    completion_tokens = tokenizer.encode(f" {example['output']}\n", add_special_tokens=False)
    completion_weights = [1] * len(completion_tokens)

    tokens = prompt_tokens + completion_tokens
    weights = prompt_weights + completion_weights

    input_tokens = tokens[:-1]
    target_tokens = tokens[1:]
    weights = weights[1:]

    return types.Datum(
        model_input=types.ModelInput.from_ints(tokens=input_tokens),
        loss_fn_inputs=dict(weights=weights, target_tokens=target_tokens),
    )

processed_examples = [process_example(ex, tokenizer) for ex in examples]

# --- Train ---
adam_params = types.AdamParams(learning_rate=1e-4)
EPOCHS = 4

print("\nStarting training...")
for epoch in range(EPOCHS):
    print(f"\nEpoch {epoch + 1}/{EPOCHS}")

    fwdbwd_future = training_client.forward_backward(processed_examples, "cross_entropy")
    optim_future = training_client.optim_step(adam_params)

    fwdbwd_result = fwdbwd_future.result()
    _ = optim_future.result()

    logprobs = np.concatenate([o["logprobs"].tolist() for o in fwdbwd_result.loss_fn_outputs])
    weights = np.concatenate([ex.loss_fn_inputs["weights"].tolist() for ex in processed_examples])

    loss = -np.dot(logprobs, weights) / weights.sum()
    print(f"  Loss: {loss:.4f}")

print("\nTraining complete!")

# --- Save adapter for reuse (IMPORTANT) ---
save_result = training_client.save_weights_for_sampler(
    name=ADAPTER_NAME
).result()

sampling_path = save_result.path
print("SAVED SAMPLING PATH:", sampling_path)

# Save path so other scripts can load the trained adapter
with open("data/adapter_path.txt", "w") as f:
    f.write(sampling_path + "\n")

with open("data/adapter_history.txt", "a") as f:
    f.write(f"{ADAPTER_NAME}\t{sampling_path}\n")

print(f"Adapter '{ADAPTER_NAME}' saved for reuse.")

# --- QUICK SANITY TEST: load sampler from saved path ---
sampling_client = service_client.create_sampling_client(
    model_path=sampling_path
)
print("Sampling client loaded from saved path (sanity test).")


def ask_board(question: str) -> str:
    prompt_text = f"Question: {question}\nAnswer:"
    prompt = types.ModelInput.from_ints(tokenizer.encode(prompt_text))

    # Use enough tokens to avoid truncating "MAYBE"
    params = types.SamplingParams(max_tokens=10, temperature=0.0, stop=["\n"])

    result = sampling_client.sample(prompt=prompt, sampling_params=params, num_samples=1).result()
    raw = tokenizer.decode(result.sequences[0].tokens).strip()

    # Force label-only output
    label = raw.split()[0].upper()
    if label.startswith("MAY"):
        label = "MAYBE"
    if label not in ALLOWED_LABELS:
        label = "MAYBE"

    print("Answer:", label)
    return label

ask_board("Will tomorrow be good?")

