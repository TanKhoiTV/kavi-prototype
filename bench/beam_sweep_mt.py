"""Beam-width sweep for Opus-MT (CTranslate2) — issue #88.

Iterates beam ∈ {1, 2, 4, 5, 8}, runs all MT items from the manifest,
collects BLEU, per-item latency, and approximate KV-cache RAM overhead,
then prints the comparison table from the issue template.

Usage:
    uv run python -m bench.beam_sweep_mt \
        --manifest eval_data/eval_manifest_v1.json \
        --out bench-results/beam-sweep-mt
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

from .candidates.opusmt_mt import OpusMTMTCandidate
from .schema import RunManifest, StageResult
from .scorer import score_item

BEAM_WIDTHS = [1, 2, 4, 5, 8]


def _current_rss_mb() -> float:
    """Return current RSS in MB (cross-platform)."""
    import psutil

    proc = psutil.Process()
    # rss is always available cross-platform; peak_wset/ru_maxrss are peak-variant
    return proc.memory_info().rss / (1024.0 ** 2)


def _peak_rss_mb() -> float:
    """Return peak RSS since process start in MB."""
    import sys as _sys
    import psutil

    if _sys.platform == "win32":
        return psutil.Process().memory_info().peak_wset / (1024.0 ** 2)
    import resource
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    divisor = 1024.0 ** 2 if _sys.platform == "darwin" else 1024.0
    return rss / divisor


@dataclass
class BeamSweepRow:
    beam_width: int
    mean_bleu: float | None
    total_latency_s: float
    relative_latency: float | None  # normalized to greedy (beam=1)
    kv_cache_mb: float | None        # peak RSS delta over model-baseline
    num_items: int
    errors: int


def run_beam_sweep(
    manifest_path: str,
    out_dir: str,
    max_items: int | None = None,
) -> list[BeamSweepRow]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    manifest = RunManifest.from_json(manifest_path)
    mt_items = [it for it in manifest.items if it.stage == "MT"]
    if max_items:
        mt_items = mt_items[:max_items]

    print(f"Manifest: {len(mt_items)} MT items, beam widths {BEAM_WIDTHS}")
    print()

    rows: list[BeamSweepRow] = []
    baseline_latency: float | None = None
    model_baseline_rss: float | None = None

    for beam in BEAM_WIDTHS:
        print(f"  beam={beam} ...", end=" ", flush=True)

        # Fresh candidate each beam width so model-load RSS is isolated
        cand = OpusMTMTCandidate()
        # Override the beam size (keep other decode kwargs at defaults)
        cand._DECODE_KWARGS = {
            "beam_size": beam,
            "repetition_penalty": 1.1,
            "no_repeat_ngram_size": 3,
            "max_decoding_length": 256,
        }

        # Snapshot RSS after model load (before any inference for this beam)
        if model_baseline_rss is None:
            model_baseline_rss = _current_rss_mb()
        rss_before = _current_rss_mb()

        bleus: list[float] = []
        total_lat = 0.0
        n_errors = 0

        for item in mt_items:
            try:
                t0 = time.perf_counter()
                out_text, _ = cand._infer(item)
                lat = time.perf_counter() - t0

                result = StageResult(
                    candidate_id=f"opus-mt-beam-{beam}",
                    item_id=item.id,
                    stage="MT",
                    output_text=out_text,
                    latency_s=round(lat, 4),
                )
                metrics = score_item(item, result)
                if metrics.bleu is not None:
                    bleus.append(metrics.bleu)
                total_lat += lat
            except Exception as exc:
                n_errors += 1
                print(f"\n    error on {item.id}: {exc}", file=sys.stderr)

        rss_after = _current_rss_mb()
        mean_bleu = sum(bleus) / len(bleus) if bleus else None
        kv_cache = max(0.0, rss_after - rss_before)

        if baseline_latency is None:
            baseline_latency = total_lat
            rel_lat = 1.0
        else:
            rel_lat = total_lat / baseline_latency if baseline_latency > 0 else None

        row = BeamSweepRow(
            beam_width=beam,
            mean_bleu=round(mean_bleu, 2) if mean_bleu is not None else None,
            total_latency_s=round(total_lat, 4),
            relative_latency=round(rel_lat, 4) if rel_lat is not None else None,
            kv_cache_mb=round(kv_cache, 1),
            num_items=len(mt_items) - n_errors,
            errors=n_errors,
        )
        rows.append(row)

        bleu_str = f"{mean_bleu:.2f}" if mean_bleu is not None else "N/A"
        print(f"BLEU={bleu_str}  lat={total_lat:.2f}s  "
              f"rel={rel_lat:.2f}x  KV-cache={kv_cache:.0f}MB")

    return rows


def print_table(rows: list[BeamSweepRow]) -> None:
    """Print the comparison table from issue #88."""

    headers = [
        "Beam width",
        "BLEU",
        "Total latency (s)",
        "Relative latency",
        "KV-cache (MB)",
        "Items",
        "Errors",
    ]
    col_widths = [len(h) for h in headers]

    table_rows = []
    for r in rows:
        bleu_str = f"{r.mean_bleu:.2f}" if r.mean_bleu is not None else "-"
        rel_str = f"{r.relative_latency:.2f}x" if r.relative_latency is not None else "-"
        kv_str = f"{r.kv_cache_mb:.0f}" if r.kv_cache_mb is not None else "-"
        table_rows.append([
            str(r.beam_width),
            bleu_str,
            f"{r.total_latency_s:.2f}",
            rel_str,
            kv_str,
            str(r.num_items),
            str(r.errors),
        ])

    # Update column widths
    for row in [headers] + table_rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    sep = "  "
    rule = "-" * (sum(col_widths) + len(sep) * (len(col_widths) - 1))

    print()
    print("=" * len(rule))
    print("  Beam-width sweep — Opus-MT (CTranslate2, int8, CPU)")
    print("=" * len(rule))
    print()
    print(sep.join(h.ljust(w) for h, w in zip(headers, col_widths)))
    print(rule)
    for row in table_rows:
        print(sep.join(c.ljust(w) for c, w in zip(row, col_widths)))
    print(rule)
    print()

    # Verdict row
    best = max(rows, key=lambda r: r.mean_bleu if r.mean_bleu is not None else 0)
    print(f"Best BLEU: beam={best.beam_width}  ({best.mean_bleu})")
    if rows[0].mean_bleu is not None and best.mean_bleu is not None:
        gain = best.mean_bleu - rows[0].mean_bleu
        print(f"Gain over greedy (beam=1): +{gain:.2f} BLEU")
        print(f"Latency cost: {best.relative_latency:.2f}x vs greedy")

    # Suggest a winner
    print()
    print("Verdict: ", end="")
    if best.beam_width == 1:
        print("Greedy is sufficient — no benefit from beam search")
    elif best.beam_width <= 4:
        print(f"Beam={best.beam_width} — good quality/latency trade-off")
    else:
        print(f"Beam={best.beam_width} — best quality, higher latency cost")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    ap = argparse.ArgumentParser(
        description="Beam-width sweep for Opus-MT (issue #88)"
    )
    ap.add_argument(
        "--manifest",
        default="eval_data/eval_manifest_v1.json",
        help="path to eval_manifest_v1.json",
    )
    ap.add_argument(
        "--out",
        default="bench-results/beam-sweep-mt",
        help="output directory",
    )
    ap.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="limit MT items per beam (for faster iteration)",
    )
    args = ap.parse_args()

    rows = run_beam_sweep(
        manifest_path=args.manifest,
        out_dir=args.out,
        max_items=args.max_items,
    )

    # Save raw results
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "beam_sweep_results.json").write_text(
        json.dumps(
            {
                "candidate": "opus-mt-vi-en-ct2-cpu",
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
