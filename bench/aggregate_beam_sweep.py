"""Aggregate beam-width sweep result directories into the issue #88 table.

Supports multiple candidates: pass --candidates to compare models side by side.
Each candidate's results live under bench-results/<candidate-id>/beam-<N>/.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_records(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def summarize(records: list[dict]) -> dict:
    bleu_vals = [
        r["metrics"]["bleu"] for r in records if r["metrics"].get("bleu") is not None
    ]
    lat_vals = [r["result"]["latency_s"] for r in records if not r["result"].get("error")]
    ram_vals = [r["result"]["peak_ram_mb"] for r in records if r["result"].get("peak_ram_mb")]
    n_err = sum(1 for r in records if r["result"].get("error"))
    return {
        "n": len(records),
        "n_err": n_err,
        "bleu": sum(bleu_vals) / len(bleu_vals) if bleu_vals else None,
        "latency_s": sum(lat_vals) / len(lat_vals) if lat_vals else None,
        "peak_ram_mb": max(ram_vals) if ram_vals else None,
    }


def load_candidate_rows(root: Path, candidate: str, beams: list[int]) -> dict[int, dict]:
    rows: dict[int, dict] = {}
    for beam in beams:
        p = root / candidate / f"beam-{beam}" / "run_results.json"
        if not p.exists():
            print(f"  MISSING: {p} -- chay sweep cho {candidate} beam={beam} truoc")
            continue
        rows[beam] = summarize(load_records(p))
    return rows


def print_candidate_table(candidate: str, rows: dict[int, dict], beams: list[int]) -> None:
    if 1 not in rows or rows[1]["latency_s"] is None:
        print(f"ERROR ({candidate}): thieu baseline beam=1 (hoac toan loi) -- bo qua model nay")
        return

    baseline_latency = rows[1]["latency_s"]
    baseline_ram = rows[1]["peak_ram_mb"]

    print(f"\n== {candidate} ==")
    header = (
        f"{'Beam':<8} {'BLEU':>7} {'Rel.latency':>12} "
        f"{'D_RAM(MB)':>10} {'RAM abs(MB)':>12} {'Errors':>7}"
    )
    print(header)
    print("-" * len(header))
    for beam in beams:
        if beam not in rows:
            continue
        r = rows[beam]
        rel_lat = f"{r['latency_s'] / baseline_latency:.2f}x" if r["latency_s"] else "-"
        delta_ram = (
            f"{r['peak_ram_mb'] - baseline_ram:+.0f}"
            if r["peak_ram_mb"] is not None and baseline_ram is not None
            else "-"
        )
        ram_abs = f"{r['peak_ram_mb']:.0f}" if r["peak_ram_mb"] is not None else "-"
        bleu_str = f"{r['bleu']:.1f}" if r["bleu"] is not None else "-"
        print(
            f"{beam:<8} {bleu_str:>7} {rel_lat:>12} "
            f"{delta_ram:>10} {ram_abs:>12} {r['n_err']:>7}"
        )


def print_cross_model_table(
    all_rows: dict[str, dict[int, dict]], beams: list[int]
) -> None:
    print("\n== So sanh cheo BLEU giua cac model (theo beam width) ==")
    header = f"{'Beam':<8}" + "".join(f"{cand:>28}" for cand in all_rows)
    print(header)
    for beam in beams:
        line = f"{beam:<8}"
        for cand in all_rows:
            r = all_rows[cand].get(beam)
            bleu_str = f"{r['bleu']:.1f}" if r and r.get("bleu") is not None else "-"
            line += f"{bleu_str:>28}"
        print(line)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-root", default="bench-results")
    ap.add_argument(
        "--candidates",
        nargs="+",
        default=[
            "opus-mt-vi-en-ct2-cpu",
            "m2m100-vi-en-ct2-cpu",
            "hy-mt1.5-1.8b-ct2-cpu",
        ],
    )
    ap.add_argument("--beams", type=int, nargs="+", default=[1, 2, 4, 5, 8])
    args = ap.parse_args()

    root = Path(args.results_root)
    all_rows: dict[str, dict[int, dict]] = {}
    for cand in args.candidates:
        rows = load_candidate_rows(root, cand, args.beams)
        all_rows[cand] = rows
        print_candidate_table(cand, rows, args.beams)

    if len(args.candidates) > 1:
        print_cross_model_table(all_rows, args.beams)


if __name__ == "__main__":
    main()