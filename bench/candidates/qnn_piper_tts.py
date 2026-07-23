"""QNN Piper TTS adapter — stub for on-device inference.

This adapter is a placeholder for the Phase-4 on-device QNN benchmark runner.
The actual QNN inference runs on a Snapdragon 8 Gen 2 (HTP v73) via the
Qualcomm AI Runtime. This host-side stub defines the interface and will
eventually:

1. Load context binary via ``QnnModelLoader`` (bundled in APK assets)
2. Convert input text to phoneme IDs on host (Piper's espeak-ng)
3. Run encoder on HTP v73 (NPU offload)
4. Run deterministic decoder (CPU fallback)
5. Return output audio path

The on-device runner is an Android instrumented test / thin service that
reads ``eval_manifest_v1.json`` and executes candidates via
``com.kavi.app.runner`` (see ``android/app/src/main/java/com/kavi/app/runner/``).

Integration path (when implemented):
    - Pre-requisite model artifacts in ``models/qnn/piper-en/``:
      piper_encoder_htp_v73.bin (NPU), piper_decoder (CPU fallback)
    - Piper ONNX must first be patched via ``bench/qnn/patch_piper_onnx.py``
      to remove RandomNormalLike and fix output length
    - Context binary bundled into APK assets
    - On-device runner loads and executes via ``QnnModelLoader``
"""

from __future__ import annotations

from ..adapters import Candidate
from ..schema import EvalItem


class QnnPiperTTSCandidate(Candidate):
    """QNN Piper TTS candidate (HTP v73, w8a16 quantized).

    Parameters
    ----------
    model_path : str | None
        Path to the directory containing the QNN context binary and metadata.
        Expected structure::

            {model_path}/
            ├── encoder_htp_v73.bin       # QNN context binary (encoder, NPU)
            ├── decoder_htp_v73.bin        # QNN context binary (decoder, CPU fallback)
            └── input_list.txt             # Calibration input list

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
        """Run Piper TTS via QNN on-device inference.

        TODO: Implement Android instrumented test runner:
        1. Load context binary via ``QnnModelLoader``
        2. Convert input text to phoneme IDs (host-side espeak-ng)
        3. Run encoder on HTP v73 (NPU offload)
        4. Run deterministic decoder (CPU fallback)
        5. Save output audio, return path

        Until the on-device runner is implemented, this stub raises
        NotImplementedError to make test failures explicit rather than
        silently producing empty results.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} is a stub. "
            f"On-device QNN inference is not yet implemented.\n"
            f"Model path: {self.model_path}\n"
            f"Integration path: patch Piper ONNX (remove RandomNormalLike, "
            f"pin output length), convert to HTP v73 context binary, bundle "
            f"in APK assets, run via Android instrumented test runner "
            f"(see android/app/src/main/java/com/kavi/app/runner/)."
        )
