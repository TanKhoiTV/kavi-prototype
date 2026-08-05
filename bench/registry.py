"""Candidate registry: candidate_id -> (class, default model_path, default config)."""

from __future__ import annotations

from .candidates.opusmt_mt import OpusMTMTCandidate
from .candidates.piper_tts import PiperTTSCandidate
from .candidates.qnn_opusmt_mt import QnnOpusMTMTCandidate
# qnn_whisper_asr / qnn_piper_tts: superseded by ADR-008/009 — kept registered
# as no-op stubs for the record; only QnnOpusMTMTCandidate is on the v1 path.
from .candidates.qnn_piper_tts import QnnPiperTTSCandidate
from .candidates.qnn_whisper_asr import QnnWhisperASRCandidate
from .candidates.rtranslator import RTranslatorCandidate
from .candidates.whisper_asr import WhisperASRCandidate
from .schema import EvalItem

RegistryEntry = tuple[type, str | None, dict]

REGISTRY: dict[str, RegistryEntry] = {
    WhisperASRCandidate.id: (WhisperASRCandidate, None, {}),
    OpusMTMTCandidate.id: (OpusMTMTCandidate, None, {}),
    PiperTTSCandidate.id: (PiperTTSCandidate, None, {}),
    QnnWhisperASRCandidate.id: (QnnWhisperASRCandidate, None, {}),
    QnnOpusMTMTCandidate.id: (QnnOpusMTMTCandidate, None, {}),
    QnnPiperTTSCandidate.id: (QnnPiperTTSCandidate, None, {}),
    RTranslatorCandidate.id: (RTranslatorCandidate, None, {}),
}


def default_candidate_id_for_stage(stage: str) -> str | None:
    """Return the registered candidate id for `stage` (first match), or None."""
    for cid, (cls, _, _) in REGISTRY.items():
        if getattr(cls, "stage", None) == stage:
            return cid
    return None


def build_candidate(item: EvalItem):
    cid = item.candidate_id or default_candidate_id_for_stage(item.stage)
    if cid is None or cid not in REGISTRY:
        raise KeyError(
            f"no candidate for item {item.id!r} (stage={item.stage!r}, "
            f"candidate_id={item.candidate_id!r}); known: {sorted(REGISTRY)}"
        )
    cls, default_model, default_cfg = REGISTRY[cid]
    model_path = item.model_path if item.model_path is not None else default_model
    config = {**default_cfg, **(item.config or {})}
    return cls(model_path=model_path, config=config)
