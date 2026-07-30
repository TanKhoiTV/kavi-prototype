"""ASR candidate: Zipformer via sherpa-onnx (CPU).

Zipformer is a transducer-based ASR model that runs on sherpa-onnx,
not CTranslate2. Each language has its own checkpoint (single-language).

Beam concept differs from CT2/Transformer models:
- beam=1 → greedy_search (true greedy decoding)
- beam≥2 → modified_beam_search with max_active_paths=<beam>

This mapping is internal to the candidate. The sweep interface
(beam_size from config-override) stays consistent with Whisper/Moonshine.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from ..adapters import Candidate
from ..schema import EvalItem


class ZipformerCandidateBase(Candidate):
    stage = "ASR"
    _model_dir_attr: str = ""
    _expected_lang: str = ""

    def __init__(
        self, model_path: str | None = None, config: dict | None = None
    ) -> None:
        import sherpa_onnx

        cfg = config or {}
        beam = cfg.get("beam_size", 4)

        # beam=1 → greedy_search (true greedy, không phải modified_beam_search
        # với max_active_paths=1 — 2 thuật toán khác nhau về mặt toán học).
        # beam≥2 → modified_beam_search với max_active_paths = beam.
        decoding_method = "greedy_search" if beam == 1 else "modified_beam_search"

        model_dir = Path(model_path) if model_path else Path(self._model_dir_attr)
        # Allow int8 encoder/joiner with fallback to fp32
        encoder = model_dir / "encoder.int8.onnx"
        if not encoder.exists():
            # Try fp32
            enc_candidates = list(model_dir.glob("encoder*.onnx"))
            encoder = enc_candidates[0] if enc_candidates else encoder

        decoder = model_dir / "decoder.onnx"
        if not decoder.exists():
            dec_candidates = list(model_dir.glob("decoder*.onnx"))
            decoder = dec_candidates[0] if dec_candidates else decoder

        joiner = model_dir / "joiner.int8.onnx"
        if not joiner.exists():
            join_candidates = list(model_dir.glob("joiner*.onnx"))
            joiner = join_candidates[0] if join_candidates else joiner

        tokens = model_dir / "tokens.txt"

        self.recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(encoder),
            decoder=str(decoder),
            joiner=str(joiner),
            tokens=str(tokens),
            decoding_method=decoding_method,
            max_active_paths=beam,  # ignored when decoding_method="greedy_search"
            provider="cpu",
        )

    def _infer(self, item: EvalItem) -> tuple[str | None, str | None]:
        lang = getattr(item, "language", None)
        if lang != self._expected_lang:
            return None, (
                f"{type(self).__name__} nhận item không phải {self._expected_lang}: "
                f"{item.id} (language={lang!r})"
            )

        audio_path = item.audio_ref or item.input_text
        if not audio_path or not os.path.exists(audio_path):
            return None, f"audio file not found: {audio_path!r}"

        import soundfile as sf

        samples, sample_rate = sf.read(audio_path)
        if samples.ndim > 1:
            samples = samples.mean(axis=1)

        stream = self.recognizer.create_stream()
        stream.accept_waveform(sample_rate, samples.astype(np.float32))
        self.recognizer.decode_stream(stream)

        text = stream.result.text.strip()
        return text or "", None


class ZipformerViCandidate(ZipformerCandidateBase):
    id = "zipformer-vi-30m-sherpa-onnx-cpu"
    _model_dir_attr = "models/sherpa-onnx-zipformer-vi-30M-int8"
    _expected_lang = "vi"


class ZipformerEnCandidate(ZipformerCandidateBase):
    id = "zipformer-en-sherpa-onnx-cpu"
    _model_dir_attr = "models/sherpa-onnx-zipformer-en"
    _expected_lang = "en"
