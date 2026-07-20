#!/usr/bin/env python3
"""Score captured RTranslator outputs against the eval manifest.

Usage:
    uv run python -m bench.score_rtranslator \
        --manifest eval_data/eval_manifest_v1.json \
        --outputs eval_data/rtranslator/outputs/2026-03-01 \
        [--out bench-results/rtranslator-row.json]

Matches each EvalItem in the manifest against the corresponding RTranslator
output file, runs WER/BLEU/RTF scoring via bench/scorer.py, and prints a
comparison-ready result row.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .candidates.rtranslator import RTranslatorCandidate
from .schema import RunManifest, StageResult
from .scorer import score_item


def _resolve_audio_duration(record: dict) -> float | None:
    """Derive audio duration from the item, preferring input or output audio."""
    item = record.get("item", {})
    result = record.get("result", {})
    stage = item.get("stage", "")

    if stage == "ASR":
        audio_ref = item.get("audio_ref")
        if audio_ref:
            dur = _audio_duration(audio_ref)
            if dur is not None:
                return dur
    elif stage == "TTS":
        out_audio = result.get("output_audio_path")
        if out_audio:
            dur = _audio_duration(out_audio)
            if dur is not None:
                return dur
    return None


def _audio_duration(path: str) -> float | None:
    """Return duration in seconds of a WAV/audio file, or None."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        import soundfile as sf

        with sf.SoundFile(str(p)) as f:
            return f.frames / f.samplerate
    except Exception:  # noqa: BLE001
        return None


def score_rtranslator_outputs(
    manifest: RunManifest,
    outputs_dir: Path,
    **candidate_kwargs,
) -> list[dict]:
    """Score every manifest item against RTranslator output files.

    Parameters
    ----------
    manifest : RunManifest
        The eval manifest containing items to score.
    outputs_dir : Path
        Path to the RTranslator output directory (per test protocol layout).
    **candidate_kwargs
        Extra kwargs forwarded to RTranslatorCandidate __init__ config.

    Returns
    -------
    list[dict]
        A list of records, each containing the original item, the StageResult,
        and the computed Metrics.
    """
    # Build a single candidate instance for the entire run
    config = {"outputs_dir": str(outputs_dir), **candidate_kwargs}
    candidate = RTranslatorCandidate(config=config)

    records: list[dict] = []
    for item in manifest.items:
        try:
            result = candidate.run(item)
        except Exception as exc:  # noqa: BLE001
            result = StageResult(
                candidate_id=candidate.id,
                item_id=item.id,
                stage=item.stage,
                error=f"{type(exc).__name__}: {exc}",
            )

        duration = _resolve_audio_duration(
            {"item": asdict(item), "result": asdict(result)}
        )
        metrics = score_item(item, result, duration)

        records.append(
            {
                "item": asdict(item),
                "result": asdict(result),
                "metrics": asdict(metrics),
            }
        )
    return records


def print_comparison_table(records: list[dict]) -> None:
    """Print a compact comparison table of RTranslator results."""
    headers = [
        "item",
        "stage",
        "lang",
        "dir",
        "lat_s",
        "WER",
        "BLEU",
        "RTF",
        "note",
    ]
    rows = []
    for rec in records:
        it = rec["item"]
        res = rec["result"]
        met = rec["metrics"]

        note = ""
        if res.get("error"):
            note = f"ERR:{res['error'][:40]}"
        elif met.get("notes"):
            note = met["notes"][0][:40]

        rows.append(
            [
                it["id"],
                it["stage"],
                it.get("language", ""),
                it.get("direction", ""),
                f"{res['latency_s']:.2f}" if res.get("latency_s") else "-",
                f"{met['wer']:.3f}" if met.get("wer") is not None else "-",
                f"{met['bleu']:.1f}" if met.get("bleu") is not None else "-",
                f"{met['rtf']:.2f}" if met.get("rtf") is not None else "-",
                note,
            ]
        )

    if not rows:
        print("(no items scored)")
        return

    widths = [
        max(len(str(r[i])) for r in [headers] + rows) for i in range(len(headers))
    ]
    line = "  ".join(str(h).ljust(w) for h, w in zip(headers, widths, strict=True))
    print(line)
    print("-" * len(line))
    for row in rows:
        print("  ".join(str(c).ljust(w) for c, w in zip(row, widths, strict=True)))


def print_summary_row(records: list[dict]) -> None:
    """Print a single aggregated comparison row for the RTranslator baseline."""
    asr_items = [r for r in records if r["item"]["stage"] == "ASR"]
    mt_items = [r for r in records if r["item"]["stage"] == "MT"]

    def avg_wer(items: list[dict]) -> str:
        vals = [
            r["metrics"]["wer"] for r in items if r["metrics"].get("wer") is not None
        ]
        return f"{sum(vals) / len(vals):.3f}" if vals else "-"

    def avg_bleu(items: list[dict]) -> str:
        vals = [
            r["metrics"]["bleu"] for r in items if r["metrics"].get("bleu") is not None
        ]
        return f"{sum(vals) / len(vals):.1f}" if vals else "-"

    row = (
        f"RTranslator-2.1.5  ASR-WER={avg_wer(asr_items)}  "
        f"MT-BLEU={avg_bleu(mt_items)}  "
        f"items={len(records)}"
    )
    print()
    print("=" * len(row))
    print(row)
    print("=" * len(row))


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Score captured RTranslator outputs against eval manifest"
    )
    ap.add_argument(
        "--manifest",
        default="eval_data/eval_manifest_v1.json",
        help="path to eval_manifest_v1.json",
    )
    ap.add_argument(
        "--outputs",
        required=True,
        help="directory containing RTranslator captured outputs",
    )
    ap.add_argument(
        "--out",
        default=None,
        help="path to write JSON results (default: stdout only)",
    )
    ap.add_argument(
        "--summary-only",
        action="store_true",
        help="print only the aggregated summary row",
    )
    args = ap.parse_args()

    manifest_path = Path(args.manifest)
    outputs_dir = Path(args.outputs)

    if not manifest_path.exists():
        ap.error(f"manifest not found: {manifest_path}")
    if not outputs_dir.is_dir():
        ap.error(f"outputs directory not found: {outputs_dir}")

    manifest = RunManifest.from_json(str(manifest_path))
    records = score_rtranslator_outputs(manifest, outputs_dir)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {"candidate_id": "rtranslator-2.1.5", "records": records},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"\nWrote {out_path}")

    if not args.summary_only:
        print_comparison_table(records)

    print_summary_row(records)


if __name__ == "__main__":
    main()
