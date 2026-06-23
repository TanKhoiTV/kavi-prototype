from __future__ import annotations

import functools
import time

import numpy as np
import soundfile as sf


@functools.lru_cache(maxsize=1)
def load_vad():
    """Load Silero VAD model, cached once."""
    from silero_vad import load_silero_vad

    return load_silero_vad(onnx=False)


def rms_normalize(data: np.ndarray, target_dbfs: float = -20.0) -> np.ndarray:
    """RMS-normalize audio to target level. No-op if input is silent."""
    rms = np.sqrt(np.mean(data**2))
    if rms > 1e-10:
        target_rms = 10.0 ** (target_dbfs / 20.0)
        data = data * (target_rms / rms)
        data = np.clip(data, -1.0, 1.0)
    return data


def get_speech_metadata(
    audio_path: str,
    threshold: float = 0.4,
    min_speech_duration_ms: int = 250,
    min_silence_duration_ms: int = 100,
) -> dict:
    """Run VAD on a 16 kHz mono WAV file and return speech metadata.

    Returns dict:
        {
            "speech_ratio": float,   # proportion of frames classified as speech (0.0–1.0)
            "total_frames": int,     # total audio frames processed
            "speech_frames": int,    # frames where speech was detected
            "elapsed_s": float,      # wall-clock VAD processing time
            "threshold": float,      # the threshold used
        }
    """
    t0 = time.perf_counter()

    try:
        from silero_vad import get_speech_timestamps
    except ImportError:
        return {
            "available": False,
            "speech_ratio": 1.0,
            "total_frames": 0,
            "speech_frames": 0,
            "elapsed_s": 0.0,
            "threshold": threshold,
        }

    wav, sr = sf.read(audio_path)
    if sr != 16000:
        import warnings

        warnings.warn(
            f"Expected 16 kHz, got {sr} Hz — VAD may be inaccurate", stacklevel=2
        )
    if wav.ndim > 1:
        wav = wav.mean(axis=1)  # mono

    vad = load_vad()

    segments = get_speech_timestamps(
        wav,
        model=vad,
        threshold=threshold,
        sampling_rate=sr,
        min_speech_duration_ms=min_speech_duration_ms,
        min_silence_duration_ms=min_silence_duration_ms,
        return_seconds=True,
    )

    total_frames = len(wav)
    speech_frames = sum(int((seg["end"] - seg["start"]) * sr) for seg in segments)
    speech_ratio = speech_frames / total_frames if total_frames > 0 else 0.0

    elapsed = round(time.perf_counter() - t0, 3)

    return {
        "available": True,
        "speech_ratio": round(speech_ratio, 4),
        "total_frames": total_frames,
        "speech_frames": speech_frames,
        "elapsed_s": elapsed,
        "threshold": threshold,
    }
