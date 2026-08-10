"""Piper TTS adapter — CPU-only stub for on-device inference. **SUPERSEDED**
(ADR-009): v1 TTS is Supertonic Phase 1 via sherpa-onnx `OfflineTts`; Piper VITS
is demoted to fallback. Retained for the record.

ADR-005 Decision 3: Piper stays on CPU. QNN conversion is skipped because
Piper ONNX has a cyclic graph that QAIRT cannot handle, and the model is
already fast on CPU (RTF 0.06–0.22 from baseline). TTS is not the pipeline
bottleneck.

The on-device runner is an Android instrumented test / thin service that
reads ``eval_manifest_v1.json`` and executes candidates via
``com.kavi.app.runner`` (see ``android/app/src/main/java/com/kavi/app/runner/``).

Integration path (when implemented):
    - Piper ONNX patched via ``bench/qnn/patch_piper_onnx.py``
      (removes RandomNormalLike, fixes output length)
    - On-device runner loads patched ONNX via ORT (CPU) in the Android app
    - Input text is converted to phoneme IDs on host using Piper's espeak-ng
"""

from __future__ import annotations

from ..adapters import Candidate
from ..schema import EvalItem


class QnnPiperTTSCandidate(Candidate):
    """Piper TTS candidate (CPU-only, per ADR-005 Decision 3).

    Parameters
    ----------
    model_path : str | None
        Path to the directory containing the patched Piper ONNX and metadata.
        Expected structure::

            {model_path}/
            ├── piper_patched.onnx        # Patched Piper ONNX (CPU, no QNN)
            └── voices/                   # Voice configs for espeak-ng

    config : dict | None
        Recognized keys:
        - ``voice_path`` (str, default ``"voices/en_US-lessac-medium.onnx"``):
          path to the original Piper voice (used for phonemisation config).
        - ``sample_rate`` (int, default ``22050``): output audio sample rate.
    """

    stage = "TTS"
    id = "qnn-piper-en-htp-v73"

    def __init__(
        self, model_path: str | None = None, config: dict | None = None
    ) -> None:
        self.model_path = model_path
        cfg = config or {}
        self.voice_path = cfg.get("voice_path", "voices/en_US-lessac-medium.onnx")
        self.sample_rate = cfg.get("sample_rate", 22050)

    def _infer(self, item: EvalItem) -> tuple[str | None, str | None]:
        """Run Piper TTS via CPU inference on-device.

        TODO: Implement Android instrumented test runner:
        1. Convert input text to phoneme IDs (host-side espeak-ng)
        2. Load patched Piper ONNX via ORT (CPU)
        3. Run full Piper pipeline (encoder + decoder, CPU)
        4. Save output audio, return path

        Until the on-device runner is implemented, this stub raises
        NotImplementedError to make test failures explicit rather than
        silently producing empty results.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} is a stub. "
            f"On-device CPU inference is not yet implemented.\n"
            f"Model path: {self.model_path}\n"
            f"Integration path: patch Piper ONNX via bench/qnn/patch_piper_onnx.py, "
            f"run via Android instrumented test runner (CPU/ORR) "
            f"(see android/app/src/main/java/com/kavi/app/runner/)."
        )
