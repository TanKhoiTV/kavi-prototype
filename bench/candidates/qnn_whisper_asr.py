"""QNN Whisper ASR adapter — stub for on-device inference.

This adapter is a placeholder for the Phase-4 on-device QNN benchmark runner.
The actual QNN inference runs on a Snapdragon 8 Gen 2 (HTP v73) via the
Qualcomm AI Runtime. This host-side stub defines the interface.

Architecture (ADR-005):
    - Encoder: QNN/NPU (HTP v73 context binary)
    - Decoder: CPU fallback (on-device, not via ADB bridge)

The Android instrumented test runner (not ADB bridge) handles:
    1. Load eval_manifest_v1.json via ManifestReader
    2. For each item: run encoder on NPU, decoder on CPU
    3. Measure latency/RTF/RAM internally
    4. Write results JSON

Integration path (when implemented):
    - Pre-requisite model artifacts in ``models/qnn/whisper-small/``:
      encoder_htp_v73.bin (NPU), decoder ONNX (CPU via ORT)
    - Android app builds with these assets
    - Instrumented test runs batch and outputs results JSON
    - Host pulls results via ``adb pull``
"""

from __future__ import annotations

from ..adapters import Candidate
from ..schema import EvalItem


class QnnWhisperASRCandidate(Candidate):
    """QNN Whisper Small ASR candidate (HTP v73, w8a16 quantized).

    Parameters
    ----------
    model_path : str | None
        Path to the directory containing the QNN context binary and metadata.
        Expected structure::

            {model_path}/
            ├── encoder_htp_v73.bin       # QNN context binary (encoder)
            ├── decoder_htp_v73.bin        # QNN context binary (decoder)
            ├── encoder_input_list.txt     # Calibration input list
            └── decoder_input_list.txt     # Calibration input list

    config : dict | None
        Recognized keys:
        - ``device_id`` (str, default ``""``): ADB device serial.
        - ``data_dir`` (str, default ``"/data/local/tmp/kavi/"``): temp dir on device.
        - ``language`` (str, default ``"vi"``): whisper decode language hint.
    """

    stage = "ASR"
    id = "qnn-whisper-small-htp-v73"

    def __init__(
        self, model_path: str | None = None, config: dict | None = None
    ) -> None:
        self.model_path = model_path
        cfg = config or {}
        self.device_id = cfg.get("device_id", "")
        self.data_dir = cfg.get("data_dir", "/data/local/tmp/kavi/")
        self.language = cfg.get("language", "vi")

    def _infer(self, item: EvalItem) -> tuple[str | None, str | None]:
        """Run Whisper ASR via QNN on-device inference.

        TODO: Implement via Android instrumented test runner (ADR-006):
        1. Host pushes manifest + audio to device once
        2. Android app loads manifest via ManifestReader
        3. For each item:
           a. Preprocess audio to mel spectrogram (CPU on device)
           b. Run encoder on NPU (QNN context binary)
           c. Run decoder loop on CPU (ORT or custom)
           d. Measure latency_ns, peak_rss_bytes
        4. Android app writes results JSON
        5. Host pulls results via ``adb pull``

        Until the Android runner is implemented, this stub raises NotImplementedError
        to make test failures explicit rather than silently producing empty results.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} is a stub. "
            f"On-device QNN inference via ADB is not yet implemented.\n"
            f"Model path: {self.model_path}\n"
            f"Device: {self.device_id or '(default ADB device)'}\n"
            f"Data dir: {self.data_dir}\n"
            f"Integration path: see bench/qnn/export_whisper_onnx.py for the ONNX "
            f"export, then use bench/qnn/convert_to_qnn.sh for context binary "
            f"conversion. Push artifacts to device and run via qnn-net-run."
        )
