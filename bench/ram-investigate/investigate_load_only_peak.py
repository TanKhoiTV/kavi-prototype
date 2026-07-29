"""Investigation 2b: load-only — measure peak_wset with NO decode whatsoever.

A single subprocess that:
  1. Imports ctranslate2
  2. Loads the model (Translator init)
  3. Records peak_wset IMMEDIATELY after load
  4. Exits without any decode call

This isolates the load-time peak from any decode-time contamination.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

OUT_DIR = Path("bench-results/investigation")


def run_load_only(label: str, reps: int = 5) -> list[dict]:
    script = """import json, psutil
rss_before = psutil.Process().memory_info().rss / (1024.0**2)
peak_before = psutil.Process().memory_info().peak_wset / (1024.0**2)

import ctranslate2
from transformers import AutoTokenizer
from pathlib import Path

rss_after_import = psutil.Process().memory_info().rss / (1024.0**2)
peak_after_import = psutil.Process().memory_info().peak_wset / (1024.0**2)

model_dir = Path("models/m2m100-418m-ct2-int8")
translator = ctranslate2.Translator(str(model_dir), device="cpu", compute_type="int8")

rss_after_load = psutil.Process().memory_info().rss / (1024.0**2)
peak_after_load = psutil.Process().memory_info().peak_wset / (1024.0**2)

# Also load tokenizer (like the real candidate does)
tokenizer = AutoTokenizer.from_pretrained("facebook/m2m100_418M", src_lang="vi")

rss_final = psutil.Process().memory_info().rss / (1024.0**2)
peak_final = psutil.Process().memory_info().peak_wset / (1024.0**2)

print(json.dumps({
    "rss_before": round(rss_before, 1),
    "rss_after_import": round(rss_after_import, 1),
    "rss_after_load": round(rss_after_load, 1),
    "rss_final": round(rss_final, 1),
    "peak_before": round(peak_before, 1),
    "peak_after_import": round(peak_after_import, 1),
    "peak_after_load": round(peak_after_load, 1),
    "peak_final": round(peak_final, 1),
}))
"""

    results = []
    for rep in range(1, reps + 1):
        print(f"  rep {rep}...", end=" ", flush=True)
        p = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=120,
        )
        if p.returncode != 0:
            print(f"FAILED: {p.stderr.strip()[:100]}")
            continue
        try:
            data = json.loads(p.stdout)
            data["rep"] = rep
            results.append(data)
            print(f"peak_after_load={data['peak_after_load']:.0f} MB, "
                  f"peak_final={data['peak_final']:.0f} MB")
        except json.JSONDecodeError as e:
            print(f"JSON error: {e}")
            print(f"  stdout: {p.stdout[:200]}")
    return results


def main() -> None:
    print("=== Investigation 2b: Load-only peak measurement (n=5) ===\n")

    results = run_load_only("load-only", reps=5)

    if not results:
        print("No results collected.")
        return

    print("\n--- Summary ---")
    peaks_load = [r["peak_after_load"] for r in results]
    peaks_final = [r["peak_final"] for r in results]
    rss_load = [r["rss_after_load"] for r in results]

    print(f"peak_after_load:  mean={sum(peaks_load)/len(peaks_load):.0f} MB  "
          f"vals={[round(p) for p in peaks_load]}")
    print(f"peak_final:       mean={sum(peaks_final)/len(peaks_final):.0f} MB  "
          f"vals={[round(p) for p in peaks_final]}")
    print(f"rss_after_load:   mean={sum(rss_load)/len(rss_load):.0f} MB  "
          f"vals={[round(r) for r in rss_load]}")

    # Compare with Investigation 1 sweep results (~1105 MB)
    print(f"\nComparison:")
    print(f"  Inv 2b (load-only, n=5):      peak={sum(peaks_load)/len(peaks_load):.0f} MB")
    print(f"  Inv 1 (sweep, separate proc): peak=1105 MB")
    print(f"  Inv 3 (load-only, separate):  peak=1106 MB")

    out_path = OUT_DIR / "m2m100-load-only-peak.json"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWritten to {out_path}")


if __name__ == "__main__":
    main()
