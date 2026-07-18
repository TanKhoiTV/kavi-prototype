"""TTS candidate: Piper voice (CPU, offline). EN leg for v0.

Loads the bundled en_US-lessac-medium.onnx voice. Fully offline. The VI voice
(vais1000) is not yet in the repo, so the v0 TTS leg is English only.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from ..adapters import Candidate
from ..schema import EvalItem

_ROOT = Path(__file__).resolve().parents[2]
VOICES_DIR = _ROOT / "voices"


class PiperTTSCandidate(Candidate):
    stage = "TTS"
    id = "piper-en-lessac-cpu"

    def __init__(
        self, model_path: str | None = None, config: dict | None = None
    ) -> None:
        from piper import PiperVoice

        self.model_path = (
            Path(model_path)
            if model_path
            else (VOICES_DIR / "en_US-lessac-medium.onnx")
        )
        self.config_path = self.model_path.with_suffix(".onnx.json")
        if not self.model_path.exists():
            raise FileNotFoundError(f"Piper voice not found: {self.model_path}")
        self.voice = PiperVoice.load(self.model_path, self.config_path)
        self.out_dir: str | None = None

    def _infer(self, item: EvalItem) -> tuple[str | None, str | None]:
        import numpy as np
        import soundfile as sf

        text = item.resolve_input()
        out_dir = Path(self.out_dir) if self.out_dir else Path(tempfile.mkdtemp())
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{item.id}.wav"
        chunks = list(self.voice.synthesize(text))
        audio = np.concatenate([c.audio_int16_array for c in chunks])
        sf.write(str(out_path), audio, self.voice.config.sample_rate)
        return None, str(out_path)
