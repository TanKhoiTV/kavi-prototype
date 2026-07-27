"""ASR candidate: Moonshine Tiny/Basic via HuggingFace Transformers (CPU).

Moonshine is a tiny 27M-param speech-to-text model that streams audio
natively (no fixed-length window like Whisper). Available in language-specific
variants (vi, en, zh, ja, ko, etc.).

v0 CPU candidate. Supports both Moonshine-Tiny and Moonshine-Base variants.
The base model is English-only; use "moonshine-tiny-vi" for Vietnamese ASR.
"""

from __future__ import annotations

import os
import sys

import torch
from transformers import AutoProcessor, MoonshineForConditionalGeneration

from ..adapters import Candidate
from ..schema import EvalItem

# Model name map: language -> HuggingFace model ID
MODEL_IDS = {
    "vi": "usefulsensors/moonshine-tiny-vi",
    "en": "usefulsensors/moonshine-tiny",
}

# Default generation kwargs shared across all beam sizes
_DECODE_KWARGS = dict(
    num_beams=5,  # faster-whisper default parity
    early_stopping=True,
    no_repeat_ngram_size=3,
    max_length=448,
)


class MoonshineASRCandidate(Candidate):
    stage = "ASR"
    id = "moonshine-tiny-cpu"

    def __init__(
        self, model_path: str | None = None, config: dict | None = None
    ) -> None:
        cfg = config or {}
        self.language = cfg.get("language", "vi")
        self.beam_size = cfg.get("beam_size", 5)

        # Pick model ID based on language, or override via config/model_path
        model_id = (
            model_path
            if model_path
            else MODEL_IDS.get(self.language, "usefulsensors/moonshine-tiny")
        )

        self.processor = AutoProcessor.from_pretrained(model_id)
        self.model = MoonshineForConditionalGeneration.from_pretrained(model_id)
        self.model.eval()

    def _infer(self, item: EvalItem) -> tuple[str | None, str | None]:
        audio_path = item.audio_ref or item.input_text
        if not audio_path or not os.path.exists(audio_path):
            raise FileNotFoundError(
                f"Moonshine ASR needs an audio_ref path; got {audio_path!r}"
            )

        import soundfile as sf

        audio, sr = sf.read(str(audio_path))

        inputs = self.processor(
            audio,
            sampling_rate=sr,
            return_tensors="pt",
            return_attention_mask=True,
        )

        decode_kwargs = {
            **_DECODE_KWARGS,
            "num_beams": self.beam_size,
        }

        with torch.no_grad():
            gen_ids = self.model.generate(
                inputs["input_values"],
                attention_mask=inputs.get("attention_mask"),
                **decode_kwargs,
            )

        text = self.processor.batch_decode(gen_ids, skip_special_tokens=True)[0]
        return text.strip() or "", None
