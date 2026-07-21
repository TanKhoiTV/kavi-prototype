"""QNN Piper TTS adapter — stub for on-device inference via ADB/bridge.

This adapter is a placeholder for the Phase-4 on-device QNN benchmark runner.
The actual QNN inference runs on a Snapdragon 8 Gen 2 (HTP v73) via the
Qualcomm AI Runtime. This host-side stub defines the interface and will
eventually:

1. Push the context binary + input phoneme IDs to the device via ADB
2. Run ``qnn-net-run`` for the Piper encoder (NPU offload)
3. Run the deterministic decoder (may need CPU fallback due to loop)
4. Pull the raw audio output back and save as WAV

Integration path (when implemented):
    - Pre-requisite model artifacts in ``models/qnn/piper-en/``:
      piper_encoder_htp_v73.bin (NPU), piper_decoder (CPU fallback)
    - Piper ONNX must first be patched via ``bench/qnn/patch_piper_onnx.py``
      to remove RandomNormalLike and fix output length
    - Input text is converted to phoneme IDs on host using Piper's espeak-ng
    - ADB device detected via ``adb devices``
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
        - ``device_id`` (str, default ``""``): ADB device serial.
        - ``data_dir`` (str, default ``"/data/local/tmp/kavi/"``): temp dir on device.
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
        self.device_id = cfg.get("device_id", "")
        self.data_dir = cfg.get("data_dir", "/data/local/tmp/kavi/")
        self.voice_path = cfg.get("voice_path", "voices/en_US-lessac-medium.onnx")
        self.sample_rate = cfg.get("sample_rate", 22050)

    def _infer(self, item: EvalItem) -> tuple[str | None, str | None]:
        """Run Piper TTS via QNN on-device inference.

        TODO: Implement ADB bridge:
        1. Load Piper voice config to get phoneme-to-ID mapping + espeak-ng voice
        2. Convert input text to phoneme IDs on host
        3. ``adb -s {device_id} shell mkdir -p {data_dir}``
        4. ``adb -s {device_id} push {phoneme_ids.raw} {data_dir}``
        5. Run encoder: ``adb -s {device_id} shell qnn-net-run --model {encoder_ctx}``
        6. Pull encoder output (mel spectrogram frames)
        7. Run decoder split (CPU fallback on device or host):
           - Resample + inverse mel -> audio waveform
        8. Push resulting audio to host, save as WAV
        9. Return (None, output_audio_path)

        Until the ADB bridge is implemented, this stub raises NotImplementedError
        to make test failures explicit rather than silently producing empty results.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} is a stub. "
            f"On-device QNN inference via ADB is not yet implemented.\n"
            f"Model path: {self.model_path}\n"
            f"Device: {self.device_id or '(default ADB device)'}\n"
            f"Data dir: {self.data_dir}\n"
            f"Integration path: run bench/qnn/patch_piper_onnx.py first for "
            f"deterministic-decoder ONNX, then use bench/qnn/convert_to_qnn.sh "
            f"for context binary conversion. Push artifacts to device and run "
            f"via qnn-net-run."
        )
