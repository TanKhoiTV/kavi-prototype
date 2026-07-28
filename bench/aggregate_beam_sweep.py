"""Aggregate beam-width sweep results. Supports MT (bleu) and ASR (wer)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

METRIC_DIRECTION = {"bleu": "higher", "wer": "lower"}


def load_records(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def summarize(records: list[dict], metric: str) -> dict:
    metric_vals = [
        r["metrics"][metric] for r in records if r["metrics"].get(metric) is not None
    ]
    lat_vals = [
        r["result"]["latency_s"] for r in records if not r["result"].get("error")
    ]
    rtf_vals = [
        r["metrics"]["rtf"] for r in records if r["metrics"].get("rtf") is not None
    ]
    ram_vals = [
        r["result"]["peak_ram_mb"]
        for r in records
        if r["result"].get("peak_ram_mb")
    ]
    n_err = sum(1 for r in records if r["result"].get("error"))

    rtf = sum(rtf_vals) / len(rtf_vals) if rtf_vals else None

    return {
        "n": len(records),
        "n_err": n_err,
        "metric": sum(metric_vals) / len(metric_vals) if metric_vals else None,
        "latency_s": sum(lat_vals) / len(lat_vals) if lat_vals else None,
        "rtf": rtf,
        "peak_ram_mb": max(ram_vals) if ram_vals else None,
    }


def load_rows(
    root: Path, candidate: str, lang: str | None, beams: list[int], metric: str
) -> dict[int, dict]:
    rows: dict[int, dict] = {}
    for beam in beams:
        p = root / candidate
        if lang:
            p = p / lang
        p = p / f"beam-{beam}" / "run_results.json"
        if not p.exists():
            print(f"  MISSING: {p}")
            continue
        rows[beam] = summarize(load_records(p), metric)
    return rows


def print_table(
    label: str, rows: dict[int, dict], beams: list[int], metric: str
) -> None:
    if 1 not in rows or rows[1]["latency_s"] is None:
        print(f"ERROR ({label}): thieu baseline beam=1 (hoac toan loi)")
        return

    baseline_latency = rows[1]["latency_s"]
    baseline_ram = rows[1]["peak_ram_mb"]

    print(f"\n== {label} ==")
    metric_col = metric.upper()
    header = (
        f"{'Beam':<8} {metric_col:>7} {'RTF':>7} "
        f"{'Rel.latency':>12} {'D_RAM(MB)':>10} {'Errors':>7}"
    )
    print(header)
    print("-" * len(header))
    for beam in beams:
        if beam not in rows:
            continue
        r = rows[beam]
        rel_lat = (
            f"{r['latency_s'] / baseline_latency:.2f}x"
            if r["latency_s"]
            else "-"
        )
        rtf_str = f"{r['rtf']:.2f}" if r["rtf"] is not None else "-"
        delta_ram = (
            f"{r['peak_ram_mb'] - baseline_ram:+.0f}"
            if r["peak_ram_mb"] is not None and baseline_ram is not None
            else "-"
        )
        met_str = f"{r['metric']:.3f}" if r["metric"] is not None else "-"
        print(
            f"{beam:<8} {met_str:>7} {rtf_str:>7} "
            f"{rel_lat:>12} {delta_ram:>10} {r['n_err']:>7}"
        )

    direction = METRIC_DIRECTION.get(metric, "higher")
    print(
        f"  (direction: {metric} — "
        f"{'higher is better' if direction == 'higher' else 'lower is better'})"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-root", default="bench-results")
    ap.add_argument("--candidate", default="whisper-small-multilang-ct2-cpu")
    ap.add_argument(
        "--lang", choices=["vi", "en"], help="ASR audio language direction"
    )
    ap.add_argument(
        "--metric",
        choices=["bleu", "wer"],
        default="wer",
        help="metric to report (bleu=higher-better, wer=lower-better)",
    )
    ap.add_argument("--beams", type=int, nargs="+", default=[1, 2, 4, 5, 8])
    args = ap.parse_args()

    root = Path(args.results_root)
    rows = load_rows(root, args.candidate, args.lang, args.beams, args.metric)

    label = args.candidate
    if args.lang:
        label += f" ({args.lang})"

    print_table(label, rows, args.beams, args.metric)


if __name__ == "__main__":
    main()