"""Investigation 3: does CT2's load-time peak depend on convert-time params?

Runs model init + decode in isolated subprocesses with different
Translator init parameters to see if peak_wset changes.

If peak_wset changes with runtime params → CT2 allocates workspace at load.
If peak_wset is constant → workspace is fixed at conversion time.

Also checks the CT2 model config for any convert-time memory settings.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RESULTS_ROOT = Path("bench-results/investigation/m2m100-phases-3")
BEAM = 8  # use largest beam to maximize any runtime allocation signal


def run_config(label: str, max_queued_batches: int = 0, inter_threads: int = 1) -> dict | None:
    out_dir = RESULTS_ROOT / label.replace(" ", "_").replace("=", "-").replace(",", "")
    if out_dir.exists():
        json_file = out_dir / "phases.json"
        if json_file.exists():
            return json.loads(json_file.read_text(encoding="utf-8"))
        return None

    script = f"""
import json, psutil
from pathlib import Path

peak_before = psutil.Process().memory_info().peak_wset / (1024.0**2)
rss_before = psutil.Process().memory_info().rss / (1024.0**2)

import ctranslate2
from transformers import AutoTokenizer

rss_after_import = psutil.Process().memory_info().rss / (1024.0**2)
peak_after_import = psutil.Process().memory_info().peak_wset / (1024.0**2)

model_dir = Path("models/m2m100-418m-ct2-int8")
translator = ctranslate2.Translator(
    str(model_dir),
    device="cpu",
    compute_type="int8",
    inter_threads={inter_threads},
    max_queued_batches={max_queued_batches},
)

rss_after_load = psutil.Process().memory_info().rss / (1024.0**2)
peak_after_load = psutil.Process().memory_info().peak_wset / (1024.0**2)

tokenizer = AutoTokenizer.from_pretrained("facebook/m2m100_418M", src_lang="vi")
en_token = tokenizer.lang_code_to_token["en"]
tokens = tokenizer.convert_ids_to_tokens(tokenizer.encode("Hom nay troi dep qua."))
target_prefix = [[en_token]]

rss_before_decode = psutil.Process().memory_info().rss / (1024.0**2)
translator.translate_batch(
    [tokens],
    target_prefix=target_prefix,
    beam_size={BEAM},
    repetition_penalty=1.1,
    no_repeat_ngram_size=3,
    max_decoding_length=256,
)
rss_after_decode = psutil.Process().memory_info().rss / (1024.0**2)
peak_final = psutil.Process().memory_info().peak_wset / (1024.0**2)

print(json.dumps({{
    "rss_before": round(rss_before, 1),
    "rss_after_import": round(rss_after_import, 1),
    "rss_after_load": round(rss_after_load, 1),
    "rss_before_decode": round(rss_before_decode, 1),
    "rss_after_decode": round(rss_after_decode, 1),
    "peak_before": round(peak_before, 1),
    "peak_after_import": round(peak_after_import, 1),
    "peak_after_load": round(peak_after_load, 1),
    "peak_final": round(peak_final, 1),
}}))
"""
    out_dir.mkdir(parents=True, exist_ok=True)

    # Write the script to a temp file to avoid encoding issues with -c
    script_path = out_dir / "run_phase.py"
    script_path.write_text(script, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        print(f"  FAILED {label}: {result.stderr.strip()[:200]}")
        return None

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"  JSON PARSE ERROR {label}: {e}")
        print(f"  stdout: {result.stdout[:200]}")
        return None

    data["label"] = label
    data["params"] = {"max_queued_batches": max_queued_batches, "inter_threads": inter_threads}

    json_file = out_dir / "phases.json"
    json_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def main() -> None:
    print("=== Investigation 3: CT2 load-time peak vs params ===\n")

    configs = [
        ("default (mqb=0, it=1)", 0, 1),
        ("mqb=1", 1, 1),
        ("mqb=16", 16, 1),
        ("mqb=0, it=4", 0, 4),
    ]

    results = []
    for label, mqb, it in configs:
        print(f"[{label}] Running...")
        r = run_config(label, mqb, it)
        if r:
            results.append(r)
            print(f"  RSS: {r['rss_before']:.0f} -> {r['rss_after_load']:.0f} MB (load) "
                  f"-> {r['rss_after_decode']:.0f} MB (decode)")
            print(f"  peak_wset: {r['peak_before']:.0f} -> {r['peak_after_import']:.0f} "
                  f"-> {r['peak_final']:.0f}")
        print()

    print("--- Summary: peak_wset ---")
    print(f"{'Config':<28} {'Peak_load':>10} {'Peak_final':>11} {'RSS_load':>9} {'RSS_decode':>11}")
    print("-" * 72)
    for r in results:
        print(f"{r['label']:<28} {r['peak_after_load']:>10.0f} {r['peak_final']:>11.0f} "
              f"{r['rss_after_load']:>9.0f} {r['rss_after_decode']:>11.0f}")

    # Also check the CT2 model config for convert-time settings
    print("\n--- CT2 model config ---")
    cfg_file = Path("models/m2m100-418m-ct2-int8/config.json")
    if cfg_file.exists():
        cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
        for k, v in sorted(cfg.items()):
            print(f"  {k}: {v}")

    # Check if there's any other metadata in the model dir
    print("\n--- Model directory files ---")
    model_dir = Path("models/m2m100-418m-ct2-int8")
    for f in sorted(model_dir.iterdir()):
        size_mb = f.stat().st_size / (1024.0**2)
        print(f"  {f.name:<40} {size_mb:.1f} MB")

    out_path = Path("bench-results/investigation/m2m100-ram-phases-3.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nJSON written to {out_path}")


if __name__ == "__main__":
    main()
