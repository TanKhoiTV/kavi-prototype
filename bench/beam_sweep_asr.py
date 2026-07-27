"""Beam-width sweep for Whisper ASR (faster-whisper) — issue #88.

Iterates beam ∈ {1, 2, 4, 5, 8}, runs a configurable ASR subset,
collects WER, per-item latency, and approximate KV-cache RAM overhead,
then prints the comparison table from the issue template.

Subset defaults to **clean items only** (60 items: 30 VI + 30 EN) to
keep per-beam runtime reasonable (~35 min at ~35 s/item on CPU).

Usage:
    uv run python -m bench.beam_sweep_asr \
        --manifest eval_data/eval_manifest_v1.json \
        --out bench-results/beam-sweep-asr
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

from .registry import REGISTRY
from .schema import EvalItem, RunManifest, StageResult
from .scorer import score_item

BEAM_WIDTHS = [1, 2, 4, 5, 8]


def _current_rss_mb() -> float:
    import psutil
    return psutil.Process().memory_info().rss / (1024.0 ** 2)


@dataclass
class BeamSweepRow:
    beam_width: int
    mean_wer: float | None  # in percent
    total_latency_s: float
    relative_latency: float | None
    kv_cache_mb: float | None
    num_items: int
    errors: int


def run_beam_sweep(
    manifest_path: str,
    out_dir: str,
    candidate_id: str = "whisper-small-faster-whisper-cpu",
    snr_filter: list[float] | None = None,
    noise_filter: list[str] | None = None,
    max_items: int | None = None,
) -> list[BeamSweepRow]:
    """Run one beam-width iteration per value in BEAM_WIDTHS.

    Parameters
    ----------
    snr_filter:
        SNR values to include. ``None`` = clean only. ``[]`` = all.
    noise_filter:
        Noise types to include. ``None`` = clean only. ``[]`` = all.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    manifest = RunManifest.from_json(manifest_path)

    # --- Build item subset ------------------------------------------------
    def _match(item) -> bool:
        if item.stage != "ASR":
            return False
        if item.audio_ref is None:
            return False
        if not Path(item.audio_ref).exists():
            return False
        if item.reference_text is None:
            return False
        if snr_filter is not None and item.snr not in snr_filter:
            return False
        if snr_filter is None and item.snr is not None:
            return False  # default: clean only
        if noise_filter is not None and item.noise_type not in noise_filter:
            return False
        if noise_filter is None and item.noise_type != "clean":
            return False
        return True

    items = [it for it in manifest.items if _match(it)]
    if max_items:
        items = items[:max_items]

    if not items:
        print("No ASR items matched the filter. Check --snrs / --noise-types.")
        return []

    print(f"Manifest: {len(items)} ASR items, beam widths {BEAM_WIDTHS}")
    print(f"  Filter: snr={snr_filter or 'clean'}  noise={noise_filter or 'clean'}")
    print()

    rows: list[BeamSweepRow] = []
    baseline_latency: float | None = None

    for beam in BEAM_WIDTHS:
        print(f"  beam={beam} ...", end=" ", flush=True)

        # Fresh candidate per beam width with explicit beam_size
        cand_cls, cand_model, _ = REGISTRY[candidate_id]
        cand = cand_cls(
            model_path=cand_model,
            config={"beam_size": beam},
        )
        rss_before = _current_rss_mb()

        wers: list[float] = []
        total_lat = 0.0
        n_errors = 0

        for item in items:
            try:
                t0 = time.perf_counter()
                out_text, _ = cand._infer(item)
                lat = time.perf_counter() - t0

                result = StageResult(
                    candidate_id=f"whisper-beam-{beam}",
                    item_id=item.id,
                    stage="ASR",
                    output_text=out_text,
                    latency_s=round(lat, 4),
                )
                metrics = score_item(item, result, audio_duration_s=None)
                if metrics.wer is not None:
                    wers.append(metrics.wer)
                total_lat += lat
            except Exception as exc:
                n_errors += 1
                print(f"\n    error on {item.id}: {exc}", file=sys.stderr)

        rss_after = _current_rss_mb()
        mean_wer = (sum(wers) / len(wers) * 100) if wers else None
        kv_cache = max(0.0, rss_after - rss_before)

        if baseline_latency is None:
            baseline_latency = total_lat
            rel_lat = 1.0
        else:
            rel_lat = total_lat / baseline_latency if baseline_latency > 0 else None

        row = BeamSweepRow(
            beam_width=beam,
            mean_wer=round(mean_wer, 2) if mean_wer is not None else None,
            total_latency_s=round(total_lat, 4),
            relative_latency=round(rel_lat, 4) if rel_lat is not None else None,
            kv_cache_mb=round(kv_cache, 1),
            num_items=len(items) - n_errors,
            errors=n_errors,
        )
        rows.append(row)

        wer_str = f"{mean_wer:.2f}%" if mean_wer is not None else "N/A"
        print(f"WER={wer_str}  lat={total_lat:.1f}s  "
              f"rel={rel_lat:.2f}x  KV-cache={kv_cache:.0f}MB")

    return rows


def print_table(rows: list[BeamSweepRow]) -> None:
    headers = [
        "Beam width",
        "WER (%)",
        "Total latency (s)",
        "Relative latency",
        "KV-cache (MB)",
        "Items",
        "Errors",
    ]
    col_widths = [len(h) for h in headers]

    table_rows = []
    for r in rows:
        wer_str = f"{r.mean_wer:.2f}" if r.mean_wer is not None else "-"
        rel_str = f"{r.relative_latency:.2f}x" if r.relative_latency is not None else "-"
        kv_str = f"{r.kv_cache_mb:.0f}" if r.kv_cache_mb is not None else "-"
        table_rows.append([
            str(r.beam_width),
            wer_str,
            f"{r.total_latency_s:.1f}",
            rel_str,
            kv_str,
            str(r.num_items),
            str(r.errors),
        ])

    for row in [headers] + table_rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    sep = "  "
    rule = "-" * (sum(col_widths) + len(sep) * (len(col_widths) - 1))

    print()
    print("=" * len(rule))
    print("  Beam-width sweep — Whisper Small (faster-whisper, CPU int8)")
    print("=" * len(rule))
    print()
    print(sep.join(h.ljust(w) for h, w in zip(headers, col_widths)))
    print(rule)
    for row in table_rows:
        print(sep.join(c.ljust(w) for c, w in zip(row, col_widths)))
    print(rule)
    print()

    best = min(rows, key=lambda r: r.mean_wer if r.mean_wer is not None else float("inf"))
    print(f"Best WER: beam={best.beam_width}  ({best.mean_wer}%)")
    if rows[0].mean_wer is not None and best.mean_wer is not None:
        impr = rows[0].mean_wer - best.mean_wer
        print(f"Improvement over greedy (beam=1): -{impr:.2f}pp WER")
        print(f"Latency cost: {best.relative_latency:.2f}x vs greedy")

    print()
    print("Verdict: ", end="")
    if best.beam_width == 1:
        print("Greedy is sufficient — no benefit from beam search")
    elif best.beam_width <= 4:
        print(f"Beam={best.beam_width} — best quality/latency trade-off")
    else:
        print(f"Beam={best.beam_width} — best WER, higher latency cost")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    ap = argparse.ArgumentParser(
        description="Beam-width sweep for Whisper ASR (issue #88)"
    )
    ap.add_argument("--manifest", default="eval_data/eval_manifest_v1.json")
    ap.add_argument("--out", default="bench-results/beam-sweep-asr")
    ap.add_argument(
        "--candidate",
        default="whisper-small-faster-whisper-cpu",
        help=f"Candidate ID from registry: {sorted(REGISTRY)}",
    )
    ap.add_argument("--max-items", type=int, default=None)
    ap.add_argument(
        "--snrs",
        type=float,
        nargs="*",
        default=None,
        help="SNR values (default: clean; [] = all)",
    )
    ap.add_argument(
        "--noise-types",
        nargs="*",
        default=None,
        help="Noise types (default: clean; [] = all)",
    )
    args = ap.parse_args()

    if args.candidate not in REGISTRY:
        print(f"Unknown candidate {args.candidate!r}. Known: {sorted(REGISTRY)}")
        sys.exit(1)

    rows = run_beam_sweep(
        manifest_path=args.manifest,
        out_dir=args.out,
        candidate_id=args.candidate,
        snr_filter=args.snrs,
        noise_filter=args.noise_types,
        max_items=args.max_items,
    )

    if not rows:
        sys.exit(1)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "beam_sweep_results.json").write_text(
        json.dumps(
            {
                "candidate": args.candidate,
                "snr_filter": args.snrs,
                "noise_filter": args.noise_types,
                "beam_widths": [asdict(r) for r in rows],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print_table(rows)
    print(f"\nResults saved to {out / 'beam_sweep_results.json'}")


if __name__ == "__main__":
    main()
