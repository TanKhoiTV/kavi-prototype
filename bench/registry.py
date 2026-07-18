"""Candidate registry: candidate_id -> (class, default model_path, default config)."""

from __future__ import annotations

from .candidates.opusmt_mt import OpusMTMTCandidate
from .candidates.piper_tts import PiperTTSCandidate
from .candidates.whisper_asr import WhisperASRCandidate
from .schema import EvalItem

RegistryEntry = tuple[type, str | None, dict]

REGISTRY: dict[str, RegistryEntry] = {
    WhisperASRCandidate.id: (WhisperASRCandidate, None, {}),
    OpusMTMTCandidate.id: (OpusMTMTCandidate, None, {}),
    PiperTTSCandidate.id: (PiperTTSCandidate, None, {}),
}


def build_candidate(item: EvalItem):
    if item.candidate_id not in REGISTRY:
        raise KeyError(
            f"unknown candidate_id {item.candidate_id!r}; known: {sorted(REGISTRY)}"
        )
    cls, default_model, default_cfg = REGISTRY[item.candidate_id]
    model_path = item.model_path if item.model_path is not None else default_model
    config = {**default_cfg, **(item.config or {})}
    return cls(model_path=model_path, config=config)
