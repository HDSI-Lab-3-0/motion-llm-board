#!/usr/bin/env python3
"""
tinker_infer.py

- Reads adapter path from data/adapter_path.txt
- Creates a Tinker SamplingClient
- Gets a tokenizer via create_lora_training_client(...).get_tokenizer()
- Encodes prompt -> token IDs
- Builds ModelInput(chunks=[EncodedTextChunk(tokens=token_ids)])
- Calls sampling_client.sample(...) (returns Future) and waits .result()
- Prints ONLY final label (YES/NO/MAYBE) to stdout (pipeline-friendly)
- Logs go to stderr
"""

import argparse
import sys
from pathlib import Path

import tinker
from tinker import types


DEFAULT_ADAPTER_PATH_FILE = "data/adapter_path.txt"
DEFAULT_BASE_MODEL = "meta-llama/Llama-3.1-8B-Instruct"


def _eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def load_clients(adapter_path_file: str, base_model: str):
    """
    Mirrors your testmodel.py pattern:
      service_client = tinker.ServiceClient()
      sampling_client = service_client.create_sampling_client(model_path=model_path)
      training_client = service_client.create_lora_training_client(base_model=base_model)
      tokenizer = training_client.get_tokenizer()
    """
    path = Path(adapter_path_file)
    if not path.exists():
        raise FileNotFoundError(f"Adapter path file not found: {adapter_path_file}")

    model_path = path.read_text(encoding="utf-8").strip()
    if not model_path:
        raise ValueError(f"Adapter path file is empty: {adapter_path_file}")

    _eprint("Loading adapter from:", model_path)

    service_client = tinker.ServiceClient()
    sampling_client = service_client.create_sampling_client(model_path=model_path)

    training_client = service_client.create_lora_training_client(base_model=base_model)
    tokenizer = training_client.get_tokenizer()

    return sampling_client, tokenizer


def build_prompt(user_text: str) -> str:
    user_text = user_text.strip()
    return (
        "You are a Magic 8 Ball. Respond with exactly ONE token: YES, NO, or MAYBE.\n"
        f"Question: {user_text}\n"
        "Answer:"
    )


def encode_tokens(tokenizer, text: str) -> list[int]:
    """
    Get token IDs from the tokenizer in a robust way.
    Different tokenizer objects expose different APIs.
    We try common patterns in order.
    """
    # 1) HuggingFace-like: tokenizer.encode(text)
    if hasattr(tokenizer, "encode") and callable(tokenizer.encode):
        out = tokenizer.encode(text)
        # could be List[int] or dict-like
        if isinstance(out, list) and (len(out) == 0 or isinstance(out[0], int)):
            return out
        if isinstance(out, dict) and "input_ids" in out:
            ids = out["input_ids"]
            if isinstance(ids, list) and ids and isinstance(ids[0], list):
                return ids[0]
            return ids

    # 2) HuggingFace-like: tokenizer(text) -> dict with input_ids
    if callable(tokenizer):
        out = tokenizer(text)
        if isinstance(out, dict) and "input_ids" in out:
            ids = out["input_ids"]
            if isinstance(ids, list) and ids and isinstance(ids[0], list):
                return ids[0]
            return ids

    # 3) tiktoken-like: tokenizer.encode(text) already covered, but just in case
    raise RuntimeError("Could not encode tokens: tokenizer API not recognized.")


def make_model_input_from_tokens(token_ids: list[int]) -> types.ModelInput:
    """
    Build ModelInput requiring EncodedTextChunk(tokens=...).
    Your validation error explicitly references EncodedTextChunk.tokens as required.
    """
    if not hasattr(types, "EncodedTextChunk"):
        raise RuntimeError("tinker.types.EncodedTextChunk not found, but ModelInput expects it.")

    EncodedTextChunk = types.EncodedTextChunk

    # Some pydantic models are strict about field names; we know 'tokens' is required.
    # Token IDs must be a list[int].
    chunk = EncodedTextChunk(tokens=token_ids)

    return types.ModelInput(chunks=[chunk])


def extract_text(sample_response) -> str:
    """
    Best-effort extraction from the SampleResponse object.
    """
    if sample_response is None:
        return ""

    if isinstance(sample_response, str):
        return sample_response

    # Common attribute names
    for attr in ("text", "output_text", "completion", "response"):
        if hasattr(sample_response, attr):
            val = getattr(sample_response, attr)
            if isinstance(val, str):
                return val

    # Dict-like
    if isinstance(sample_response, dict):
        for k in ("text", "output_text", "completion", "response"):
            v = sample_response.get(k)
            if isinstance(v, str):
                return v

    # Nested list fields
    for attr in ("samples", "generations", "outputs", "candidates"):
        if hasattr(sample_response, attr):
            items = getattr(sample_response, attr)
            if isinstance(items, (list, tuple)) and items:
                first = items[0]
                if isinstance(first, str):
                    return first
                if hasattr(first, "text") and isinstance(first.text, str):
                    return first.text
                if isinstance(first, dict) and isinstance(first.get("text"), str):
                    return first["text"]

    return str(sample_response)


def clean_answer(raw: str) -> str:
    """
    Force a single token output for your Ouija board.
    """
    if not raw:
        return "MAYBE"
    txt = raw.strip().upper()
    if not txt:
        return "MAYBE"

    first = txt.split()[0]
    first = first.strip(".,!?:;\"'()[]{}")

    if first in ("YES", "NO", "MAYBE"):
        return first

    for token in ("YES", "NO", "MAYBE"):
        if token in txt:
            return token

    return "MAYBE"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True, help="Question text to classify")
    ap.add_argument("--adapter_path_file", default=DEFAULT_ADAPTER_PATH_FILE)
    ap.add_argument("--base_model", default=DEFAULT_BASE_MODEL)

    ap.add_argument("--num_samples", type=int, default=1)
    ap.add_argument("--max_new_tokens", type=int, default=6)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--top_p", type=float, default=1.0)
    ap.add_argument("--top_k", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)

    args = ap.parse_args()

    sampling_client, tokenizer = load_clients(args.adapter_path_file, args.base_model)

    prompt_str = build_prompt(args.text)
    token_ids = encode_tokens(tokenizer, prompt_str)

    model_input = make_model_input_from_tokens(token_ids)

    sampling_params = types.SamplingParams(
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        top_p=args.top_p,
        top_k=args.top_k,
        seed=args.seed,
    )

    fut = sampling_client.sample(
        prompt=model_input,
        num_samples=args.num_samples,
        sampling_params=sampling_params,
        include_prompt_logprobs=False,
        topk_prompt_logprobs=0,
    )

    resp = fut.result()
    raw_text = extract_text(resp)
    answer = clean_answer(raw_text)

    # stdout: ONLY final answer
    print(answer)


if __name__ == "__main__":
    main()

