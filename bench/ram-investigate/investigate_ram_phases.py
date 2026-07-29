"""Investigation 2: measure RSS at each phase — model load vs decode.

Goal: determine whether peak_ram_mb's flatness comes from the peak
landing at model load time (where CT2 allocates fixed scratch buffers)
rather than at decode time (where KV-cache scales with beam_size).

This runs within a single process (no subprocess) to isolate the
load-time vs decode-time RSS contributions.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import psutil


def rss_mb() -> float:
    return psutil.Process().memory_info().rss / (1024.0**2)


def main() -> None:
    print("=== Investigation 2: RSS at load vs decode ===")
    print()

    rss_before = rss_mb()
    print(f"[1] RSS before anything:     {rss_before:.1f} MB")

    # --- Phase 1: import heavy packages ---
    import ctranslate2 as _ct2
    import transformers as _txf

    rss_after_import = rss_mb()
    print(f"[2] RSS after imports:        {rss_after_import:.1f} MB  "
          f"(+{rss_after_import - rss_before:.1f})")

    # --- Phase 2: load model + tokenizer ---
    model_dir = Path("models/m2m100-418m-ct2-int8")
    tokenizer = _txf.AutoTokenizer.from_pretrained(
        "facebook/m2m100_418M", src_lang="vi"
    )
    en_token = tokenizer.lang_code_to_token["en"]
    translator = _ct2.Translator(str(model_dir), device="cpu", compute_type="int8")

    rss_after_load = rss_mb()
    print(f"[3] RSS after model load:     {rss_after_load:.1f} MB  "
          f"(+{rss_after_load - rss_after_import:.1f})")

    # --- Phase 3: tokenize a sample ---
    text = "Hôm qua tôi đi chợ mua rau và thịt."
    tokens = tokenizer.convert_ids_to_tokens(tokenizer.encode(text))
    target_prefix = [[en_token]]
    print(f"    (sample: {len(tokens)} tokens)")

    # --- Phase 4: decode with each beam size, measure RSS after each ---
    beams = [1, 2, 4, 5, 8]
    results = {}

    for beam in beams:
        rss_before_decode = rss_mb()
        t0 = time.perf_counter()
        out = translator.translate_batch(
            [tokens],
            target_prefix=target_prefix,
            beam_size=beam,
            repetition_penalty=1.1,
            no_repeat_ngram_size=3,
            max_decoding_length=256,
        )
        latency = time.perf_counter() - t0
        rss_after_decode = rss_mb()
        delta = rss_after_decode - rss_before_decode

        results[beam] = {
            "rss_before_decode": round(rss_before_decode, 1),
            "rss_after_decode": round(rss_after_decode, 1),
            "delta_mb": round(delta, 1),
            "latency_s": round(latency, 3),
        }

        print(f"[4] beam={beam:2d}: RSS {rss_before_decode:.1f} -> {rss_after_decode:.1f} MB  "
              f"(delta={delta:+.1f} MB)  latency={latency:.3f}s")

    # --- Phase 5: peak RSS (process-wide all-time high) ---
    peak = psutil.Process().memory_info().peak_wset / (1024.0**2)
    print(f"\n[5] Process peak_wset:        {peak:.1f} MB")
    print(f"    (vs last RSS snapshot:    {rss_mb():.1f} MB)")

    print("\n--- Summary table ---")
    print(f"{'Beam':<6} {'RSSbef':>8} {'RSSaft':>8} {'+(mb)':>7} {'Lat(s)':>7}")
    print("-" * 40)
    for beam in beams:
        r = results[beam]
        print(f"{beam:<6} {r['rss_before_decode']:>8.1f} {r['rss_after_decode']:>8.1f} "
              f"{r['delta_mb']:>+7.1f} {r['latency_s']:>7.3f}")

    # Dump JSON for reference
    out_path = Path("bench-results/investigation/m2m100-ram-phases.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "rss_before": round(rss_before, 1),
                "rss_after_import": round(rss_after_import, 1),
                "rss_after_load": round(rss_after_load, 1),
                "peak_wset": round(peak, 1),
                "per_beam": results,
            },
            indent=2,
        )
    )
    print(f"\nJSON written to {out_path}")


if __name__ == "__main__":
    main()
