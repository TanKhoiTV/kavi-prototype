"""MT candidate: Opus-MT (Helsinki-NLP) vi->en via CTranslate2 int8 (offline).

Loads the CT2 weights already in models/opus-mt-vi-en-ct2 and the SentencePiece
tokenizers from models/opus-mt-vi-en-src (reused from archive/pipeline.py). Fully
offline. v0 covers vi->en only; the en->vi weights are not yet in the repo.
"""

from __future__ import annotations

from pathlib import Path

from ..adapters import Candidate
from ..schema import EvalItem

_ROOT = Path(__file__).resolve().parents[2]
MT_MODEL_DIR = _ROOT / "models" / "opus-mt-vi-en-ct2"
MT_SRC_DIR = _ROOT / "models" / "opus-mt-vi-en-src"


class OpusMTMTCandidate(Candidate):
    stage = "MT"
    id = "opus-mt-vi-en-ct2-cpu"

    def __init__(
        self, model_path: str | None = None, config: dict | None = None
    ) -> None:
        import ctranslate2
        import sentencepiece as spm

        model_dir = Path(model_path) if model_path else MT_MODEL_DIR
        if not model_dir.exists():
            raise FileNotFoundError(f"MT model not found at {model_dir}")
        self.translator = ctranslate2.Translator(
            str(model_dir), device="cpu", compute_type="int8"
        )
        self.sp_src = spm.SentencePieceProcessor()
        self.sp_src.load(str(MT_SRC_DIR / "source.spm"))
        self.sp_tgt = spm.SentencePieceProcessor()
        self.sp_tgt.load(str(MT_SRC_DIR / "target.spm"))

    def _infer(self, item: EvalItem) -> tuple[str | None, str | None]:
        text = item.resolve_input()
        tokens = self.sp_src.encode(text, out_type=str)
        results = self.translator.translate_batch([tokens])
        translation = self.sp_tgt.decode(results[0].hypotheses[0])
        return translation, None
