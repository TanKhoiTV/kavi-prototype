"""QNN Opus-MT MT adapter — stub for on-device inference via ADB/bridge.

This adapter is a placeholder for the Phase-4 on-device QNN benchmark runner.
The actual QNN inference runs on a Snapdragon 8 Gen 2 (HTP v73) via the
Qualcomm AI Runtime. This host-side stub defines the interface and will
eventually:

1. Push the context binary + tokenised input to the device via ADB
2. Run ``qnn-net-run`` for encoder and decoder
3. Pull the output token sequence back and detokenise on host

Integration path (when implemented):
    - Pre-requisite model artifacts in ``models/qnn/opus-mt-vi-en/``:
      encoder_htp_v73.bin, decoder_htp_v73.bin
    - Tokenizers in ``models/opus-mt-vi-en-src/`` (SentencePiece)
    - ADB device detected via ``adb devices``
    - Host encodes source text to token IDs, pushes as raw int32
    - Device runs encoder + autoregressive decoder, returns token IDs
    - Host detokenises to target text
"""

from __future__ import annotations

from ..adapters import Candidate
from ..schema import EvalItem


class QnnOpusMTMTCandidate(Candidate):
    """QNN Opus-MT vi<->en candidate (HTP v73, w8a16 quantized).

    Parameters
    ----------
    model_path : str | None
        Path to the directory containing the QNN context binaries and metadata.
        Expected structure::

            {model_path}/
            ├── encoder_htp_v73.bin       # QNN context binary (encoder)
            ├── decoder_htp_v73.bin        # QNN context binary (decoder)
            └── input_list.txt             # Calibration input list

    config : dict | None
        Recognized keys:
        - ``device_id`` (str, default ``""``): ADB device serial.
        - ``data_dir`` (str, default ``"/data/local/tmp/kavi/"``): temp dir on device.
        - ``src_spm`` (str): path to source SentencePiece model (defaults to
          ``models/opus-mt-vi-en-src/source.spm``).
        - ``tgt_spm`` (str): path to target SentencePiece model (defaults to
          ``models/opus-mt-vi-en-src/target.spm``).
        - ``max_length`` (int, default ``256``): max decode length.
    """

    stage = "MT"
    id = "qnn-opus-mt-vi-en-htp-v73"

    def __init__(
        self, model_path: str | None = None, config: dict | None = None
    ) -> None:
        self.model_path = model_path
        cfg = config or {}
        self.device_id = cfg.get("device_id", "")
        self.data_dir = cfg.get("data_dir", "/data/local/tmp/kavi/")
        self.src_spm_path = cfg.get("src_spm")
        self.tgt_spm_path = cfg.get("tgt_spm")
        self.max_length = cfg.get("max_length", 256)

    def _infer(self, item: EvalItem) -> tuple[str | None, str | None]:
        """Run Opus-MT translation via QNN on-device inference.

        TODO: Implement ADB bridge:
        1. Load SentencePiece tokeniser (source) on host
        2. Encode source text to token IDs (int32 array)
        3. ``adb -s {device_id} shell mkdir -p {data_dir}``
        4. ``adb -s {device_id} push {input_tokens.raw} {data_dir}``
        5. ``adb -s {device_id} shell qnn-net-run --model {encoder_ctx} ...``
        6. Pull encoder output, run decoder loop:
           - For each decode step: push decoder input, run qnn-net-run, pull output
        7. After EOS or max_length: detokenise on host via target SPM
        8. Return translated text

        Until the ADB bridge is implemented, this stub raises NotImplementedError
        to make test failures explicit rather than silently producing empty results.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} is a stub. "
            f"On-device QNN inference via ADB is not yet implemented.\n"
            f"Model path: {self.model_path}\n"
            f"Device: {self.device_id or '(default ADB device)'}\n"
            f"Data dir: {self.data_dir}\n"
            f"Integration path: see bench/qnn/export_opusmt_onnx.py for the ONNX "
            f"export, then use bench/qnn/convert_to_qnn.sh for context binary "
            f"conversion. Push artifacts to device and run via qnn-net-run."
        )
