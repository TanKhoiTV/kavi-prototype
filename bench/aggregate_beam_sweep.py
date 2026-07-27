"""Aggregate beam-width sweep result directories into the issue #88 table."""

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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-root", default="bench-results")
    ap.add_argument("--beams", type=int, nargs="+", default=[1, 2, 4, 5, 8])
    args = ap.parse_args()

    root = Path(args.results_root)
    rows: dict[int, dict] = {}
    for beam in args.beams:
        p = root / f"beam-{beam}" / "run_results.json"
        if not p.exists():
            print(f"  MISSING: {p} — chạy sweep cho beam={beam} trước")
            continue
        rows[beam] = summarize(load_records(p))

    if 1 not in rows or rows[1]["latency_s"] is None:
        print("ERROR: thiếu baseline beam=1 (hoặc toàn lỗi) — không tính được relative latency")
        return

    baseline_latency = rows[1]["latency_s"]
    baseline_ram = rows[1]["peak_ram_mb"]

    print(f"{'Beam':<8} {'BLEU':>7} {'Rel.latency':>12} {'D_RAM(MB)':>10} {'Errors':>7}")
    print("-" * 50)
    for beam in args.beams:
        if beam not in rows:
            continue
        r = rows[beam]
        rel_lat = f"{r['latency_s'] / baseline_latency:.2f}x" if r["latency_s"] else "-"
        delta_ram = (
            f"{r['peak_ram_mb'] - baseline_ram:+.0f}"
            if r["peak_ram_mb"] is not None and baseline_ram is not None
            else "-"
        )
        bleu_str = f"{r['bleu']:.1f}" if r["bleu"] is not None else "-"
        print(f"{beam:<8} {bleu_str:>7} {rel_lat:>12} {delta_ram:>10} {r['n_err']:>7}")


if __name__ == "__main__":
    main()