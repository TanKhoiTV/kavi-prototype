"""Tiny self-contained eval set so the harness runs end-to-end on CPU today (offline)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from .schema import EvalItem, RunManifest


def make_tone_wav(path: Path, seconds: float = 1.0, sample_rate: int = 16000) -> None:
    import numpy as np
    import soundfile as sf

    t = np.linspace(0, seconds, int(seconds * sample_rate))
    tone = (0.2 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)
    sf.write(str(path), tone, sample_rate)


def build_smoke_manifest(workdir: Path | None = None) -> RunManifest:
    workdir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="kavi-bench-"))
    workdir.mkdir(parents=True, exist_ok=True)

    items = [
        EvalItem(
            id="smoke-mt-1",
            stage="MT",
            language="vi",
            direction="vi->en",
            input_text="Xin chào, tôi cần giúp đỡ.",
            reference_text="Hello, I need help.",
        ),
        EvalItem(
            id="smoke-tts-1",
            stage="TTS",
            language="en",
            direction="",
            input_text="Hello, I need help.",
        ),
        # ASR needs a one-time Whisper-Small weight fetch (setup, not runtime).
        # If the weights are not cached, run.py records the error gracefully.
        EvalItem(
            id="smoke-asr-1",
            stage="ASR",
            language="vi",
            direction="",
            audio_ref=str(workdir / "smoke-asr-tone.wav"),
            reference_text="",
        ),
    ]
    make_tone_wav(Path(workdir / "smoke-asr-tone.wav"))
    return RunManifest(version="eval_manifest_v1", items=items)
