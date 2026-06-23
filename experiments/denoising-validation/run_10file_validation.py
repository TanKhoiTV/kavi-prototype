#!/usr/bin/env python3
"""
10-file denoising validation — Phase 1 of denoising impact analysis.

Validates whether DeepFilterNet and RNNoise degrade WER vs raw noisy audio
on Vietnamese speech (VIVOS) at SNR 5dB with ESC-50 industrial noise,
using Whisper Small int8 on CPU (our pipeline's actual ASR model).

Advisor finding (2026-06-23):
  SNR 5dB with industrial noise is a valid edge case but not the decision
  point for our pipeline. The counterintuitive Cuong result (both denoisers
  hurt vs raw noisy) needs validation on our pipeline first.

Usage:
  uv run python run_10file_validation.py [--vivos-dir DATA_DIR] [--noise NOISE_WAV]

Requires:
  - VIVOS test set downloaded: kaggle datasets download kynthesis/...
  - ESC-50 dataset downloaded for noise samples
  - pip: faster-whisper, noisereduce, deepfilternet, soundfile, numpy, jiwer

Author: Scaffold by Worker — implementation via SpotMe
"""

from pathlib import Path

import numpy as np
import soundfile as sf

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SR: int = 16000
"""Target sample rate for all processing."""

SNR_DB: float = 5.0
"""Signal-to-noise ratio in dB for noise mixing."""

SEED: int = 42
"""Random seed for reproducibility."""

# 10 VIVOS file IDs sampled randomly from the test set (seed=42)
VIVOS_IDS: list[str] = [
    "VIVOSDEV02_R106",
    "VIVOSDEV02_R122",
    "VIVOSDEV02_R130",
    "VIVOSDEV02_R132",
    "VIVOSDEV02_R135",
    "VIVOSDEV02_R137",
    "VIVOSDEV02_R149",
    "VIVOSDEV02_R154",
    "VIVOSDEV02_R015",
    "VIVOSDEV02_R164",
]

# Default directory paths — override via CLI args
DEFAULT_VIVOS_DIR = Path("data/vivos")
DEFAULT_NOISE_WAV = Path(
    "experiments/denoising-validation/noise_samples/industrial_mix.wav"
)
OUTPUT_DIR = Path("experiments/denoising-validation/results")


# ---------------------------------------------------------------------------
# TODO: Implement each function below (SpotMe self-implementation)
# ---------------------------------------------------------------------------


def load_reference_transcripts(vivos_dir: Path) -> dict[str, str]:
    """Read VIVOS prompts.txt and return {file_id: transcript} for our 10 IDs.

    The prompts.txt file lives at <vivos_dir>/test/prompts.txt, with each line:
      <file_id> <transcript text>

    Args:
        vivos_dir: Path to VIVOS dataset root.

    Returns:
        Dict mapping file_id (str) to reference transcript (str).
        Only includes IDs present in VIVOS_IDS.

    Raises:
        NotImplementedError: Scaffold — implement in SpotMe.
        FileNotFoundError: If prompts.txt is missing.
    """
    raise NotImplementedError("SpotMe: implement load_reference_transcripts()")


def load_audio(file_id: str, vivos_dir: Path) -> np.ndarray:
    """Load a VIVOS WAV file and return mono float32 array at 16kHz.

    Files are at: <vivos_dir>/test/waves/<speaker>/<file_id>.wav
    Speaker is the first 10 characters of file_id (VIVOS convention).

    Args:
        file_id: VIVOS utterance ID (e.g. "VIVOSDEV02_R106").
        vivos_dir: Path to VIVOS dataset root.

    Returns:
        1D float32 array, values in [-1.0, 1.0].

    Raises:
        NotImplementedError: Scaffold — implement in SpotMe.
        FileNotFoundError: If the WAV file is missing.
    """
    raise NotImplementedError("SpotMe: implement load_audio()")


def load_noise(noise_path: Path) -> np.ndarray:
    """Load and return noise audio as mono float32 at 16kHz.

    Args:
        noise_path: Path to noise WAV file.

    Returns:
        1D float32 noise array.

    Raises:
        NotImplementedError: Scaffold — implement in SpotMe.
    """
    raise NotImplementedError("SpotMe: implement load_noise()")


def mix_noise(
    audio: np.ndarray, noise: np.ndarray, snr_db: float, sr: int
) -> np.ndarray:
    """Mix audio with noise at a target SNR, normalizing to prevent clipping.

    SNR definition: SNR = 10 * log10(P_signal / P_noise).

    If noise is shorter than audio, tile it. If longer, take a random segment.
    Scale noise so that its power after mixing achieves the target SNR.

    Args:
        audio: Clean speech array (1D float32).
        noise: Noise array (1D float32).
        snr_db: Target SNR in decibels.
        sr: Sample rate (for potential resampling).

    Returns:
        Mixed audio array (1D float32, same length as input audio).

    Raises:
        NotImplementedError: Scaffold — implement in SpotMe.
    """
    import random
    raise NotImplementedError("SpotMe: implement mix_noise()")


def apply_rnnoise(audio: np.ndarray, sr: int) -> np.ndarray:
    """Apply RNNoise via noisereduce with stationary=False.

    stationary=False is critical — ESC-50 industrial noise (engine, chainsaw,
    etc.) is non-stationary. Cuong\'s original experiment used stationary=True
    (Issue #2), which is incorrect for this noise type.

    Args:
        audio: Noisy speech array (1D float32).
        sr: Sample rate.

    Returns:
        Denoised array (1D float32).

    Raises:
        NotImplementedError: Scaffold — implement in SpotMe.
    """
    raise NotImplementedError("SpotMe: implement apply_rnnoise()")


def apply_deepfilternet(audio: np.ndarray, sr: int) -> np.ndarray:
    """Apply DeepFilterNet via df.enhance pipeline.

    DeepFilterNet operates at 48kHz internally — resample to 48k, enhance,
    then resample back to original sr.

    Note: First run triggers model download (~50MB).

    Args:
        audio: Noisy speech array (1D float32).
        sr: Sample rate.

    Returns:
        Denoised array (1D float32 at original sr).

    Raises:
        NotImplementedError: Scaffold — implement in SpotMe.
    """
    raise NotImplementedError("SpotMe: implement apply_deepfilternet()")


def load_whisper_model():
    """Load and return a faster-whisper WhisperModel (Small, int8, CPU).

    The model is cached after first load (~1.5GB RAM). Use a module-level
    cache to avoid reloading per file.

    Returns:
        WhisperModel instance.

    Raises:
        NotImplementedError: Scaffold — implement in SpotMe.
    """
    raise NotImplementedError("SpotMe: implement load_whisper_model()")


def transcribe(audio_path: Path, model) -> str:
    """Transcribe audio using Whisper Small int8 with language=vi.

    Args:
        audio_path: Path to WAV file to transcribe.
        model: Loaded WhisperModel instance.

    Returns:
        Transcribed text string.

    Raises:
        NotImplementedError: Scaffold — implement in SpotMe.
    """
    raise NotImplementedError("SpotMe: implement transcribe()")


def compute_wer(reference: str, hypothesis: str) -> float:
    """Compute Word Error Rate using jiwer.

    Normalization: lowercase, strip punctuation, collapse whitespace.
    WER = (substitutions + insertions + deletions) / reference_length.

    Args:
        reference: Ground-truth transcript.
        hypothesis: ASR hypothesis.

    Returns:
        WER as a float in [0.0, 1.0].

    Raises:
        NotImplementedError: Scaffold — implement in SpotMe.
    """
    raise NotImplementedError("SpotMe: implement compute_wer()")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def main(vivos_dir: Path, noise_path: Path) -> None:
    """Run the 10-file denoising validation.

    For each of the 10 VIVOS files:
      1. Load clean audio + reference transcript
      2. Mix noise at SNR_DB dB -> "raw_noisy"
      3. Apply RNNoise (stationary=False) -> "rnnoise"
      4. Apply DeepFilterNet -> "dfn"
      5. Transcribe all 4 conditions with Whisper Small int8
      6. Compute WER against reference
      7. Print row in results table

    Saves results JSON to OUTPUT_DIR / "10file_results.json".

    Args:
        vivos_dir: Path to VIVOS dataset root.
        noise_path: Path to noise WAV file.
    """
    import json
    raise NotImplementedError("SpotMe: implement main()")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate denoising WER impact on 10 VIVOS utterances"
    )
    parser.add_argument(
        "--vivos-dir",
        type=Path,
        default=DEFAULT_VIVOS_DIR,
        help=f"VIVOS dataset root (default: {DEFAULT_VIVOS_DIR})",
    )
    parser.add_argument(
        "--noise",
        type=Path,
        default=DEFAULT_NOISE_WAV,
        help=f"Noise WAV file (default: {DEFAULT_NOISE_WAV})",
    )

    args = parser.parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    main(args.vivos_dir, args.noise)
