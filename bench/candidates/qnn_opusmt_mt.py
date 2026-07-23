"""QNN Opus-MT MT adapter — stub for on-device inference.

This adapter is a placeholder for the Phase-4 on-device QNN benchmark runner.
The actual QNN inference runs on a Snapdragon 8 Gen 2 (HTP v73) via the
Qualcomm AI Runtime. This host-side stub defines the interface and will
eventually:

1. Load context binary via ``QnnModelLoader`` (bundled in APK assets)
2. Encode source text to token IDs on host
3. Run encoder + autoregressive decoder on HTP v73
4. Detokenise output on host via target SentencePiece model
5. Return translated text

The on-device runner is an Android instrumented test / thin service that
reads ``eval_manifest_v1.json`` and executes candidates via
``com.kavi.app.runner`` (see ``android/app/src/main/java/com/kavi/app/runner/``).

Integration path (when implemented):
    - Pre-requisite model artifacts in ``models/qnn/opus-mt-vi-en/``:
      encoder_htp_v73.bin, decoder_htp_v73.bin
    - Tokenizers in ``models/opus-mt-vi-en-src/`` (SentencePiece)
    - Context binary bundled into APK assets
    - On-device runner loads and executes via ``QnnModelLoader``
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
        self.src_spm_path = cfg.get("src_spm")
        self.tgt_spm_path = cfg.get("tgt_spm")
        self.max_length = cfg.get("max_length", 256)

    def _infer(self, item: EvalItem) -> tuple[str | None, str | None]:
        """Run Opus-MT translation via QNN on-device inference.

        TODO: Implement Android instrumented test runner:
        1. Load context binary via ``QnnModelLoader``
        2. Encode source text to token IDs (host-side SentencePiece)
        3. Run encoder + autoregressive decoder on HTP v73
        4. Detokenise output on host via target SPM
        5. Return translated text

        Until the on-device runner is implemented, this stub raises
        NotImplementedError to make test failures explicit rather than
        silently producing empty results.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} is a stub. "
            f"On-device QNN inference is not yet implemented.\n"
            f"Model path: {self.model_path}\n"
            f"Integration path: convert ONNX to HTP v73 context binary, "
            f"bundle in APK assets, run via Android instrumented test runner "
            f"(see android/app/src/main/java/com/kavi/app/runner/)."
        )
