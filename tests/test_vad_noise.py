"""Minimal test for one noisy case (real MUSAN + RIRS + 10 dB)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from bench.vad_noise import align_noise, run_case


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
