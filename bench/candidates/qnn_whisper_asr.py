"""QNN Whisper ASR adapter — stub for on-device inference. **SUPERSEDED**
(ADR-008): ASR is CPU-only Dual Zipformer via sherpa-onnx; the Whisper QNN path
is retained for the record only.

This adapter is a placeholder for the Phase-4 on-device QNN benchmark runner.
The actual QNN inference runs on a Snapdragon 8 Gen 2 (HTP v73) via the
Qualcomm AI Runtime. This host-side stub defines the interface and will
eventually:

1. Load context binary via ``QnnModelLoader`` (bundled in APK assets)
2. Convert audio to mel spectrogram via a host-side Whisper preprocessor
3. Run encoder inference on HTP v73
4. Run decoder loop (autoregressive; likely CPU fallback on device)
5. Return transcribed text

The on-device runner is an Android instrumented test / thin service that
reads ``eval_manifest_v1.json`` and executes candidates via
``com.kavi.app.runner`` (see ``android/app/src/main/java/com/kavi/app/runner/``).

Integration path (when implemented):
    - Pre-requisite model artifacts in ``models/qnn/whisper-small/``:
      encoder_htp_v73.bin, decoder_htp_v73.bin
    - Context binary bundled into APK assets
    - On-device runner loads and executes via ``QnnModelLoader``
"""

from __future__ import annotations

from ..adapters import Candidate
from ..schema import EvalItem


class QnnWhisperASRCandidate(Candidate):
    """QNN Whisper Small ASR candidate (encoder on HTP v73, decoder on CPU).

    ADR-005 Decision 2: encoder on NPU, decoder on CPU.

    Parameters
    ----------
    model_path : str | None
        Path to the directory containing the model artifacts.
        Expected structure::

            {model_path}/
            ├── encoder_htp_v73.bin       # QNN context binary (encoder, NPU)
            ├── decoder_model.onnx        # Whisper decoder ONNX (CPU/ORT)
            └── input_list.txt            # Calibration input list

    config : dict | None
        Recognized keys:
        - ``language`` (str, default ``"vi"``): whisper decode language hint.
    """

    stage = "ASR"
    id = "qnn-whisper-small-htp-v73"

    def __init__(
        self, model_path: str | None = None, config: dict | None = None
    ) -> None:
        self.model_path = model_path
        cfg = config or {}
        self.language = cfg.get("language", "vi")

    def _infer(self, item: EvalItem) -> tuple[str | None, str | None]:
        """Run Whisper ASR via QNN on-device inference.

        TODO: Implement Android instrumented test runner:
        1. Convert audio to mel spectrogram (host-side preprocessor)
        2. Load encoder context binary via ``QnnModelLoader`` (NPU)
        3. Run encoder on HTP v73 via ``QnnModelLoader.run_inference()``
        4. Load decoder ONNX via ORT (CPU)
        5. Run autoregressive decoder loop (CPU)
        6. Return transcribed text

        Until the on-device runner is implemented, this stub raises
        NotImplementedError to make test failures explicit rather than
        silently producing empty results.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} is a stub. "
            f"On-device inference is not yet implemented.\n"
            f"Model path: {self.model_path}\n"
            f"Integration path: convert encoder ONNX to HTP v73 context binary, "
            f"bundle decoder ONNX + encoder .bin in APK assets, run via "
            f"Android instrumented test runner "
            f"(see android/app/src/main/java/com/kavi/app/runner/)."
        )
