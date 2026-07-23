#!/usr/bin/env python3
"""Generate calibration input lists for QNN conversion from FLEURS manifest data.

Produces two input list files consumed by ``qnn-onnx-converter --input_list``:

* ``whisper_input_list.txt``  — paths to FP32 mel spectrogram binaries
  (shape ``[1, 80, 3000]``) for Whisper-Small encoder calibration.
* ``opusmt_input_list.txt``   — paths to int32 token-ID sequences
  (shape ``[1, 128]``) for Opus-MT encoder calibration.

Calibration data is drawn from real items in ``eval_data/eval_manifest_v1.json``,
falling back to the previously converted single-sample file when available.

Usage::

    uv run python -m bench.qnn.generate_calibration_lists \\
        --manifest eval_data/eval_manifest_v1.json \\
        --out-dir models/qnn/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import numpy as np

# ═══════════════════════════════════════════════════════════════════════
# Whisper mel-spectrogram helpers  (matches openai/whisper exactly)
# ═══════════════════════════════════════════════════════════════════════

WHISPER_SAMPLE_RATE = 16000
WHISPER_N_FFT = 400
WHISPER_HOP_LENGTH = 160
WHISPER_N_MELS = 80
WHISPER_F_MIN = 0.0
WHISPER_F_MAX = 8000.0
WHISPER_N_SAMPLES = 30 * WHISPER_SAMPLE_RATE  # 480 000


def _load_audio_mono(path: str, target_sr: int = WHISPER_SAMPLE_RATE) -> np.ndarray:
    """Load audio as mono float32 numpy array at *target_sr*.

    Uses ``scipy.io.wavfile`` for WAV files which avoids the torchcodec
    dependency.  Falls back to ``torchaudio`` for non-WAV formats.
    """
    import scipy.io.wavfile  # pyright: ignore[reportMissingImports]

    try:
        orig_sr, data = scipy.io.wavfile.read(path)
    except Exception:
        # Fallback to torchaudio for non-WAV formats
        import torchaudio  # pyright: ignore[reportMissingImports]

        try:
            waveform, orig_sr = torchaudio.load(path)
        except Exception as exc:
            raise RuntimeError(f"Failed to load {path}: {exc}") from exc
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        if orig_sr != target_sr:
            resampler = torchaudio.transforms.Resample(orig_sr, target_sr)
            waveform = resampler(waveform)
        return waveform.squeeze(0).numpy().astype(np.float32)

    # Convert to mono float32 [-1, 1]
    if data.ndim > 1:
        data = data.mean(axis=1)
    dtype = data.dtype
    if dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    elif dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0
    elif dtype == np.uint8:
        data = (data.astype(np.float32) - 128.0) / 128.0
    else:
        data = data.astype(np.float32)

    # Resample with scipy if needed
    if orig_sr != target_sr:
        import scipy.signal  # pyright: ignore[reportMissingImports]

        ratio = target_sr / orig_sr
        new_len = int(len(data) * ratio)
        data = scipy.signal.resample(data, new_len).astype(np.float32)

    return data


def _mel_spectrogram(audio: np.ndarray) -> np.ndarray:
    """Compute Whisper-compatible log-mel spectrogram (80-band, 3000 frames).

    Implementation mirrors ``whisper.log_mel_spectrogram`` using
    ``scipy.signal.stft`` so it runs without PyTorch.
    """
    import scipy.signal  # pyright: ignore[reportMissingImports]

    window = np.hanning(WHISPER_N_FFT).astype(np.float32)
    _, _, stft = scipy.signal.stft(
        audio,
        fs=WHISPER_SAMPLE_RATE,
        window=window,
        nperseg=WHISPER_N_FFT,
        noverlap=WHISPER_N_FFT - WHISPER_HOP_LENGTH,
        nfft=WHISPER_N_FFT,
        boundary=None,  # no zero-padding (matches whisper center=False)
        padded=False,
    )  # stft shape: (201, T), complex

    # Power spectrogram
    powers = np.abs(stft) ** 2  # shape: (201, T)

    # Mel filterbank (80 bands, 0-8000 Hz, 201 FFT bins)
    mel_filters = _mel_filterbank(
        sr=WHISPER_SAMPLE_RATE,
        n_fft=WHISPER_N_FFT,
        n_mels=WHISPER_N_MELS,
        f_min=WHISPER_F_MIN,
        f_max=WHISPER_F_MAX,
    )  # shape: (80, 201)

    mel_spec = mel_filters @ powers.numpy()  # shape: (80, T)

    # Log
    log_spec = np.log10(np.clip(mel_spec, a_min=1e-10, a_max=None))

    # Normalize: subtract mean, divide by std (over time dim)
    mean = log_spec.mean(axis=-1, keepdims=True)
    std = log_spec.std(axis=-1, keepdims=True) + 1e-10
    log_spec = (log_spec - mean) / std

    # Pad or trim to 3000 frames
    n_frames = log_spec.shape[-1]
    target_frames = WHISPER_N_SAMPLES // WHISPER_HOP_LENGTH
    if n_frames < target_frames:
        pad_width = ((0, 0), (0, target_frames - n_frames))
        log_spec = np.pad(log_spec, pad_width, mode="constant")
    elif n_frames > target_frames:
        log_spec = log_spec[:, :target_frames]

    # Add batch dim
    return log_spec[np.newaxis, ...].astype(np.float32)  # (1, 80, 3000)


def _mel_filterbank(
    sr: int, n_fft: int, n_mels: int, f_min: float, f_max: float
) -> np.ndarray:
    """Build mel filterbank matrix of shape ``(n_mels, n_freq)``.

    This reproduces the mel filterbank used by ``openai-whisper`` (librosa-style
    Slaney mel).  ``n_freq = n_fft // 2 + 1``.
    """
    n_freq = n_fft // 2 + 1
    weights = np.zeros((n_mels, n_freq), dtype=np.float32)

    # Mel scale
    def _hz_to_mel(f: np.ndarray | float) -> np.ndarray | float:
        return 2595.0 * np.log10(1.0 + np.asarray(f) / 700.0)

    def _mel_to_hz(m: np.ndarray | float) -> np.ndarray | float:
        return 700.0 * (10.0 ** (np.asarray(m) / 2595.0) - 1.0)

    mel_min = _hz_to_mel(f_min)
    mel_max = _hz_to_mel(f_max)
    mel_points = np.linspace(mel_min, mel_max, n_mels + 2)
    hz_points = _mel_to_hz(mel_points)

    # FFT bin centres
    fft_bins = np.linspace(0, sr / 2.0, n_freq)

    for i in range(n_mels):
        left = float(hz_points[i])
        center = float(hz_points[i + 1])
        right = float(hz_points[i + 2])

        # Rising ramp
        idx_l = np.logical_and(fft_bins >= left, fft_bins <= center)
        weights[i, idx_l] = (fft_bins[idx_l] - left) / (center - left)

        # Falling ramp
        idx_r = np.logical_and(fft_bins >= center, fft_bins <= right)
        weights[i, idx_r] = (right - fft_bins[idx_r]) / (right - center)

    return weights


# ═══════════════════════════════════════════════════════════════════════
# Opus-MT tokenization
# ═══════════════════════════════════════════════════════════════════════


def _tokenize_opusmt(
    texts: list[str],
    tokenizer_path: str,
    max_length: int = 128,
) -> np.ndarray:
    """Tokenize a list of source texts into int32 arrays ``[1, max_length]``.

    Returns the token IDs for the *first* text.  (Single-sample calibration
    is sufficient for activation range estimation.)
    """
    from transformers import AutoTokenizer  # pyright: ignore[reportMissingImports]

    tok = AutoTokenizer.from_pretrained(tokenizer_path)
    enc = tok(
        texts[:1],
        padding="max_length",
        truncation=True,
        max_length=max_length,
        return_tensors="np",
    )
    return enc["input_ids"].astype(np.int32)  # (1, max_length)


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

WHISPER_ASR_LANGS = {"vi", "en"}
OPUSMT_SRC_LANG = "vi"  # vi->en direction; the manifest direction is vi->en


def _gather_asr_items(
    manifest: dict[str, Any], max_samples: int = 50
) -> list[dict[str, Any]]:
    """Pick clean ASR items from the manifest, balanced across languages."""
    items = manifest.get("items", [])
    clean = [
        i for i in items if i.get("stage") == "ASR" and i.get("noise_type") == "clean"
    ]
    # Return up to max_samples, preferring language balance
    by_lang: dict[str, list[dict[str, Any]]] = {}
    for item in clean:
        lang = item.get("language", "unknown")
        by_lang.setdefault(lang, []).append(item)

    selected: list[dict[str, Any]] = []
    per_lang = max_samples // max(len(by_lang), 1)
    for lang in sorted(by_lang):
        selected.extend(by_lang[lang][:per_lang])

    # If we still have room, top up from the largest language bucket
    if len(selected) < max_samples:
        remaining = [
            i
            for lang_items in by_lang.values()
            for i in lang_items
            if i not in selected
        ]
        selected.extend(remaining[: max_samples - len(selected)])

    return selected[:max_samples]


def _gather_mt_items(
    manifest: dict[str, Any], max_samples: int = 32
) -> list[dict[str, Any]]:
    """Pick MT items for calibration."""
    items = manifest.get("items", [])
    mt = [i for i in items if i.get("stage") == "MT" and i.get("direction") == "vi->en"]
    return mt[:max_samples]


def _ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def generate_whisper_list(
    manifest: dict[str, Any],
    out_dir: str,
    manifest_base: str | None = None,
    max_samples: int = 50,
) -> str:
    """Generate ``whisper_input_list.txt``.

    Returns the path to the created list file.
    """
    items = _gather_asr_items(manifest, max_samples=max_samples)

    calib_dir = _ensure_dir(os.path.join(out_dir, "whisper-calib"))
    list_lines: list[str] = []

    for idx, item in enumerate(items):
        audio_path = item.get("audio_ref")
        if not audio_path or not os.path.exists(audio_path):
            # Resolve relative to manifest dir
            if manifest_base and audio_path:
                resolved = os.path.join(manifest_base, audio_path)
                if os.path.exists(resolved):
                    audio_path = resolved
                else:
                    continue
            else:
                continue

        bin_path = os.path.join(calib_dir, f"whisper_calib_{idx:04d}.bin")

        try:
            audio = _load_audio_mono(audio_path)
            # Pad / trim to 30 s
            if len(audio) < WHISPER_N_SAMPLES:
                audio = np.pad(audio, (0, WHISPER_N_SAMPLES - len(audio)))
            else:
                audio = audio[:WHISPER_N_SAMPLES]
            mel = _mel_spectrogram(audio)
            mel.tofile(bin_path)
            list_lines.append(f"{os.path.relpath(bin_path, out_dir)} input_features")
        except Exception as exc:
            print(f"  [skip] {item.get('id', '?')}: {exc}", file=sys.stderr)
            continue

    # Fallback: if no samples were generated, use the existing single-sample file
    if not list_lines:
        existing = os.path.join(out_dir, "whisper-small", "input_features.bin")
        if os.path.exists(existing):
            rel = os.path.relpath(existing, out_dir)
            list_lines.append(f"{rel} input_features")
            print(
                "  [fallback] using existing input_features.bin (single sample)",
                file=sys.stderr,
            )

    list_path = os.path.join(out_dir, "whisper_input_list.txt")
    with open(list_path, "w") as f:
        f.write("\n".join(list_lines) + "\n")

    print(f"Wrote {len(list_lines)} lines to {list_path}")
    return list_path


def generate_opusmt_list(
    manifest: dict[str, Any],
    out_dir: str,
    max_samples: int = 32,
) -> str:
    """Generate ``opusmt_input_list.txt``.

    Returns the path to the created list file.
    """
    items = _gather_mt_items(manifest, max_samples=max_samples)

    calib_dir = _ensure_dir(os.path.join(out_dir, "opusmt-calib"))
    list_lines: list[str] = []

    # Use the local tokenizer if available, otherwise download
    local_tokenizer = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "models",
        "opus-mt-vi-en-src",
    )
    tokenizer_path = (
        local_tokenizer
        if os.path.exists(local_tokenizer)
        else "Helsinki-NLP/opus-mt-vi-en"
    )

    for idx, item in enumerate(items):
        source_text = item.get("input_text")
        if not source_text or not source_text.strip():
            continue

        bin_path = os.path.join(calib_dir, f"opusmt_calib_{idx:04d}.bin")

        try:
            ids = _tokenize_opusmt([source_text], tokenizer_path)
            ids.tofile(bin_path)
            list_lines.append(f"{os.path.relpath(bin_path, out_dir)} input_ids")
        except Exception as exc:
            print(f"  [skip] {item.get('id', '?')}: {exc}", file=sys.stderr)
            continue

    # Require real calibration data (PR #73 review: random tokens degrade quantization)
    if not list_lines:
        raise ValueError(
            "No valid MT items found for calibration. "
            "Cannot proceed with synthetic tokens as they degrade w8a16 quantization. "
            "Ensure eval_manifest_v1.json contains MT items or provide FLEURS data."
        )

    list_path = os.path.join(out_dir, "opusmt_input_list.txt")
    with open(list_path, "w") as f:
        f.write("\n".join(list_lines) + "\n")

    print(f"Wrote {len(list_lines)} lines to {list_path}")
    return list_path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate QNN calibration input lists from FLEURS manifest data",
    )
    parser.add_argument(
        "--manifest",
        default="eval_data/eval_manifest_v1.json",
        help="Path to eval manifest JSON (default: %(default)s)",
    )
    parser.add_argument(
        "--out-dir",
        default="models/qnn",
        help="Output directory for list files and calibration binaries (default: %(default)s)",
    )
    parser.add_argument(
        "--max-whisper-samples",
        type=int,
        default=50,
        help="Max Whisper calibration samples (default: %(default)s)",
    )
    parser.add_argument(
        "--max-opusmt-samples",
        type=int,
        default=32,
        help="Max Opus-MT calibration samples (default: %(default)s)",
    )
    parser.add_argument(
        "--whisper-only",
        action="store_true",
        help="Only generate Whisper calibration list",
    )
    parser.add_argument(
        "--opusmt-only",
        action="store_true",
        help="Only generate Opus-MT calibration list",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    manifest_path = args.manifest
    if not os.path.exists(manifest_path):
        print(f"Error: manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)

    with open(manifest_path) as f:
        manifest = json.load(f)

    manifest_base = os.path.dirname(os.path.abspath(manifest_path))
    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)

    do_whisper = not args.opusmt_only
    do_opusmt = not args.whisper_only

    if do_whisper:
        print("Generating Whisper calibration list...")
        wlist = generate_whisper_list(
            manifest,
            out_dir,
            manifest_base=manifest_base,
            max_samples=args.max_whisper_samples,
        )
        with open(wlist) as f:
            print(f"  {len(f.readlines())} entries")

    if do_opusmt:
        print("Generating Opus-MT calibration list...")
        olist = generate_opusmt_list(
            manifest,
            out_dir,
            max_samples=args.max_opusmt_samples,
        )
        with open(olist) as f:
            print(f"  {len(f.readlines())} entries")

    print("Done.")


if __name__ == "__main__":
    main()
