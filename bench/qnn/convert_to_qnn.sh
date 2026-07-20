#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# QAIRT / QNN conversion wrapper — ONNX → HTP v73 context binary
#
# Converts a model from ONNX to a QNN HTP v73 context binary via the 3-step
# QAIRT pipeline:
#   1. qnn-onnx-converter        →  <model>.cpp (graph + net.json + CPU .bin)
#   2. qnn-model-lib-generator   →  model library (.so for aarch64-android)
#   3. qnn-context-binary-generator  →  HTP v73 context binary
#
# Prerequisites:
#   - QAIRT SDK 2.31.0.250130 installed at $QAIRT_SDK_ROOT
#   - ANDROID_NDK_ROOT set to NDK r26c (26.1.10909125) for model-lib build
#   - Python 3.10 venv (qairt-converters) with onnx 1.16.1, onnxruntime 1.17.1,
#     numpy<2, onnx-simplifier
#   - Ubuntu 22.04 or WSL2 (no GUI libraries needed)
#
# Usage:
#   ./bench/qnn/convert_to_qnn.sh \
#       --onnx models/qnn/opus-mt-vi-en/encoder_model.onnx \
#       --input-name input_ids \
#       --input-dims "1,128" \
#       --input-list /path/to/input_list.txt \
#       --output-dir models/qnn/opus-mt-vi-en/ctx \
#       --name opus_mt_vi_en_encoder
#
# Environment:
#   QAIRT_SDK_ROOT   – path to QAIRT SDK 2.31.0.250130 (required)
#   ANDROID_NDK_ROOT – path to Android NDK r26c (required for step 2)
#
# SDK version requirement:
#   Must be 2.31.0.250130 (= device qnn-2.31 / HTP v73).
#   Do NOT upgrade — ABI drift breaks on-device loading.
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── defaults ─────────────────────────────────────────────────────────────────

OUTPUT_DIR="."
NAME="model"
INPUT_LIST=""
INPUT_DIMS_OPT=()
QUANTIZE=true
SKIP_LIB=false
SKIP_CTX=false
VERBOSE=false

# ── helpers ──────────────────────────────────────────────────────────────────

die() { echo "[ERROR] $*" >&2; exit 1; }
info() { echo "[INFO] $*"; }

usage() {
    cat <<'USAGE'
Usage: convert_to_qnn.sh [OPTIONS]

Required:
  --onnx <path>           Path to the ONNX model file
  --input-name <name>     Name of the model's input tensor (repeatable)
  --input-dims <dims>     Input dimensions in ONNX format, e.g. "1,80,3000"
                          (repeatable, one per --input-name)
  --output-dir <dir>      Output directory for generated artifacts

Conversion options:
  --input-list <path>     Path to calibration input list (for quantization)
  --name <name>           Model name used in generated files (default: basename of ONNX)
  --no-quantize           Skip quantization (float conversion only)

Pipeline step options:
  --skip-lib              Skip model-lib generation (step 2)
  --skip-ctx              Skip context-binary generation (step 3)

Environment:
  QAIRT_SDK_ROOT          Path to QAIRT SDK 2.31.0.250130
  ANDROID_NDK_ROOT        Path to Android NDK r26c

Examples:
  # Basic conversion (no quantization, onnx input list)
  ./bench/qnn/convert_to_qnn.sh --onnx model.onnx \
      --input-name input_ids --input-dims "1,128" \
      --output-dir out/

  # Full pipeline with quantization
  ./bench/qnn/convert_to_qnn.sh --onnx encoder.onnx \
      --input-name input_features --input-dims "1,80,3000" \
      --input-list calibration_input_list.txt \
      --output-dir out/ --name whisper_encoder
USAGE
    exit 0
}

# ── parse arguments ──────────────────────────────────────────────────────────

ONNX=""
INPUT_NAMES=()
INPUT_DIMS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --onnx) ONNX="$2"; shift 2 ;;
        --input-name) INPUT_NAMES+=("$2"); shift 2 ;;
        --input-dims) INPUT_DIMS+=("$2"); shift 2 ;;
        --input-list) INPUT_LIST="$2"; shift 2 ;;
        --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
        --name) NAME="$2"; shift 2 ;;
        --no-quantize) QUANTIZE=false; shift ;;
        --skip-lib) SKIP_LIB=true; shift ;;
        --skip-ctx) SKIP_CTX=true; shift ;;
        --verbose) VERBOSE=true; shift ;;
        --help|-h) usage ;;
        *) die "Unknown option: $1 (use --help)" ;;
    esac
done

# Validate required arguments
[[ -z "$ONNX" ]] && die "--onnx is required"
[[ ! -f "$ONNX" ]] && die "ONNX file not found: $ONNX"
[[ ${#INPUT_NAMES[@]} -eq 0 ]] && die "At least one --input-name is required"
[[ ${#INPUT_DIMS[@]} -eq 0 ]] && die "At least one --input-dims is required"
[[ ${#INPUT_NAMES[@]} -ne ${#INPUT_DIMS[@]} ]] && die "Number of --input-name entries must match --input-dims entries"

# If NAME is not set explicitly, derive from ONNX basename
if [[ "$NAME" == "." ]]; then
    NAME=$(basename "$ONNX" .onnx)
fi

# Ensure output directory exists
mkdir -p "$OUTPUT_DIR"

# Validate SDK environment
[[ -z "${QAIRT_SDK_ROOT:-}" ]] && die "QAIRT_SDK_ROOT is not set. Point it to QAIRT SDK 2.31.0.250130"
QAIRT_SDK_ROOT="$(cd "$QAIRT_SDK_ROOT" && pwd)"
CONVERTER="$QAIRT_SDK_ROOT/bin/x86_64-linux-clang/qnn-onnx-converter"
MODEL_LIB_GEN="$QAIRT_SDK_ROOT/bin/x86_64-linux-clang/qnn-model-lib-generator"
CTX_BIN_GEN="$QAIRT_SDK_ROOT/bin/x86_64-linux-clang/qnn-context-binary-generator"

for tool in "$CONVERTER" "$MODEL_LIB_GEN" "$CTX_BIN_GEN"; do
    [[ -x "$tool" ]] || die "Tool not found or not executable: $tool (check QAIRT_SDK_ROOT)"
done

if [[ -n "${ANDROID_NDK_ROOT:-}" ]]; then
    ANDROID_NDK_ROOT="$(cd "$ANDROID_NDK_ROOT" && pwd)"
fi

info "=== QAIRT Conversion Pipeline ==="
info "ONNX:     $ONNX"
info "Name:     $NAME"
info "Output:   $OUTPUT_DIR"
info "SDK:      $QAIRT_SDK_ROOT"
[[ -n "${ANDROID_NDK_ROOT:-}" ]] && info "NDK:      $ANDROID_NDK_ROOT"
info ""

# ── Step 1: ONNX → .cpp (graph) ─────────────────────────────────────────────

CPP_OUT="$OUTPUT_DIR/$NAME"

info "Step 1: qnn-onnx-converter → $CPP_OUT.cpp"

INPUT_DIM_FLAGS=()
for i in "${!INPUT_NAMES[@]}"; do
    INPUT_DIM_FLAGS+=(--input_dim "${INPUT_NAMES[$i]}" "${INPUT_DIMS[$i]}")
done

QUANT_FLAGS=()
if $QUANTIZE; then
    QUANT_FLAGS=(
        --param_quantizer tf
        --act_quantizer tf
        --weights_bitwidth 8
        --act_bitwidth 16
    )
    if [[ -n "$INPUT_LIST" ]]; then
        QUANT_FLAGS+=(--input_list "$INPUT_LIST")
    else
        info "  WARNING: No --input-list provided; quantizer will use fallback ranges."
        info "  For best accuracy, supply real calibration data via --input-list"
    fi
fi

set -x
"$CONVERTER" \
    --input_network "$ONNX" \
    --output_path "$CPP_OUT" \
    "${INPUT_DIM_FLAGS[@]}" \
    "${QUANT_FLAGS[@]}"
{ set +x; } 2>/dev/null

# Verify outputs
CPP_FILE="$CPP_OUT.cpp"
NET_JSON="$CPP_OUT"_net.json
[[ -f "$CPP_FILE" ]] || die "Step 1 failed: $CPP_FILE not generated"
[[ -f "$NET_JSON" ]] || die "Step 1 failed: $NET_JSON not generated"
info "  ✓ $CPP_FILE"
info "  ✓ $NET_JSON"
info ""

# ── Step 2: .cpp → model library (.so) ──────────────────────────────────────

if $SKIP_LIB; then
    info "Step 2: SKIPPED (--skip-lib)"
else
    LIB_OUT="$OUTPUT_DIR/${NAME}_libs"
    info "Step 2: qnn-model-lib-generator → $LIB_OUT/aarch64-android/lib${NAME}.so"

    if [[ -z "${ANDROID_NDK_ROOT:-}" ]]; then
        info "  WARNING: ANDROID_NDK_ROOT not set; attempting build with system toolchain."
        info "  Set ANDROID_NDK_ROOT=path/to/ndk-r26c for correct aarch64-android build."
    fi

    set -x
    "$MODEL_LIB_GEN" \
        -c "$CPP_FILE" \
        -t aarch64-android \
        -n "$NAME" \
        -o "$LIB_OUT"
    { set +x; } 2>/dev/null

    LIB_SO="$LIB_OUT/aarch64-android/lib${NAME}.so"
    [[ -f "$LIB_SO" ]] || die "Step 2 failed: $LIB_SO not generated"
    info "  ✓ $LIB_SO"
    info ""
fi

# ── Step 3: model lib → HTP v73 context binary ──────────────────────────────

if $SKIP_CTX; then
    info "Step 3: SKIPPED (--skip-ctx)"
else
    CTX_OUT="$OUTPUT_DIR/${NAME}_ctx"
    mkdir -p "$CTX_OUT"

    # Use the generated .so from step 2, or accept an external one
    if [[ -f "$LIB_SO" ]]; then
        MODEL_SO="$LIB_SO"
    else
        die "No model .so available for context binary generation (run step 2 or provide one)"
    fi

    HTP_BACKEND="$QAIRT_SDK_ROOT/lib/aarch64-android/libQnnHtp.so"
    [[ -f "$HTP_BACKEND" ]] || die "HTP backend not found: $HTP_BACKEND"

    CTX_BIN="$CTX_OUT/${NAME}_v73.bin"

    info "Step 3: qnn-context-binary-generator → $CTX_BIN"

    set -x
    "$CTX_BIN_GEN" \
        --model "$MODEL_SO" \
        --backend "$HTP_BACKEND" \
        --htp_arch v73 \
        --binary_file "$CTX_BIN" \
        --output_dir "$CTX_OUT"
    { set +x; } 2>/dev/null

    [[ -f "$CTX_BIN" ]] || die "Step 3 failed: $CTX_BIN not generated"
    info "  ✓ $CTX_BIN"
    info ""
fi

# ── summary ──────────────────────────────────────────────────────────────────

info "=== Conversion complete ==="
info "Artifacts in: $OUTPUT_DIR"
info ""
info "Generated files:"
ls -lh "$OUTPUT_DIR"/"$NAME"* 2>/dev/null || true
if [[ -d "${LIB_OUT:-}" ]]; then
    ls -lh "$LIB_OUT"/aarch64-android/ 2>/dev/null || true
fi
if [[ -d "${CTX_OUT:-}" ]]; then
    ls -lh "$CTX_OUT"/ 2>/dev/null || true
fi
info ""
info "On-device verification:"
info "  qnn-net-run \\"
info "    --model $MODEL_SO \\"
info "    --backend $HTP_BACKEND \\"
info "    --binary_file $CTX_BIN \\"
info "    --input_list <input_name>:<input_data>.raw"
