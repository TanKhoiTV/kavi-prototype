# QNN Model Artifacts

This directory holds the QAIRT / QNN artifacts for on-device inference on the
**Snapdragon 8 Gen 2 (HTP v73)** target, pinned to **QAIRT SDK 2.31.0.250130**.

## What's here

| Model | Format | Source | Status |
| --- | --- | --- | --- |
| **Whisper-Small-Quantized** | QNN context binary (w8a16) | Qualcomm AI Hub (`qualcomm/Whisper-Small-Quantized`) | Manual conversion required — see below |
| **PiperTTS-EN** | QNN context binary | Qualcomm AI Hub (`qualcomm/PiperTTS-EN`) | Manual conversion required — see below |
| **Opus-MT vi↔en** | ONNX → QNN context binary | Helsinki-NLP via Optimum export | Must export + convert locally |

## Pre-built model availability

### Whisper-Small-Quantized

- **HuggingFace:** <https://huggingface.co/qualcomm/Whisper-Small-Quantized>
- **AI Hub release assets:** QNN context binaries exist for 8 Gen 3 / 8 Elite /
  7 Gen 4 / X Elite, built with QAIRT 2.45.0.260326154327 (S3 download URLs in
  `release_assets.json`).
- **SD 8 Gen 2 (HTP v73):** No pre-built binary. Must compile from ONNX using
  QAIRT SDK 2.31.0.250130.

### PiperTTS-EN

- **HuggingFace:** <https://huggingface.co/qualcomm/PiperTTS-EN>
- **AI Hub release assets:** `voice_ai` format only (float, not QNN context
  binary). Available for 8 Gen 1 / 8 Gen 3 / 8 Elite.
- **SD 8 Gen 2 (HTP v73):** No pre-built binary. Must convert from the original
  Piper ONNX after deterministic-decoder surgery (see Phase 4 plan §3.3 / §10).

## Manual download URLs (for reference)

The AI Hub S3 URLs are public and can be downloaded without authentication.
They are **not pinned** and may change with new releases.

**Whisper-Small-Quantized (w8a16, 8 Gen 3 — for reference only):**

```
https://qaihub-public-assets.s3.us-west-2.amazonaws.com/qai-hub-models/models/whisper_small_quantized/releases/v0.58.0/whisper_small_quantized-qnn_context_binary-w8a16-qualcomm_snapdragon_8gen3.zip
```

These binaries are built with QAIRT 2.45.0 — **not compatible** with our
SD 8 Gen 2 (HTP v73) runtime pinned to QAIRT 2.31.0. They serve as a reference for
the expected artifact format.

## QAIRT SDK setup

### Prerequisites

- **Host OS:** Ubuntu 22.04 x86_64 (or WSL2) — the QAIRT SDK converters are
  Linux x86_64 binaries.
- **SDK version:** 2.31.0.250130 — **must match** the device `qnn-2.31` / HTP v73
  runtime. Do NOT upgrade.
- **Python:** 3.10 (auto-managed by `scripts/qairt-env.sh`)
- **NDK:** Android NDK r26c (26.1.10909125)

### Installation (recommended)

1. Download QAIRT SDK 2.31.0.250130 from Qualcomm's portal:
   <https://account.qualcomm.com/> (requires free Qualcomm ID)

2. Extract to `~/Qualcomm/AIStack/QAIRT/`:

   ```bash
   mkdir -p ~/Qualcomm/AIStack/QAIRT/
   tar xzf qairt-sdk-2.31.0.250130.tar.gz -C ~/Qualcomm/AIStack/QAIRT/
   ```

3. Source the environment helper (auto-creates `.venv-qairt/` on first run):

   ```bash
   source scripts/qairt-env.sh
   ```

   This sets `QAIRT_SDK_ROOT`, activates the converter venv, configures
   `LD_LIBRARY_PATH` and `PYTHONPATH`, and verifies all converter binaries.

### Installation (manual)

If you prefer manual setup:

1. Set SDK path: `export QAIRT_SDK_ROOT=/path/to/2.31.0.250130`
2. Create venv: `uv venv --python 3.10 .venv-qairt`
3. Install deps: `uv pip install --python .venv-qairt onnx==1.16.1 onnxruntime==1.17.1 'numpy<2' onnx-simplifier scipy lxml absl-py pandas pyyaml`
4. Source envsetup: `source $QAIRT_SDK_ROOT/bin/envsetup.sh`
5. Set ANDROID_NDK_ROOT: `export ANDROID_NDK_ROOT=/path/to/android-ndk-r26c`

## Conversion pipeline

### Whisper-Small → QNN

```bash
# Step 1: Export Whisper Small to ONNX (if not using AI Hub source)
# See docs/reference/phase-4-qnn-plan.md for the export approach

# Step 2: Convert ONNX to QNN graph
./bench/qnn/convert_to_qnn.sh \
    --onnx models/whisper/encoder_model.onnx \
    --input-name input_features \
    --input-dims "1,80,3000" \
    --input-list models/qnn/whisper_calib_input_list.txt \
    --output-dir models/qnn/whisper-small/ \
    --name whisper_small_encoder
```

### Opus-MT → ONNX → QNN

```bash
# Step 1: Export Opus-MT to ONNX (vi→en)
uv run python -m bench.qnn.export_opusmt_onnx \
    --model Helsinki-NLP/opus-mt-vi-en \
    --output models/qnn/opus-mt-vi-en/

# Step 2: Convert each sub-model
for sub in encoder decoder; do
    ./bench/qnn/convert_to_qnn.sh \
        --onnx "models/qnn/opus-mt-vi-en/${sub}_model.onnx" \
        --input-name input_ids \
        --input-dims "1,128" \
        --input-list models/qnn/opusmt_calib_input_list.txt \
        --output-dir "models/qnn/opus-mt-vi-en/${sub}/" \
        --name "opus_mt_vi_en_${sub}"
done
```

### Piper → QNN

Piper conversion requires deterministic-decoder surgery before the ONNX
conversion (see `docs/reference/phase-4-qnn-plan.md` §3.3 / §10). After patching:

```bash
./bench/qnn/convert_to_qnn.sh \
    --onnx models/piper/en_US-lessac-medium_patched.onnx \
    --input-name input \
    --input-dims "1,128,256" \
    --output-dir models/qnn/piper/ \
    --name piper_tts_en
```

## Verification

### On-device (qnn-net-run)

After deploying the context binary to the device:

```bash
# Push artifacts
adb push models/qnn/whisper-small/ctx/whisper_small_encoder_v73.bin /data/local/tmp/
adb push $QAIRT_SDK_ROOT/lib/aarch64-android/libQnnHtp.so /data/local/tmp/
adb push input_features.raw /data/local/tmp/

# Run inference
adb shell "
export LD_LIBRARY_PATH=/data/local/tmp
qnn-net-run \
    --model whisper_small_encoder_v73.bin \
    --backend /data/local/tmp/libQnnHtp.so \
    --input_list input_features:input_features.raw
"
```

### Accuracy validation

1. Save the FP32 reference output from the ONNX model:

   ```python
   import numpy as np

   np.save("ref_encoder_out.npy", ort_output[0])
   ```

2. Compare on-device output:
   - Pull the HTP output from the device (`adb pull`)
   - Compute max absolute difference against the FP32 reference
   - Expected: small error (~int16 step) due to quantized inference

## SDK version notes

| Component | Pinned Version | Notes |
| --- | --- | --- |
| QAIRT SDK | 2.31.0.250130 | Device runtime is `qnn-2.31` / HTP v73 |
| Android NDK | r26c (26.1.10909125) | Matches `archive/`/`sdk.yaml` |
| onnx | 1.16.1 | In converter venv |
| onnxruntime | 1.17.1 | In converter venv |
| Python | 3.10 | Converter venv only |

## Key constraints

- **No dynamic shapes:** All input/output dimensions must be fixed. Autoregressive
  decoders need static padding + masking.
- **w8a16 quantization:** HTP only executes quantized graphs. Use int8 weights /
  int16 activations for transformer accuracy.
- **Piper RandomNormalLike:** Must be replaced with deterministic zero-noise
  before conversion (see Phase 4 plan).
- **Opus-MT calibration:** Use real FLEURS VI/EN token sequences for calibration,
  not synthetic ranges.
