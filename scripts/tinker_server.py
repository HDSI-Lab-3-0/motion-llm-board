#!/usr/bin/env python3
import argparse
import sys
import time
import concurrent.futures
from pathlib import Path

import tinker
from tinker import types

DEFAULT_ADAPTER_PATH_FILE = "data/adapter_path.txt"
DEFAULT_BASE_MODEL = "meta-llama/Llama-3.1-8B-Instruct"

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def build_prompt(user_text: str) -> str:
    user_text = user_text.strip()
    return (
        "You are a Magic 8 Ball. Respond with exactly ONE token: YES, NO, or MAYBE.\n"
        f"Question: {user_text}\n"
        "Answer:"
    )

def encode_tokens(tokenizer, text: str) -> list[int]:
    # HuggingFace-like: tokenizer.encode(text)
    if hasattr(tokenizer, "encode") and callable(tokenizer.encode):
        out = tokenizer.encode(text)
        if isinstance(out, list) and (len(out) == 0 or isinstance(out[0], int)):
            return out
        if isinstance(out, dict) and "input_ids" in out:
            ids = out["input_ids"]
            if isinstance(ids, list) and ids and isinstance(ids[0], list):
                return ids[0]
            return ids

    # HuggingFace-like: tokenizer(text) -> dict with input_ids
    if callable(tokenizer):
        out = tokenizer(text)
        if isinstance(out, dict) and "input_ids" in out:
            ids = out["input_ids"]
            if isinstance(ids, list) and ids and isinstance(ids[0], list):
                return ids[0]
            return ids

    raise RuntimeError("Tokenizer API not recognized for encoding tokens.")

def make_model_input_from_tokens(token_ids: list[int]) -> types.ModelInput:
    if not hasattr(types, "EncodedTextChunk"):
        raise RuntimeError("types.EncodedTextChunk not found, but ModelInput expects it.")
    chunk = types.EncodedTextChunk(tokens=token_ids)
    return types.ModelInput(chunks=[chunk])

def extract_text(sample_response) -> str:
    if sample_response is None:
        return ""
    if isinstance(sample_response, str):
        return sample_response

    for attr in ("text", "output_text", "completion", "response"):
        if hasattr(sample_response, attr):
            v = getattr(sample_response, attr)
            if isinstance(v, str):
                return v

    if isinstance(sample_response, dict):
        for k in ("text", "output_text", "completion", "response"):
            v = sample_response.get(k)
            if isinstance(v, str):
                return v

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
    if not raw:
        return "MAYBE"
    txt = raw.strip().upper()
    if not txt:
        return "MAYBE"
    first = txt.split()[0].strip(".,!?:;\"'()[]{}")
    if first in ("YES", "NO", "MAYBE"):
        return first
    for token in ("YES", "NO", "MAYBE"):
        if token in txt:
            return token
    return "MAYBE"

def load_sampling_and_tokenizer(adapter_path_file: str, base_model: str):
    path = Path(adapter_path_file)
    if not path.exists():
        raise FileNotFoundError(f"Adapter path file not found: {adapter_path_file}")

    model_path = path.read_text(encoding="utf-8").strip()
    if not model_path:
        raise ValueError(f"Adapter path file is empty: {adapter_path_file}")

    eprint("Loading adapter from:", model_path)

    service_client = tinker.ServiceClient()

    eprint("Creating sampling client...")
    sampling_client = service_client.create_sampling_client(model_path=model_path)

    eprint("Creating training client (for tokenizer)...")
    training_client = service_client.create_lora_training_client(base_model=base_model)

    eprint("Getting tokenizer...")
    tokenizer = training_client.get_tokenizer()

    eprint("Tinker server ready.")
    return sampling_client, tokenizer

def infer_one(sampling_client, tokenizer, question: str, max_new_tokens: int, temperature: float, timeout_s: int) -> str:
    prompt_str = build_prompt(question)
    token_ids = encode_tokens(tokenizer, prompt_str)
    model_input = make_model_input_from_tokens(token_ids)

    sampling_params = types.SamplingParams(
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        top_p=1.0,
        top_k=0,
        seed=0,
    )

    fut = sampling_client.sample(
        prompt=model_input,
        num_samples=1,
        sampling_params=sampling_params,
        include_prompt_logprobs=False,
        topk_prompt_logprobs=0,
    )

    try:
        resp = fut.result(timeout=timeout_s)
    except concurrent.futures.TimeoutError:
        return "MAYBE"  # safe fallback for demo

    raw = extract_text(resp)
    return clean_answer(raw)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter_path_file", default=DEFAULT_ADAPTER_PATH_FILE)
    ap.add_argument("--base_model", default=DEFAULT_BASE_MODEL)
    ap.add_argument("--max_new_tokens", type=int, default=3)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--timeout_s", type=int, default=30)
    args = ap.parse_args()

    sampling_client, tokenizer = load_sampling_and_tokenizer(args.adapter_path_file, args.base_model)

    # Read one question per line from stdin; write one answer per line to stdout
    for line in sys.stdin:
        q = line.strip()
        if not q:
            continue
        ans = infer_one(
            sampling_client, tokenizer, q,
            max_new_tokens=args.max_new_tokens,
            temperature=args.temperature,
            timeout_s=args.timeout_s
        )
        print(ans, flush=True)

if __name__ == "__main__":
    main()

