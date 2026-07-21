"""QNN Whisper ASR adapter — stub for on-device inference via ADB/bridge.

This adapter is a placeholder for the Phase-4 on-device QNN benchmark runner.
The actual QNN inference runs on a Snapdragon 8 Gen 2 (HTP v73) via the
Qualcomm AI Runtime. This host-side stub defines the interface and will
eventually:

1. Push the context binary + input audio to the device via ADB
2. Run ``qnn-net-run`` with the Whisper decoder loop (CPU fallback)
3. Pull the output text back

Integration path (when implemented):
    - Pre-requisite model artifacts in ``models/qnn/whisper-small/``:
      encoder_htp_v73.bin, decoder_htp_v73.bin, input_list.txt
    - ADB device detected via ``adb devices``
    - Input audio is pushed to ``/data/local/tmp/kavi/``
    - Output text is pulled back and returned as ``output_text``
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

        TODO: Implement ADB bridge:
        1. ``adb -s {device_id} shell mkdir -p {data_dir}``
        2. ``adb -s {device_id} push {input_audio} {data_dir}``
        3. Convert audio to mel spectrogram via a host-side Whisper preprocessor
        4. Push mel ``.raw`` to device
        5. ``adb -s {device_id} shell qnn-net-run --model {ctx_bin} ...``
        6. Pull output ``last_hidden_state.raw``
        7. Run decoder loop (autoregressive; likely CPU fallback on device)
        8. Return transcribed text

        Until the ADB bridge is implemented, this stub raises NotImplementedError
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
