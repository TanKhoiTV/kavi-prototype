"""RTranslator baseline adapter — read-only, scores captured on-device outputs.

This adapter does NOT run RTranslator (that is a semi-manual on-device process
documented in docs/rtranslator-test-protocol.md). Instead it reads the text and
audio files produced by a manual RTranslator run and maps them to EvalItem
schema for scoring via bench/scorer.py.

Expected output directory layout (after running the test protocol):
    rtranslator_outputs/
    ├── manifest.json              # copy of eval_manifest_v1.json for this run
    ├── device-state.json          # device state checklist values
    ├── vi-en/
    │   ├── asr_vi_1824.txt        # ASR transcript for item vi-asr-1824-clean
    │   ├── mt_en_1824.txt         # MT translation for item vi-en-mt-1824
    │   ├── tts_en_1824.wav        # TTS audio if captured
    │   └── ...
    └── en-vi/
        ├── asr_en_0001.txt
        ├── mt_vi_0001.txt
        └── ...
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..adapters import Candidate
from ..schema import EvalItem


def _extract_numeric_id(item_id: str) -> str | None:
    """Extract the trailing numeric portion of a hyphenated item ID.

    Examples::
        _extract_numeric_id("vi-asr-1824-clean")    -> "1824"
        _extract_numeric_id("vi-en-mt-1816")         -> "1816"
        _extract_numeric_id("gold-mt-00")            -> "00"
    """
    import re

    parts = item_id.split("-")
    for part in reversed(parts):
        if re.fullmatch(r"\d+", part):
            return part
    return None


class RTranslatorCandidate(Candidate):
    """Read-only candidate that maps captured RTranslator outputs to EvalItems.

    Parameters
    ----------
    model_path : str | None
        Ignored (RTranslator runs on-device, not via this harness). Use
        ``outputs_dir`` in config instead.
    config : dict | None
        Recognized keys:
        - ``outputs_dir`` (str, required): path to the directory containing
          RTranslator output files.
        - ``suffix`` (str, default ``".txt"``): file extension for text outputs.
        - ``fallback_pattern`` (str, default ``"{item_id}"``): template for
          matching output files to item IDs. Supports ``{item_id}``,
          ``{stage}``, ``{language}``, ``{direction}``.
        - ``audio_suffix`` (str, default ``".wav"``): file extension for TTS outputs.
    """

    stage = "RTranslator"
    id = "rtranslator-2.1.5"

    def __init__(
        self, model_path: str | None = None, config: dict[str, Any] | None = None
    ) -> None:
        cfg = config or {}
        outputs_dir_str = cfg.get("outputs_dir")
        if not outputs_dir_str:
            raise ValueError(
                "RTranslatorCandidate requires config['outputs_dir'] pointing to "
                "the directory of captured RTranslator outputs"
            )
        self.outputs_dir = Path(outputs_dir_str)
        if not self.outputs_dir.is_dir():
            raise NotADirectoryError(
                f"RTranslator outputs directory not found: {self.outputs_dir}"
            )
        self.suffix = cfg.get("suffix", ".txt")
        self.audio_suffix = cfg.get("audio_suffix", ".wav")
        self.fallback_pattern = cfg.get("fallback_pattern", "{item_id}")

        # Load device-state metadata if present
        self.device_state: dict[str, Any] = {}
        state_path = self.outputs_dir / "device-state.json"
        if state_path.exists():
            self.device_state = json.loads(state_path.read_text(encoding="utf-8"))

    def _infer(self, item: EvalItem) -> tuple[str | None, str | None]:
        """Read pre-captured RTranslator output for `item` from the outputs dir.

        Returns
        -------
        (output_text | None, output_audio_path | None)
            Text comes from a ``.txt`` file; audio from a ``.wav`` file.
        """

        # Try exact match: outputs_dir / {item_id}.txt
        text_path = self.outputs_dir / f"{item.id}{self.suffix}"
        if not text_path.exists():
            # Try stage-specific pattern: outputs_dir / {stage}_{lang}_{id}.txt
            pattern = self.fallback_pattern.format(
                item_id=item.id,
                stage=item.stage.lower(),
                language=item.language,
                direction=item.direction.replace("->", "-") if item.direction else "",
            )
            text_path = (self.outputs_dir / pattern).with_suffix(self.suffix)
            if not text_path.exists():
                # Scan subdirectories (e.g. vi-en/, en-vi/)
                text_path = self._find_recursive(item)

        output_text: str | None = None
        if text_path and text_path.exists():
            output_text = text_path.read_text(encoding="utf-8").strip()

        # Audio output (TTS stage only)
        output_audio: str | None = None
        if item.stage == "TTS":
            audio_path = text_path.with_suffix(self.audio_suffix) if text_path else None
            if audio_path and audio_path.exists():
                output_audio = str(audio_path)
            else:
                # Also try subdirectory scan for audio
                audio_candidate = self._find_recursive(item, suffix=self.audio_suffix)
                if audio_candidate:
                    output_audio = str(audio_candidate)

        return output_text, output_audio

    def _find_recursive(self, item: EvalItem, suffix: str | None = None) -> Path | None:
        """Search outputs_dir subdirectories for a file matching item.id.

        Matches by extracting the numeric ID from the item (e.g. ``1824`` from
        ``vi-asr-1824-clean``) and scanning for files whose stem contains that
        number. This handles the naming convention from the test protocol:
        ``asr_vi_1824.txt``, ``mt_en_1824.txt``, etc.
        """
        suffix = suffix or self.suffix
        # Extract numeric portion of the item ID (e.g. "1824" from "vi-asr-1824-clean")
        numeric_id = _extract_numeric_id(item.id)
        if numeric_id is None:
            return None
        for child in self.outputs_dir.rglob(f"*{numeric_id}{suffix}"):
            if child.is_file():
                return child
        return None

    def summary(self) -> str:
        """Return a one-line summary of the loaded RTranslator outputs."""
        files = [
            str(p.relative_to(self.outputs_dir))
            for p in sorted(self.outputs_dir.rglob("*"))
            if p.is_file() and p.suffix in (".txt", ".wav", ".json", ".yaml", ".yml")
        ]
        if not files:
            return "No RTranslator output files found."
        n_txt = sum(1 for f in files if f.endswith(".txt"))
        n_wav = sum(1 for f in files if f.endswith(".wav"))
        return f"{len(files)} files ({n_txt} text, {n_wav} audio)"
