"""Minimal test for one noisy case (real MUSAN + RIRS + 10 dB)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from bench.vad_noise import (
    LEAD_SAMPLES,
    TRAIL_SAMPLES,
    align_noise,
    build_timeline_audio,
    rms,
    run_case,
    speech_mask,
)


def test_align_noise_longer():
    arr = np.arange(100)
    out = align_noise(arr, 30)
    assert len(out) == 30
    assert np.array_equal(out, arr[:30])


def test_align_noise_shorter():
    arr = np.arange(10)
    out = align_noise(arr, 25)
    assert len(out) == 25
    assert np.array_equal(out[:10], arr)


def test_align_noise_equal():
    arr = np.arange(20)
    out = align_noise(arr, 20)
    assert len(out) == 20
    assert np.array_equal(out, arr)


def test_noisy_output() -> None:
    out = "/tmp/kavi_vad_test_noisy.wav"
    if Path(out).exists():
        Path(out).unlink()
    res = run_case(out_path=out)
    assert Path(out).exists(), "no output WAV"
    info = sf.info(out)
    assert info.samplerate == 16000, f"sr={info.samplerate}"
    assert info.frames > 0, "empty audio"
    assert res["target_snr_db"] == 10.0
    # Tolerance ±0.5 dB
    assert abs(res["measured_after_mix_dB"] - 10.0) <= 0.5, (
        f"SNR error={abs(res['measured_after_mix_dB'] - 10.0):.2f} dB"
    )
    assert not res["clipping"], "clipping occurred"
    print(
        f"target={res['target_snr_db']} measured_after_mix={res['measured_after_mix_dB']:.2f} peak={res['mixed_peak']:.4f} clipping={res['clipping']}"
    )


def _speech(n: int, seed: int) -> np.ndarray:
    return (0.1 * np.random.default_rng(seed).standard_normal(n)).astype(np.float32)


def test_timeline_clean_gt_and_silence() -> None:
    a, b = _speech(3200, 1), _speech(4800, 2)
    built = build_timeline_audio(a, b, 350)
    pause = 350 * 16
    assert built.gt_segments == [
        (LEAD_SAMPLES, LEAD_SAMPLES + 3200),
        (LEAD_SAMPLES + 3200 + pause, LEAD_SAMPLES + 3200 + pause + 4800),
    ]
    assert len(built.audio) == LEAD_SAMPLES + 3200 + pause + 4800 + TRAIL_SAMPLES
    assert np.all(built.audio[:LEAD_SAMPLES] == 0)
    assert np.all(built.audio[-TRAIL_SAMPLES:] == 0)
    assert built.noise_component is None
    assert built.snr_db_construction is None


@pytest.mark.parametrize("snr_db", [15.0, 5.0, 0.0, -5.0])
def test_timeline_noise_covers_whole_timeline_and_hits_snr(snr_db: float) -> None:
    a, b = _speech(8000, 3), _speech(8000, 4)
    noise = np.random.default_rng(5).standard_normal(5000).astype(np.float32)
    built = build_timeline_audio(a, b, 200, noise=noise, snr_db=snr_db)
    audio = built.audio.astype(np.float64)
    assert rms(audio[:LEAD_SAMPLES]) > 0
    assert rms(audio[-TRAIL_SAMPLES:]) > 0
    (_, a_end), (b_start, _) = built.gt_segments
    assert rms(audio[a_end:b_start]) > 0
    residual = audio - built.reference
    mask = speech_mask(len(audio), built.gt_segments)
    measured = 20 * np.log10(rms(built.reference[mask]) / rms(residual))
    assert abs(measured - snr_db) < 0.01


def test_timeline_rir_tail_spills_into_pause() -> None:
    a, b = _speech(3200, 6), _speech(3200, 7)
    rir = np.exp(-np.arange(1600) / 200.0).astype(np.float32)
    built = build_timeline_audio(a, b, 200, rir=rir)
    (_, a_end), (b_start, _) = built.gt_segments
    assert np.max(np.abs(built.reference[a_end : a_end + 800])) > 0
    assert b_start - a_end == 200 * 16


def test_timeline_identity_rir_keeps_speech() -> None:
    a, b = _speech(3200, 8), _speech(3200, 9)
    plain = build_timeline_audio(a, b, 200)
    ident = build_timeline_audio(a, b, 200, rir=np.array([1.0], dtype=np.float32))
    assert np.allclose(plain.audio, ident.audio, atol=1e-6)


def test_timeline_peak_limited_keeps_snr() -> None:
    a, b = 4 * _speech(3200, 10), 4 * _speech(3200, 11)
    noise = np.random.default_rng(12).standard_normal(4000).astype(np.float32)
    built = build_timeline_audio(a, b, 200, noise=noise, snr_db=-5.0)
    assert built.peak_limited
    assert float(np.max(np.abs(built.audio))) <= 0.99 + 1e-6
    residual = built.audio.astype(np.float64) - built.reference
    mask = speech_mask(len(built.audio), built.gt_segments)
    measured = 20 * np.log10(rms(built.reference[mask]) / rms(residual))
    assert abs(measured + 5.0) < 0.01


def test_timeline_noise_requires_snr() -> None:
    a, b = _speech(1600, 13), _speech(1600, 14)
    with pytest.raises(ValueError):
        build_timeline_audio(a, b, 200, noise=np.ones(100, dtype=np.float32))
