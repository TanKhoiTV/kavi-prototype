#!/usr/bin/env bash
# shellcheck disable=SC1091
#
# qairt-env.sh — QAIRT SDK environment helper
#
# Source this script to set up the environment for QAIRT 2.31.0.250130
# model conversion (qnn-onnx-converter, qnn-model-lib-generator,
# qnn-context-binary-generator).
#
# Usage:
#   source scripts/qairt-env.sh              # default /opt/qairt/2.31.0.250130
#   QAIRT_SDK_ROOT=/custom/path source scripts/qairt-env.sh
#
# This script:
#   - Sets QAIRT_SDK_ROOT (default /opt/qairt/2.31.0.250130 if unset)
#   - Sources $QAIRT_SDK_ROOT/bin/envsetup.sh (sets QNN_SDK_ROOT, SNPE_ROOT)
#   - Exports LD_LIBRARY_PATH for the SDK libs and converter venv
#   - Validates that key converter binaries are reachable
#   - Prints a verification summary

set -euo pipefail

# ---- Defaults ----
: "${QAIRT_SDK_ROOT:=/home/dmin/Qualcomm/AIStack/QAIRT/2.31.0.250130}"
export QAIRT_SDK_ROOT

# ---- Resolve real paths ----
QAIRT_SDK_ROOT="$(cd "$QAIRT_SDK_ROOT" 2>/dev/null && pwd)" || {
	echo "[qairt-env] ERROR: QAIRT_SDK_ROOT does not exist or is not a directory: $QAIRT_SDK_ROOT" >&2
	return 1 2>/dev/null || exit 1
}

# ---- Source SDK envsetup ----
ENVSETUP="$QAIRT_SDK_ROOT/bin/envsetup.sh"
if [[ -f "$ENVSETUP" ]]; then
	# SDK envsetup.sh uses unquoted ${PYTHONPATH} which fails under set -u
	# Temporarily disable nounset for the source call.
	# shellcheck source=/dev/null
	set +u
	source "$ENVSETUP"
	set -u
	echo "[qairt-env] Sourced $ENVSETUP"
else
	echo "[qairt-env] WARNING: $ENVSETUP not found — QNN_SDK_ROOT/SNPE_ROOT may not be set" >&2
fi

# ---- PYTHONPATH (SDK converter packages) ----
SDK_PYTHON="$QAIRT_SDK_ROOT/lib/python"
if [[ -d "$SDK_PYTHON" ]]; then
	export PYTHONPATH="${SDK_PYTHON}${PYTHONPATH:+:$PYTHONPATH}"
fi

# ---- LD_LIBRARY_PATH ----
# Add QAIRT SDK host libs
SDK_LIB="$QAIRT_SDK_ROOT/lib/x86_64-linux-clang"
if [[ -d "$SDK_LIB" ]]; then
	export LD_LIBRARY_PATH="${SDK_LIB}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

# Try to locate the converter venv libpython3.10 directory
# Common locations: $QAIRT_SDK_ROOT/../converters-venv/lib/python3.10/lib-dynload
# or directly adjacent
CONVERTER_VENV_LIB=""
for candidate in \
	"$QAIRT_SDK_ROOT/../converters-venv/lib/python3.10/lib-dynload" \
	"$QAIRT_SDK_ROOT/../qairt-converters/lib/python3.10/lib-dynload" \
	"/opt/qairt/converters-venv/lib/python3.10/lib-dynload" \
	"/home/dmin/venvs/qairt-converters/lib/python3.10/lib-dynload"; do
	candidate="$(cd "$(dirname "$candidate")" 2>/dev/null && pwd)/$(basename "$candidate")" || continue
	if [[ -d "$candidate" ]]; then
		CONVERTER_VENV_LIB="$(cd "$candidate" && pwd)"
		break
	fi
done

if [[ -n "$CONVERTER_VENV_LIB" ]]; then
	export LD_LIBRARY_PATH="${CONVERTER_VENV_LIB}:${LD_LIBRARY_PATH}"
	echo "[qairt-env] Added converter venv lib to LD_LIBRARY_PATH: $CONVERTER_VENV_LIB"
else
	echo "[qairt-env] WARNING: Could not locate converter venv libpython3.10 directory" >&2
	echo "[qairt-env] Set LD_LIBRARY_PATH manually if qnn-onnx-converter fails with import errors" >&2
fi

# ---- Validation ----
BIN_DIR="$QAIRT_SDK_ROOT/bin/x86_64-linux-clang"
echo ""
echo "============================================"
echo " QAIRT Environment — Verification"
echo "============================================"
echo " QAIRT_SDK_ROOT : $QAIRT_SDK_ROOT"
echo " QNN_SDK_ROOT   : ${QNN_SDK_ROOT:-<not set>}"
echo " SNPE_ROOT      : ${SNPE_ROOT:-<not set>}"
echo " ANDROID_NDK_ROOT: ${ANDROID_NDK_ROOT:-<not set>}"

# Check key converters
converters=(qnn-onnx-converter qnn-model-lib-generator qnn-context-binary-generator)
all_found=true
for tool in "${converters[@]}"; do
	tool_path="$BIN_DIR/$tool"
	if [[ -x "$tool_path" ]]; then
		echo " $(printf '%25s' "$tool") : $tool_path  ✅"
	else
		echo " $(printf '%25s' "$tool") : NOT FOUND  ❌"
		all_found=false
	fi
done

echo " LD_LIBRARY_PATH: ${LD_LIBRARY_PATH:-<empty>}"
echo "============================================"

if $all_found; then
	echo "[qairt-env] All key converters are available."
else
	echo "[qairt-env] WARNING: Some converters are missing. Check QAIRT_SDK_ROOT." >&2
fi
