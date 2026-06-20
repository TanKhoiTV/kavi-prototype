#!/usr/bin/env python3
"""
Evaluation harness for the ASR→MT→TTS pipeline.

Measures WER (ASR accuracy) and chrF (translation quality) against
reference transcripts stored in refs/<audio_stem>.txt.

Reference format (two lines):
    <Vietnamese ground-truth transcript>
    <English ground-truth translation>

Usage:
    uv run python eval.py greeting_vi.wav
    uv run python eval.py greeting_vi.wav --asr-model small --json

Batch mode:
    uv run python eval.py --batch refs/
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

import jiwer
import sacrebleu

from pipeline import run_pipeline


def load_ref(ref_path: str) -> dict:
    """Load reference transcript from a two-line file.

    Line 1: Vietnamese ground-truth transcript
    Line 2: English ground-truth translation
    """
    path = Path(ref_path)
    if not path.exists():
        raise FileNotFoundError(f"Reference file not found: {ref_path}")

    lines = [l.strip() for l in path.read_text().strip().splitlines()
             if l.strip() and not l.startswith("#")]
    if len(lines) < 2:
        raise ValueError(
            f"Reference file {ref_path} must have at least 2 lines "
            f"(Vietnamese + English), got {len(lines)}"
        )
    return {"vi": lines[0], "en": lines[1]}


def ref_path_for_audio(audio_path: str, ref_dir: str = "refs") -> str:
    """Derive reference file path from audio file path."""
    stem = Path(audio_path).stem
    candidate = Path(ref_dir) / f"{stem}.txt"
    if candidate.exists():
        return str(candidate)
    # Also check alongside the audio file
    candidate2 = Path(audio_path).with_suffix(".txt")
    if candidate2.exists():
        return str(candidate2)
    return str(candidate)


def compute_wer(reference: str, hypothesis: str) -> dict:
    """Compute WER and related metrics."""
    measures = jiwer.process_words(reference, hypothesis)
    return {
        "wer": round(measures.wer, 4),
        "hits": measures.hits,
        "substitutions": measures.substitutions,
        "deletions": measures.deletions,
        "insertions": measures.insertions,
    }


def compute_chrf(reference: str, hypothesis: str) -> dict:
    """Compute chrF score."""
    result = sacrebleu.sentence_chrf(hypothesis, [reference])
    return {"chrf": round(result.score, 2)}


def evaluate_file(audio_path: str, ref_path: str | None = None,
                  asr_model: str = "small", ref_dir: str = "refs",
                  quiet: bool = True) -> dict:
    """Run pipeline on one audio file and compute evaluation metrics.

    Returns a dict with pipeline results and metrics.
    """
    # Resolve reference
    if ref_path is None:
        ref_path = ref_path_for_audio(audio_path, ref_dir)

    ref = load_ref(ref_path) if Path(ref_path).exists() else None

    # Run pipeline with quiet=True and temp output dir
    with tempfile.TemporaryDirectory(prefix="eval_") as tmpdir:
        result = run_pipeline(
            audio_path=audio_path,
            asr_model_size=asr_model,
            output_dir=tmpdir,
            quiet=quiet,
        )

    # Compute metrics if reference available
    metrics = {}
    if ref:
        # ASR metrics (Vietnamese)
        asr_wer = compute_wer(ref["vi"], result["asr"]["text"])
        metrics["asr"] = asr_wer

        # MT metrics (English)
        mt_chrf = compute_chrf(ref["en"], result["mt"]["translation"])
        metrics["mt"] = {
            "chrf": mt_chrf["chrf"],
            "hypothesis": result["mt"]["translation"],
            "reference": ref["en"],
        }

    return {
        "audio": audio_path,
        "reference": ref,
        "asr_result": result["asr"],
        "mt_result": result["mt"],
        "tts_result": result["tts"],
        "total_s": result["total_s"],
        "metrics": metrics,
    }


def print_report(results: list[dict], json_output: bool = False):
    """Print evaluation report."""
    if json_output:
        # Strip non-serialisable fields
        clean = []
        for r in results:
            cr = {
                "audio": r["audio"],
                "asr": {
                    "text": r["asr_result"]["text"],
                    "elapsed_s": r["asr_result"]["elapsed_s"],
                },
                "mt": {
                    "translation": r["mt_result"]["translation"],
                    "elapsed_s": r["mt_result"]["elapsed_s"],
                },
                "total_s": r["total_s"],
                "metrics": r["metrics"],
            }
            clean.append(cr)
        print(json.dumps(clean, indent=2, ensure_ascii=False))
        return

    # Table header
    sep = "─" * 78
    print(f"\n{sep}")
    print("  EVALUATION REPORT")
    print(sep)

    for r in results:
        print(f"\n  File:        {r['audio']}")
        print(f"  ─{'─' * 65}")

        # ASR
        asr = r["asr_result"]
        print(f"  ASR text:    {asr['text']}")
        if r.get("reference"):
            print(f"  Reference:   {r['reference']['vi']}")
        if r["metrics"].get("asr"):
            m = r["metrics"]["asr"]
            print(f"  WER:         {m['wer']*100:.1f}%  "
                  f"(H={m['hits']} S={m['substitutions']} "
                  f"D={m['deletions']} I={m['insertions']})")
        print(f"  ASR time:    {asr['elapsed_s']}s")

        # MT
        mt = r["mt_result"]
        print(f"  MT output:   {mt['translation']}")
        if r["metrics"].get("mt"):
            m = r["metrics"]["mt"]
            print(f"  chrF:        {m['chrf']}")
            print(f"  Reference:   {m['reference']}")
        print(f"  MT time:     {mt['elapsed_s']}s")

        # TTS
        tts = r["tts_result"]
        print(f"  TTS output:  {tts['output']}")
        print(f"  TTS time:    {tts['elapsed_s']}s")

        # Total
        print(f"  ─{'─' * 65}")
        print(f"  Total time:  {r['total_s']}s  "
              f"(inference only, cold models)")

    # Summary row for batch
    if len(results) > 1:
        print(f"\n{sep}")
        print("  SUMMARY")
        print(sep)
        avg_total = sum(r["total_s"] for r in results) / len(results)
        avg_asr = sum(r["asr_result"]["elapsed_s"] for r in results) / len(results)
        avg_mt = sum(r["mt_result"]["elapsed_s"] for r in results) / len(results)
        avg_tts = sum(r["tts_result"]["elapsed_s"] for r in results) / len(results)
        print(f"  Files:       {len(results)}")
        print(f"  Avg total:   {avg_total:.2f}s")
        print(f"  Avg ASR:     {avg_asr:.2f}s")
        print(f"  Avg MT:      {avg_mt:.2f}s")
        print(f"  Avg TTS:     {avg_tts:.2f}s")

        if all(r["metrics"].get("asr") for r in results):
            avg_wer = sum(r["metrics"]["asr"]["wer"] for r in results) / len(results)
            print(f"  Avg WER:     {avg_wer*100:.1f}%")

        if all(r["metrics"].get("mt", {}).get("chrf") is not None for r in results):
            avg_chrf = sum(r["metrics"]["mt"]["chrf"] for r in results) / len(results)
            print(f"  Avg chrF:    {avg_chrf:.1f}")

    print(f"\n{sep}\n")


def batch_eval(ref_dir: str = "refs", asr_model: str = "small",
               json_output: bool = False) -> list[dict]:
    """Evaluate all audio files that have matching references."""
    ref_dir = Path(ref_dir)
    if not ref_dir.exists():
        print(f"❌ Reference directory not found: {ref_dir}")
        sys.exit(1)

    ref_files = sorted(ref_dir.glob("*.txt"))
    if not ref_files:
        print(f"❌ No reference files found in {ref_dir}")
        sys.exit(1)

    # Map audio files to reference files
    results = []
    for ref_file in ref_files:
        # Look for corresponding audio file
        for ext in [".wav", ".mp3", ".m4a", ".flac"]:
            audio_candidates = [
                ref_file.with_suffix(ext),
                Path(".") / ref_file.stem + ext,
            ]
            for ac in audio_candidates:
                if Path(ac).exists():
                    audio_path = str(ac)
                    break
            else:
                continue
            break
        else:
            print(f"  ⚠ No audio file found for {ref_file.name}, skipping")
            continue

        print(f"  Evaluating {audio_path} …")
        result = evaluate_file(
            audio_path=audio_path,
            ref_path=str(ref_file),
            asr_model=asr_model,
            quiet=True,
        )
        results.append(result)

    print_report(results, json_output=json_output)
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate ASR→MT→TTS pipeline against reference transcripts")
    parser.add_argument("audio", nargs="?", help="Audio file to evaluate")
    parser.add_argument("--asr-model", default="small",
                        help="Whisper model size [small]")
    parser.add_argument("--ref", help="Reference transcript file "
                        "(default: refs/<audio_stem>.txt)")
    parser.add_argument("--ref-dir", default="refs",
                        help="Reference directory for batch mode [refs]")
    parser.add_argument("--batch", action="store_true",
                        help="Batch evaluate all files in ref-dir")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON instead of table")
    parser.add_argument("--verbose", action="store_true",
                        help="Show pipeline progress output")
    args = parser.parse_args()

    if args.batch:
        batch_eval(
            ref_dir=args.ref_dir,
            asr_model=args.asr_model,
            json_output=args.json,
        )
        return

    if not args.audio:
        parser.print_help()
        sys.exit(1)

    if not Path(args.audio).exists():
        print(f"❌ Audio file not found: {args.audio}")
        sys.exit(1)

    result = evaluate_file(
        audio_path=args.audio,
        ref_path=args.ref,
        asr_model=args.asr_model,
        ref_dir=args.ref_dir,
        quiet=not args.verbose,
    )
    print_report([result], json_output=args.json)


if __name__ == "__main__":
    main()
