"""Phase 6 — Denoising gate evaluation.

Runs the lean ASR slice (clean, +5 dB, 0 dB) under three audio conditions:
  - **Raw**       — no preprocessing (baseline)
  - **Wiener**    — ``noisereduce.reduce_noise(prop_decrease=0.5)``
  - **RNNoise**   — ``noisereduce.reduce_noise(stationary=False)``

Computes per-condition WER via jiwer, aggregates by SNR / noise type, then
applies the binary gate logic from ADR-002:

    If denoised WER < raw WER at noisy SNRs → adopt the best denoiser.
    Else → VAD-only pipeline (drop denoising).

Usage:
    uv run python -m bench.eval_denoising \\
        --manifest eval_data/eval_manifest_v1.json \\
        --out bench-results/denoising
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import tempfile
import time
from collections import defaultdict
from pathlib import Path

import noisereduce as nr
import soundfile as sf

from .schema import EvalItem, RunManifest


def _load_audio(path: str, sample_rate: int = 16000):
    """Load a WAV file and return (mono numpy array, sample_rate)."""
    data, sr = sf.read(path, dtype="float32", always_2d=True)
    # data shape: (frames, channels) -> transpose to (channels, frames)
    if data.ndim == 2 and data.shape[1] > 1:
        # downmix multi-channel to mono
        data = data.mean(axis=1, keepdims=True).T
    elif data.ndim == 2:
        data = data.T  # (1, frames)
    # If still 2D with 1 channel, flatten
    if data.ndim == 2 and data.shape[0] == 1:
        data = data[0]  # (frames,)
    return data, sr


def _denoise_wiener(audio, sr):
    """Apply Wiener-style denoising with gentle noise reduction."""
    return nr.reduce_noise(y=audio, sr=sr, prop_decrease=0.5)


def _denoise_rnnoise(audio, sr):
    """Apply RNNoise-style spectral gating (non-stationary, full reduction)."""
    return nr.reduce_noise(y=audio, sr=sr, stationary=False)


DENOISERS = {
    "raw": None,  # no preprocessing
    "wiener": _denoise_wiener,
    "rnnoise": _denoise_rnnoise,
}


_WHISPER_MODEL = None


def _ensure_whisper_model():
    """Lazy-load the faster-whisper Small int8 model (singleton)."""
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        from faster_whisper import WhisperModel

        _WHISPER_MODEL = WhisperModel(
            model_size_or_path="small",
            device="cpu",
            compute_type="int8",
        )
    return _WHISPER_MODEL


def _transcribe(audio_path: str, language: str = "vi") -> str:
    """Transcribe audio with faster-whisper Small int8."""
    model = _ensure_whisper_model()
    segments, _info = model.transcribe(audio_path, language=language)
    text = " ".join(seg.text for seg in segments).strip()
    return text or ""


def _wer(ref: str, hyp: str) -> float | None:
    """Compute WER via jiwer."""
    import jiwer

    try:
        return jiwer.wer(ref, hyp)
    except Exception:  # noqa: BLE001
        return None


def _fmt_pct(val: float | None, width: int = 7) -> str:
    if val is None:
        return " " * width
    return f"{val * 100:6.2f}%"


def run_denoising_eval(
    manifest_path: str,
    out_dir: str,
    snr_levels: list[float] | None = None,
    max_items: int | None = None,
) -> dict:
    """Run the full denoising gate evaluation.

    Parameters
    ----------
    manifest_path:
        Path to ``eval_manifest_v1.json``.
    out_dir:
        Output directory for results.
    snr_levels:
        SNRs to evaluate (default: [5.0, 0.0]).
    max_items:
        Limit number of items per SNR/noise_type combination (for testing).

    Returns
    -------
    dict:
        Aggregated results with per-condition WER and gate decision.
    """
    if snr_levels is None:
        snr_levels = [5.0, 0.0]

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "tmp").mkdir(parents=True, exist_ok=True)

    # ---- Load manifest & filter ASR items ---------------------------------
    manifest = RunManifest.from_json(manifest_path)
    asr_items = [
        it
        for it in manifest.items
        if it.stage == "ASR"
        and it.audio_ref is not None
        and os.path.exists(it.audio_ref)
        and (it.snr is None or it.snr in snr_levels)
    ]
    print(f"Manifest: {len(manifest.items)} total, {len(asr_items)} ASR with audio")

    # Group by (snr, noise_type, language) for structured output
    grouped: dict[tuple, list[EvalItem]] = defaultdict(list)
    for it in asr_items:
        snr = it.snr  # None for clean
        noise = it.noise_type or "clean"
        grouped[(snr, noise, it.language)].append(it)

    print(f"Groups: {len(grouped)}")

    # We evaluate each item under each denoiser.
    # For speed, cache raw transcription results (since raw = same as baseline).
    results: dict[str, dict] = {}  # item_id -> {denoiser -> {...}}

    # ---- Evaluate ---------------------------------------------------------
    total_combos = sum(
        len(items) * len(DENOISERS) for (_snr, _noise, _lang), items in grouped.items()
    )
    processed = 0
    start_wall = time.time()

    for (snr, noise_type, language), items in sorted(
        grouped.items(), key=lambda x: (x[0][0] or -1, x[0][1] or "", x[0][2] or "")
    ):
        if max_items and len(items) > max_items:
            items = items[:max_items]

        for item in items:
            item_results: dict[str, dict] = {}
            assert item.audio_ref is not None  # filtered above
            audio, sr = _load_audio(item.audio_ref)

            for dkey, denoise_fn in DENOISERS.items():
                processed += 1
                if processed % 10 == 0:
                    elapsed = time.time() - start_wall
                    print(
                        f"  [{processed}/{total_combos}] "
                        f"{item.id} / {dkey} "
                        f"({elapsed:.0f}s elapsed)"
                    )

                # Create temp file for denoised audio (raw can use original file)
                if denoise_fn is None:
                    audio_path = item.audio_ref
                else:
                    denoised = denoise_fn(audio.copy(), sr)
                    with tempfile.NamedTemporaryFile(
                        suffix=".wav", delete=False, dir=out / "tmp"
                    ) as tmp:
                        sf.write(tmp.name, denoised, sr)
                        audio_path = tmp.name

                # Transcribe
                try:
                    hyp = _transcribe(audio_path, language=language)
                except Exception as exc:  # noqa: BLE001
                    hyp = ""
                    err = f"{type(exc).__name__}: {exc}"
                else:
                    err = None

                # Clean up temp file
                if denoise_fn is not None and audio_path is not None:
                    with contextlib.suppress(OSError):
                        os.unlink(audio_path)

                # Score WER
                ref = item.reference_text or ""
                w = _wer(ref, hyp) if ref and hyp is not None else None

                item_results[dkey] = {
                    "hypothesis": hyp,
                    "wer": w,
                    "error": err,
                }

            results[item.id] = {
                "item_id": item.id,
                "language": language,
                "snr": snr,
                "noise_type": noise_type,
                "reference": item.reference_text,
                "denoisers": item_results,
            }

    wall_seconds = time.time() - start_wall
    print(f"\nEvaluation finished: {processed} runs in {wall_seconds:.0f}s")

    # ---- Aggregate --------------------------------------------------------
    # Group by (snr, noise_type) -> list of WERs per denoiser
    agg: dict[tuple, dict[str, list[float | None]]] = defaultdict(
        lambda: {d: [] for d in DENOISERS}
    )
    for _rid, r in results.items():
        key = (r["snr"], r["noise_type"])
        for dkey in DENOISERS:
            agg[key][dkey].append(r["denoisers"][dkey]["wer"])

    def _mean_wer(wers: list[float | None]) -> float | None:
        vals = [w for w in wers if w is not None]
        if not vals:
            return None
        return sum(vals) / len(vals)

    agg_summary: dict[str, dict] = {}
    for (snr, noise_type), denoiser_wers in sorted(
        agg.items(), key=lambda x: (x[0][0] or -1, x[0][1] or "")
    ):
        snr_label = "clean" if snr is None else f"SNR {snr:g}"
        key = f"{snr_label}/{noise_type}"
        agg_summary[key] = {
            "snr": snr,
            "noise_type": noise_type,
            "count": len(next(iter(denoiser_wers.values()))),
        }
        for dkey in DENOISERS:
            agg_summary[key][f"wer_{dkey}"] = _mean_wer(denoiser_wers[dkey])

    # ---- Print table ------------------------------------------------------
    print("\n" + "=" * 80)
    print("  PHASE 6 — DENOISING GATE EVALUATION")
    print("=" * 80)

    # Header
    header = f"{'Condition':<22} {'Items':>6} {'Raw':>9} {'Wiener':>9} {'RNNoise':>9}"
    print(header)
    print("-" * len(header))

    rows: list[dict] = []
    for key, row in agg_summary.items():
        print(
            f"{key:<22} {row['count']:>6} "
            f"{_fmt_pct(row['wer_raw']):>9} "
            f"{_fmt_pct(row['wer_wiener']):>9} "
            f"{_fmt_pct(row['wer_rnnoise']):>9}"
        )
        rows.append(row)

    print("-" * len(header))

    # Weighted average across noisy conditions only (exclude clean)
    noisy_wer: dict[str, list[tuple[float, int]]] = {d: [] for d in DENOISERS}
    for _key, row in agg_summary.items():
        if row["snr"] is None:
            continue  # skip clean for gate logic
        for dkey in DENOISERS:
            w = row[f"wer_{dkey}"]
            if w is not None:
                noisy_wer[dkey].append((w, row["count"]))

    def _weighted_mean(items: list[tuple[float, int]]) -> float | None:
        if not items:
            return None
        total_w = sum(v * c for v, c in items)
        total_c = sum(c for _, c in items)
        return total_w / total_c if total_c > 0 else None

    print()
    print("Noisy-conditions weighted-average WER (SNR 5 + SNR 0, both noise types):")
    for dkey in DENOISERS:
        w = _weighted_mean(noisy_wer[dkey])
        if w is not None:
            print(f"  {dkey:8s}: {_fmt_pct(w)}")

    # ---- Binary gate ------------------------------------------------------
    raw_noisy_w = _weighted_mean(noisy_wer["raw"])
    wiener_noisy_w = _weighted_mean(noisy_wer["wiener"])
    rnnoise_noisy_w = _weighted_mean(noisy_wer["rnnoise"])

    print("\n" + "─" * 40)
    print("  BINARY GATE DECISION")
    print("─" * 40)

    if raw_noisy_w is None:
        gate_decision = "INCONCLUSIVE: no noisy WER data"
        adopt_denoiser = None
        prop_decrease_value = None
    else:
        best_denoiser = None
        best_wer = raw_noisy_w
        best_prop_decrease = None

        if wiener_noisy_w is not None and wiener_noisy_w < best_wer:
            best_denoiser = "wiener"
            best_wer = wiener_noisy_w
            best_prop_decrease = 0.5

        if rnnoise_noisy_w is not None and rnnoise_noisy_w < best_wer:
            best_denoiser = "rnnoise"
            best_wer = rnnoise_noisy_w
            best_prop_decrease = None  # RNNoise has no prop_decrease

        if best_denoiser is not None:
            gate_decision = (
                f"ADOPT denoiser: {best_denoiser} "
                f"(noisy WER {_fmt_pct(best_wer).strip()} vs raw {_fmt_pct(raw_noisy_w).strip()})"
            )
            adopt_denoiser = best_denoiser
            prop_decrease_value = best_prop_decrease
        else:
            gate_decision = (
                f"REJECT denoising: VAD-only pipeline "
                f"(raw noisy WER {_fmt_pct(raw_noisy_w).strip()} beats or ties all denoisers)"
            )
            adopt_denoiser = None
            prop_decrease_value = None

    print(f"  {gate_decision}")
    if adopt_denoiser and adopt_denoiser == "wiener":
        print(f"  Recommended prop_decrease = {prop_decrease_value}")
    print("─" * 40)

    # ---- Save results -----------------------------------------------------
    report = {
        "gate_decision": gate_decision,
        "adopt_denoiser": adopt_denoiser,
        "prop_decrease": prop_decrease_value,
        "raw_noisy_wer": raw_noisy_w,
        "wiener_noisy_wer": wiener_noisy_w,
        "rnnoise_noisy_wer": rnnoise_noisy_w,
        "per_condition": agg_summary,
        "total_runs": processed,
        "wall_seconds": wall_seconds,
    }

    (out / "denoising_results.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"\nResults saved to {out / 'denoising_results.json'}")

    return report


def main() -> None:
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description="Phase 6 — Denoising gate evaluation")
    ap.add_argument("--manifest", default="eval_data/eval_manifest_v1.json")
    ap.add_argument("--out", default="bench-results/denoising")
    ap.add_argument("--snr", type=float, nargs="*", default=[5.0, 0.0])
    ap.add_argument("--max-items", type=int, default=None, help="limit per group")
    args = ap.parse_args()

    run_denoising_eval(
        manifest_path=args.manifest,
        out_dir=args.out,
        snr_levels=args.snr,
        max_items=args.max_items,
    )


if __name__ == "__main__":
    main()
