"""Phase 1 data prep: build the lean eval set + noise/SNR variants -> manifest.

This module is the Phase 1 runner. It needs network + Hugging Face access, so it
is NOT exercised by the offline smoke (`bench.run --smoke`). Run it explicitly:

    uv run python -m bench.data_prep --out eval_manifest_v1.json

Implemented here: the reusable noise-mixing core (torchaudio.add_noise) and the
manifest emitter. The corpus download (VIVOS / Common Voice / LibriSpeech /
bespoke VI<->EN gold) and noise bank (MUSAN / RIRS_NOISES / DEMAND) are scaffolded
but intentionally minimal -- flesh out per docs/benchmarking-plan.md S3-S4.
"""

from __future__ import annotations

from .schema import EvalItem, RunManifest

SNR_LEVELS = [None, 15.0, 10.0, 5.0, 0.0]  # clean + mild/moderate/hard/severe
NOISE_TYPES = ["steady", "impulsive"]


def mix_noise(clean_wav: str, noise_wav: str, snr_db: float, out_path: str) -> None:
    """Mix `noise_wav` into `clean_wav` at `snr_db` dB and write to `out_path`."""
    import torch
    import torchaudio

    clean, sr = torchaudio.load(clean_wav)
    noise, nsr = torchaudio.load(noise_wav)
    if nsr != sr:
        noise = torchaudio.functional.resample(noise, nsr, sr)
    mixed = torchaudio.functional.add_noise(clean, noise, torch.tensor([snr_db]))
    torchaudio.save(out_path, mixed, sr)


def emit_manifest(items: list[EvalItem], out_path: str) -> None:
    RunManifest(items=items).to_json(out_path)


def build_lean_manifest(out_path: str, workdir: str = "eval_data") -> None:
    """Download lean eval set + noise, generate SNR variants, emit the manifest.

    Phase 1 work: replace the placeholder below with real corpus loading via
    `datasets` and the noise bank from benchmarking-plan.md S3.4, then call
    `mix_noise` across SNR_LEVELS x NOISE_TYPES and `emit_manifest`.
    """
    # TODO(phase-1): load VIVOS / Common Voice-en / LibriSpeech / bespoke VI<->EN gold.
    # TODO(phase-1): stage MUSAN / RIRS_NOISES / DEMAND noise bank.
    raise NotImplementedError(
        "Phase 1 data prep not yet wired -- see docs/benchmarking-plan.md S3-S4. "
        "Use `bench.run --smoke` for an offline harness proof today."
    )


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Kavi bench data prep (Phase 1)")
    ap.add_argument("--out", default="eval_manifest_v1.json")
    ap.add_argument("--workdir", default="eval_data")
    args = ap.parse_args()
    build_lean_manifest(args.out, args.workdir)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
