# NDK Conversion Runbook — Opus-MT Encoder (HTP v73 Context Binary)

> **Audience:** The person handling the NDK-gated part of the QNN conversion pipeline.
> **Scope:** Convert the already-exported Opus-MT vi→en encoder ONNX into an HTP v73
> context binary for the `kavi-android` app. This is the **only** QNN artifact on
> the v1 path — Whisper (ASR) and Piper (TTS) are CPU-only per ADR-008/009.
> **Pre-requisite reading:** `docs/reference/phase-4-qnn-plan.md` (full conversion spec),
> ADR-007 (Decision 8: QNN bundling), ADR-011 (asset provenance).

---

## 1. What you are producing

| Artifact | Format | Consumed by |
|----------|--------|-------------|
| `libopus_mt_vi_en_encoder.so` | aarch64-android shared lib | `qnn-context-binary-generator` (step 3) |
| `opus_mt_vi_en_encoder_v73.bin` | HTP v73 context binary | On-device `QnnGraph_execute` at runtime |

Both artifacts are committed **inside `kavi-android`** (`app/src/main/assets/`) with
a `SHA256SUMS` manifest entry (ADR-011). The host-side `prototype/models/qnn/*`
outputs are gitignored — never commit them here.

---

## 2. Environment set-up

### 2.1 Android NDK r26c (26.1.10909125)

The model-lib generator (`qnn-model-lib-generator`) cross-compiles C++ to
aarch64-android and needs the NDK toolchain.

```bash
# Option A — Android Studio: SDK Manager → SDK Tools → NDK (Side by side) → 26.1.10909125
# Option B — sdkmanager CLI:
sdkmanager --install "ndk;26.1.10909125"

# Set and export:
export ANDROID_NDK_ROOT=/home/dmin/Android/Sdk/ndk/26.1.10909125
```

**Pin this version.** The HTP v73 context binary is cross-compiled against the NDK
toolchain that must be reproducible — a different NDK produces a different `.so` ABI.

### 2.2 QAIRT SDK 2.31.0.250130

Already installed at `/home/dmin/Qualcomm/AIStack/QAIRT/2.31.0.250130`. Do **not**
upgrade — it must match the device's `qnn-2.31` / HTP v73 runtime.

```bash
export QAIRT_SDK_ROOT=/home/dmin/Qualcomm/AIStack/QAIRT/2.31.0.250130
```

### 2.3 Converter venv (Python 3.10)

The `scripts/qairt-env.sh` helper creates `.venv-qairt/` on first run and activates it:

```bash
source scripts/qairt-env.sh
```

This sets `QAIRT_SDK_ROOT`, `QNN_SDK_ROOT`, `SNPE_ROOT`, `LD_LIBRARY_PATH`,
`PYTHONPATH`, and creates the venv with the pinned converter deps
(`onnx==1.16.1`, `onnxruntime==1.17.1`, `numpy<2`, `onnx-simplifier`, …).

The venv **must** be Python 3.10 — the SDK's compiled `.so` files link against
`libpython3.10.so.1.0` and are ABI-incompatible with 3.11+.

---

## 3. What is already done (do not redo)

Step 1 of the pipeline (ONNX → `.cpp` + `_net.json` + `.bin`) has already been run
for the Opus-MT encoder:

```text
models/qnn/opus-mt-vi-en/encoder/
├── opus_mt_vi_en_encoder.cpp       ← graph source (step 1 output)
├── opus_mt_vi_en_encoder.bin       ← QNN_CPU calibration artifact (step 1 output)
└── opus_mt_vi_en_encoder_net.json  ← network descriptor (step 1 output)
```

The source ONNX is at `models/qnn/opus-mt-vi-en/opus-mt-vi-en/encoder_model.onnx`
(186 MB). Calibration data is in `models/qnn/opusmt-calib/` (32 items) with the
input list at `models/qnn/opusmt_input_list.txt`.

The encoder's input tensors are: `input_ids` `[1,128]` and `attention_mask` `[1,128]`.
Output: `last_hidden_state`. (All float32 → quantized w8a16 by the converter.)

---

## 4. Run steps 2–3

The `convert_to_qnn.sh` wrapper orchestrates the full pipeline. Because step 1
outputs already exist, you can start from step 2 with `--skip-lib` not set (steps
2 and 3 run; step 1 is skipped automatically when the `.cpp` is present — or run
the full pipeline; it is idempotent):

```bash
# Ensure the env is active (§2)
source scripts/qairt-env.sh
export ANDROID_NDK_ROOT=/home/dmin/Android/Sdk/ndk/26.1.10909125

./bench/qnn/convert_to_qnn.sh \
    --onnx models/qnn/opus-mt-vi-en/opus-mt-vi-en/encoder_model.onnx \
    --input-name input_ids --input-dims "1,128" \
    --input-name attention_mask --input-dims "1,128" \
    --input-list models/qnn/opusmt_input_list.txt \
    --output-dir models/qnn/opus-mt-vi-en/ctx \
    --name opus_mt_vi_en_encoder
```

### What the wrapper does

| Step | Tool | Output |
| ------ | ------ | -------- |
| 1 | `qnn-onnx-converter` | `.cpp` + `_net.json` + `.bin` (already present) |
| 2 | `qnn-model-lib-generator` | `ctx/opus_mt_vi_en_encoder_libs/aarch64-android/libopus_mt_vi_en_encoder.so` |
| 3 | `qnn-context-binary-generator` | `ctx/opus_mt_vi_en_encoder_ctx/opus_mt_vi_en_encoder_v73.bin` |

### Step 2 in detail (NDK-gated)

```bash
qnn-model-lib-generator \
    -c models/qnn/opus-mt-vi-en/encoder/opus_mt_vi_en_encoder \
    -t aarch64-android \
    -n opus_mt_vi_en_encoder \
    -o models/qnn/opus-mt-vi-en/ctx/opus_mt_vi_en_encoder_libs
```

**`-n` is required** — without it the `.so` defaults to `libqnn_model.so` and
every downstream path breaks.

### Step 3 in detail (context binary)

```bash
qnn-context-binary-generator \
    --model models/qnn/opus-mt-vi-en/ctx/opus_mt_vi_en_encoder_libs/aarch64-android/libopus_mt_vi_en_encoder.so \
    --backend $QAIRT_SDK_ROOT/lib/aarch64-android/libQnnHtp.so \
    --htp_arch v73 \
    --binary_file models/qnn/opus-mt-vi-en/ctx/opus_mt_vi_en_encoder_ctx/opus_mt_vi_en_encoder_v73.bin \
    --output_dir models/qnn/opus-mt-vi-en/ctx/opus_mt_vi_en_encoder_ctx
```

`--backend` needs the **full path** to `libQnnHtp.so` — a bare filename will not
resolve. `--htp_arch v73` is accepted only with `--model <compiled .so>`.

---

## 5. Verify the output

Expected artifacts after success:

```text
models/qnn/opus-mt-vi-en/ctx/
├── opus_mt_vi_en_encoder_libs/
│   └── aarch64-android/
│       └── libopus_mt_vi_en_encoder.so        ← model library
└── opus_mt_vi_en_encoder_ctx/
    ├── opus_mt_vi_en_encoder_v73.bin          ← HTP v73 context binary
    └── ...                                    ← ancillary outputs
```

Sanity checks:

```bash
# 1. The .so is aarch64
file models/qnn/opus-mt-vi-en/ctx/*/aarch64-android/*.so
# → ELF 64-bit LSB shared object, ARM aarch64

# 2. The context binary is non-empty
ls -lh models/qnn/opus-mt-vi-en/ctx/*_ctx/*.bin

# 3. The context binary targets v73
# (qnn-context-binary-generator has no --info flag; the verification is on-device — see §7)
```

---

## 6. Deliver into kavi-android (ADR-011)

Per ADR-011, the context binary and model `.so` are committed **inside the
`kavi-android` submodule**, never in `prototype/models/qnn/*` (which is gitignored).

```bash
cd android  # kavi-android submodule

# Copy artifacts into assets
mkdir -p app/src/main/assets/models/opus-mt-vi-en-encoder
cp ../models/qnn/opus-mt-vi-en/ctx/opus_mt_vi_en_encoder_ctx/opus_mt_vi_en_encoder_v73.bin \
   app/src/main/assets/models/opus-mt-vi-en-encoder/
cp ../models/qnn/opus-mt-vi-en/ctx/*/aarch64-android/libopus_mt_vi_en_encoder.so \
   app/src/main/assets/models/opus-mt-vi-en-encoder/

# Generate / update SHA256SUMS manifest
cd app/src/main/assets && sha256sum models/opus-mt-vi-en-encoder/* >> SHA256SUMS

# Commit inside the submodule
git add -A app/src/main/assets/
git commit -m "feat(android): add Opus-MT encoder HTP v73 context binary + model lib"

# Bump the pointer in the parent repo
cd ../..  # back to kavi-prototype
git add android
git commit -m "chore: bump kavi-android with Opus-MT encoder QNN artifacts"
```

---

## 7. On-device verification (after Build D)

The final verification happens on the Meizu 21 Note (SD8G2, HTP v73) in Build D of
the Kotlin/C++ implementation plan:

```bash
qnn-net-run \
    --model app/src/main/assets/models/opus-mt-vi-en-encoder/libopus_mt_vi_en_encoder.so \
    --backend /system/lib64/qnn/qnn-2.31/libQnnHtp.so \
    --binary_file app/src/main/assets/models/opus-mt-vi-en-encoder/opus_mt_vi_en_encoder_v73.bin \
    --input_list <calibration_input>.raw
```

Confirm profiling shows `BackendType=HTP` for the encoder layers (not `CPU`).

---

## 8. Troubleshooting

| Symptom | Cause | Fix |
| --------- | ------- | ----- |
| `libpython3.10.so.1.0: cannot open` | Wrong Python in venv | Recreate with `uv venv --python 3.10` |
| `qnn-model-lib-generator: command not found` | `ANDROID_NDK_ROOT` not set | `export ANDROID_NDK_ROOT=...` |
| `HTP backend not found` | QAIRT SDK path wrong or `libQnnHtp.so` missing | Check `$QAIRT_SDK_ROOT/lib/aarch64-android/` |
| `.so` is x86_64 instead of aarch64 | `-t aarch64-android` missing or NDK not in PATH | Add `-t aarch64-android` and ensure NDK clang is used |
| `Unused Arguments` from context binary generator | `--htp_arch v73` passed without a compiled `.so` | Run step 2 first; pass the `.so` path (not the `.onnx`) |
| `File not found: libQnnHtp.so` (bare name) | `--backend` needs full path | Use `$QAIRT_SDK_ROOT/lib/aarch64-android/libQnnHtp.so` |
| Version mismatch warning on device | SDK ≠ device runtime | Must be exactly `2.31.0.250130` (= `qnn-2.31` / HTP v73) |

---

## 9. References

- `docs/reference/phase-4-qnn-plan.md` — full QNN conversion spec (§2, §8, §9 are live)
- `docs/android-kotlin-cpp-implementation-plan.md` — Build D consumes this binary
- `docs/android-implementation-plan.md` — Milestone 3 (M3) delivers this
- ADR-007 — Decision 8 (QNN jniLibs roster + version lock)
- ADR-011 — Android asset provenance & delivery (where to commit)
- `bench/qnn/convert_to_qnn.sh` — conversion wrapper (read its --help for current flags)
- `scripts/qairt-env.sh` — environment helper
