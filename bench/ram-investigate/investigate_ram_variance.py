"""Investigation 1: measure peak_ram_mb variance by repeating each beam N times.

Each run is a separate process (uv run) to maintain process isolation.
Output: per-beam statistics (mean, stddev, min, max of peak_ram_mb).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RESULTS_ROOT = Path("bench-results/investigation/m2m100")
BEAMS = [1, 2, 4, 5, 8]
REPS = 5
MANIFEST = "eval_data/mt_subset_beam.json"
CANDIDATE = "m2m100-vi-en-ct2-cpu"


def run_one(beam: int, rep: int) -> float | None:
    out_dir = RESULTS_ROOT / f"rep-{rep}" / f"beam-{beam}"
    if out_dir.exists():
        result_file = out_dir / "run_results.json"
        if result_file.exists():
            records = json.loads(result_file.read_text(encoding="utf-8"))
            ram_vals = [
                r["result"]["peak_ram_mb"]
                for r in records
                if r["result"].get("peak_ram_mb") is not None
            ]
            return max(ram_vals) if ram_vals else None
        print(f"  SKIP (dir exists but no run_results.json) beam={beam} rep={rep}")
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "bench.run",
        "--out", str(out_dir),
        "--manifest", MANIFEST,
        "--candidate", CANDIDATE,
        "--config-override", json.dumps({"beam_size": beam}),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT beam={beam} rep={rep}")
        return None

    if result.returncode != 0:
        print(f"  FAILED beam={beam} rep={rep}: {result.stderr.strip()[:200]}")
        return None

    result_file = out_dir / "run_results.json"
    if not result_file.exists():
        print(f"  MISSING output for beam={beam} rep={rep}")
        return None

    records = json.loads(result_file.read_text(encoding="utf-8"))
    ram_vals = [
        r["result"]["peak_ram_mb"]
        for r in records
        if r["result"].get("peak_ram_mb") is not None
    ]
    if not ram_vals:
        print(f"  NO ram_vals for beam={beam} rep={rep}")
        return None
    return max(ram_vals)


def main() -> None:
    # collect results
    results: dict[int, list[float]] = {b: [] for b in BEAMS}
    for beam in BEAMS:
        print(f"\nBeam = {beam}")
        for rep in range(1, REPS + 1):
            ram = run_one(beam, rep)
            if ram is not None:
                results[beam].append(ram)
                print(f"  rep {rep}: {ram:.1f} MB")
            else:
                print(f"  rep {rep}: FAILED")

    # print statistics
    print("\n\n========== Summary ==========")
    print(f"{'Beam':<6} {'N':<4} {'Mean (MB)':<12} {'Std (MB)':<12} {'Min (MB)':<12} {'Max (MB)':<12} {'Range':<12}")
    print("-" * 72)
    for beam in BEAMS:
        vals = results[beam]
        if not vals:
            continue
        mean = sum(vals) / len(vals)
        std = (sum((x - mean) ** 2 for x in vals) / len(vals)) ** 0.5
        vmin = min(vals)
        vmax = max(vals)
        print(f"{beam:<6} {len(vals):<4} {mean:<12.1f} {std:<12.2f} {vmin:<12.1f} {vmax:<12.1f} {vmax - vmin:<12.1f}")


if __name__ == "__main__":
    main()
