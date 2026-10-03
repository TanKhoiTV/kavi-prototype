"""Minimal noisy-audio pipeline for one Stage 3A case (1 clean + MUSAN + RIRS + 10 dB)."""

from __future__ import annotations

import numpy as np
import soundfile as sf
from scipy import signal

SR = 16000


def load_mono(path: str, sr: int = SR) -> np.ndarray:
    data, fs = sf.read(path, dtype="float32", always_2d=True)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if fs != sr:
        import torch
        from torchaudio import functional

        t = torch.from_numpy(data).unsqueeze(0)
        t = functional.resample(t, fs, sr)
        data = t.squeeze(0).numpy()
    return data


def apply_rir(speech: np.ndarray, rir: np.ndarray) -> np.ndarray:
    out = signal.fftconvolve(speech, rir, mode="full")
    out = out[: len(speech)]
    peak = np.max(np.abs(out))
    if peak > 0.9:
        out = out * (0.9 / peak)
    return out


def align_noise(noise: np.ndarray, target_len: int) -> np.ndarray:
    if len(noise) >= target_len:
        return noise[:target_len]
    repeats = (target_len + len(noise) - 1) // len(noise)
    aligned = np.tile(noise, repeats)
    return aligned[:target_len]


def mix_snr(
    speech: np.ndarray, noise: np.ndarray, snr_db: float
) -> tuple[np.ndarray, float, float, bool]:
    # 1. Align noise before RMS
    aligned_noise = align_noise(noise, len(speech))
    # 2. Compute RMS on aligned components
    s_rms = float(np.sqrt(np.mean(speech**2)))
    n_rms_before = float(np.sqrt(np.mean(aligned_noise**2)))
    if s_rms == 0:
        raise ValueError("Speech RMS is zero")
    # 3. Scale noise to target SNR
    target_noise_rms = s_rms / (10 ** (snr_db / 20.0))
    scale_factor = target_noise_rms / (n_rms_before + 1e-12)
    scaled_noise = aligned_noise * scale_factor
    # 4. Measure SNR before mix (signal / scaled_noise aligned)
    n_rms_after = float(np.sqrt(np.mean(scaled_noise**2)))
    measured_before = float(20 * np.log10(s_rms / (n_rms_after + 1e-12)))
    # 5. Mix
    mixed = speech + scaled_noise
    # 6. Check/report clipping
    peak = float(np.max(np.abs(mixed)))
    clipping = peak > 0.99
    if clipping:
        # Preserve scale but note clipping; do not silently rescale output and claim same SNR
        pass
    # Measure after mix from aligned components
    return mixed, float(measured_before), float(peak), float(clipping)


def measure_snr_from_components(speech: np.ndarray, noise: np.ndarray) -> float:
    s_rms = float(np.sqrt(np.mean(speech**2)))
    n_rms = float(np.sqrt(np.mean(noise**2)))
    return float(20 * np.log10(s_rms / (n_rms + 1e-12)))


def run_case(
    clean_path: str = "eval_data/vad_audio/fleurs/vi/vi_1660.wav",
    noise_path: str = "assets/noise/musan/steady/noise-free-sound-0030.wav",
    rir_path: str = "assets/noise/rirs/air_type1_air_binaural_aula_carolina_1_1_90_3.wav",
    snr_db: float = 10.0,
    out_path: str = "/tmp/kavi_vad_test_noisy.wav",
) -> dict:
    clean = load_mono(clean_path, SR)
    noise = load_mono(noise_path, SR)
    rir = load_mono(rir_path, SR)
    reverbed = apply_rir(clean, rir)
    noisy, measured_before, mixed_peak, clipping = mix_snr(reverbed, noise, snr_db)
    # After mix measurement from actual components (reverbed + scaled_noise)
    # Rebuild scaled_noise for measurement consistency
    aligned_noise = align_noise(noise, len(reverbed))
    s_rms = float(np.sqrt(np.mean(reverbed**2)))
    target_noise_rms = s_rms / (10 ** (snr_db / 20.0))
    scale_factor = target_noise_rms / (
        float(np.sqrt(np.mean(aligned_noise**2))) + 1e-12
    )
    scaled_noise = aligned_noise * scale_factor
    measured_after = measure_snr_from_components(reverbed, scaled_noise)
    sf.write(out_path, noisy, SR)
    return {
        "target_snr_db": snr_db,
        "measured_before_mix_dB": measured_before,
        "measured_after_mix_dB": measured_after,
        "mixed_peak": mixed_peak,
        "clipping": clipping,
        "output_path": out_path,
        "clean_path": clean_path,
        "noise_path": noise_path,
        "rir_path": rir_path,
        "sample_rate": SR,
        "duration_s": float(len(noisy) / SR),
        "speech_peak": float(np.max(np.abs(reverbed))),
        "noise_peak_before_scale": float(np.max(np.abs(aligned_noise))),
    }
