"""Eval-manifest schema (eval_manifest_v1.json) + result dataclasses."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

MANIFEST_VERSION = "eval_manifest_v1"


@dataclass
class EvalItem:
    id: str
    stage: str  # "ASR" | "MT" | "TTS"
    language: str  # "vi" | "en"
    direction: str = ""  # "vi->en" | "en->vi" | ""
    candidate_id: str = ""
    model_path: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    audio_ref: str | None = None  # input audio (ASR) or input text file (MT/TTS)
    transcript_ref: str | None = None  # reference transcript file
    input_text: str | None = None  # inline input text (overrides audio_ref)
    reference_text: str | None = (
        None  # inline reference text (overrides transcript_ref)
    )
    snr: float | None = None
    noise_type: str | None = None

    def resolve_input(self) -> str:
        if self.input_text is not None:
            return self.input_text
        if self.audio_ref is not None:
            path = Path(self.audio_ref)
            if path.exists() and path.suffix not in (".wav", ".mp3", ".flac", ".ogg"):
                return path.read_text(encoding="utf-8").strip()
            return self.audio_ref  # treat as a (possibly missing) audio path
        raise ValueError(f"item {self.id}: needs input_text or audio_ref")

    def resolve_reference(self) -> str | None:
        if self.reference_text is not None:
            return self.reference_text
        if self.transcript_ref is not None:
            path = Path(self.transcript_ref)
            if path.exists():
                return path.read_text(encoding="utf-8").strip()
        return None


@dataclass
class StageResult:
    candidate_id: str
    item_id: str
    stage: str
    output_text: str | None = None
    output_audio_path: str | None = None
    latency_s: float = 0.0
    peak_ram_mb: float | None = None
    error: str | None = None


@dataclass
class RunManifest:
    version: str = MANIFEST_VERSION
    items: list[EvalItem] = field(default_factory=list)

    def to_json(self, path: str | Path) -> None:
        data = {"version": self.version, "items": [asdict(i) for i in self.items]}
        Path(path).write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def from_json(cls, path: str | Path) -> RunManifest:
        try:
            raw = Path(path).read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid eval manifest {path}: {exc}") from exc
        items = [EvalItem(**i) for i in data.get("items", [])]
        return cls(version=data.get("version", MANIFEST_VERSION), items=items)
