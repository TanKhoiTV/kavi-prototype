"""Investigation 3a: does CT2 load-time peak change with runtime Translator params?

Try different `max_queued_batches` and `inter_threads` to see if they
affect the load-time peak_wset. If yes → CT2 allocates workspace at load
based on runtime params. If no → workspace is fixed at conversion time.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import psutil


def peak_mb() -> float:
    return psutil.Process().memory_info().peak_wset / (1024.0**2)


def rss_mb() -> float:
    return psutil.Process().memory_info().rss / (1024.0**2)


def run_config(label: str, max_queued_batches: int = 0, inter_threads: int = 1) -> dict:
    # Snap RSS+peak before anything
    rss_before = rss_mb()
    peak_before = peak_mb()

    # Import + load with the given params
    import ctranslate2

    model_dir = Path("models/m2m100-418m-ct2-int8")
    translator = ctranslate2.Translator(
        str(model_dir),
        device="cpu",
        compute_type="int8",
        inter_threads=inter_threads,
        max_queued_batches=max_queued_batches,
    )

    rss_after_load = rss_mb()
    peak_after_load = peak_mb()

    # Decode one item to see runtime delta
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        "facebook/m2m100_418M", src_lang="vi"
    )
    en_token = tokenizer.lang_code_to_token["en"]
    tokens = tokenizer.convert_ids_to_tokens(
        tokenizer.encode("Hom nay troi dep qua.")
    )
    target_prefix = [[en_token]]

    rss_before_decode = rss_mb()
    translator.translate_batch(
        [tokens],
        target_prefix=target_prefix,
        beam_size=8,
        repetition_penalty=1.1,
        no_repeat_ngram_size=3,
        max_decoding_length=256,
    )
    rss_after_decode = rss_mb()
    peak_final = peak_mb()

    return {
        "label": label,
        "params": {
            "max_queued_batches": max_queued_batches,
            "inter_threads": inter_threads,
        },
        "rss_before": round(rss_before, 1),
        "rss_after_load": round(rss_after_load, 1),
        "peak_after_load": round(peak_after_load, 1),
        "rss_before_decode": round(rss_before_decode, 1),
        "rss_after_decode": round(rss_after_decode, 1),
        "peak_final": round(peak_final, 1),
        "load_delta_rss": round(rss_after_load - rss_before, 1),
        "decode_delta_rss": round(rss_after_decode - rss_before_decode, 1),
    }


def main() -> None:
    print("=== Investigation 3a: CT2 load-time peak vs runtime params ===\n")

    configs = [
        ("default (mqb=0, it=1)", 0, 1),
        ("mqb=1", 1, 1),
        ("mqb=16", 16, 1),
        ("mqb=0, it=4", 0, 4),
    ]

    results = []
    for label, mqb, it in configs:
        print(f"[{label}] Loading model...")
        r = run_config(label, mqb, it)
        results.append(r)
        print(f"  RSS: {r['rss_before']} -> {r['rss_after_load']} MB  "
              f"(load delta: {r['load_delta_rss']})")
        print(f"  peak_wset after load: {r['peak_after_load']} MB")
        print(f"  Decode delta: {r['decode_delta_rss']} MB")
        print()

    print("--- Summary ---")
    header = f"{'Config':<28} {'RSSbef':>7} {'RSSaft':>7} {'Peak':>7} {'DecΔ':>6}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(f"{r['label']:<28} {r['rss_before']:>7.1f} {r['rss_after_load']:>7.1f} "
              f"{r['peak_after_load']:>7.1f} {r['decode_delta_rss']:>+6.1f}")

    out_path = Path("bench-results/investigation/m2m100-ram-phases-3a.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nJSON written to {out_path}")


if __name__ == "__main__":
    main()
