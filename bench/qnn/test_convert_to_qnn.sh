#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# Dry-run test for bench/qnn/convert_to_qnn.sh — no Qualcomm SDK required.
#
# Covers the issue #116 P0 contract: the conversion wrapper must be able to emit
# *both* quantization arms (w8a16 / w8a8) from one code path, reject invalid
# bit-widths, and refuse to let one arm overwrite the other.
#
# The real qnn-* tools are replaced by stubs that record the flags they received
# and emit the artifacts the wrapper expects. That lets the flag plumbing,
# validation, build-stamp guard and artifact-naming be verified on any machine.
#
# Usage:  bash bench/qnn/test_convert_to_qnn.sh
# ──────────────────────────────────────────────────────────────────────────────

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONVERT="$REPO_ROOT/bench/qnn/convert_to_qnn.sh"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PASS=0
FAIL=0

ok() {
	PASS=$((PASS + 1))
	printf '  \033[32mPASS\033[0m  %s\n' "$1"
}
no() {
	FAIL=$((FAIL + 1))
	printf '  \033[31mFAIL\033[0m  %s\n' "$1"
	[[ $# -gt 1 ]] && printf '        %s\n' "$2"
}
section() { printf '\n\033[1m%s\033[0m\n' "$1"; }

sha_of() { sha256sum "$1" | awk '{print $1}'; }

# Assert that a command fails and its stderr/stdout mentions $2.
expect_die() {
	local desc="$1" needle="$2"
	shift 2
	local out
	out="$("$@" 2>&1)"
	if [[ $? -ne 0 ]]; then
		if [[ "$out" == *"$needle"* ]]; then
			ok "$desc"
		else
			no "$desc" "expected message containing: $needle | got: $(printf '%s' "$out" | head -c 200)"
		fi
	else
		no "$desc" "command unexpectedly succeeded"
	fi
}

expect_ok() {
	local desc="$1"
	shift
	local out
	if out="$("$@" 2>&1)"; then
		ok "$desc"
	else
		no "$desc" "$(printf '%s' "$out" | head -c 300)"
	fi
}

# ── fake toolchain ───────────────────────────────────────────────────────────

SDK="$TMP/fake-sdk"
BINDIR="$SDK/bin/x86_64-linux-clang"
mkdir -p "$BINDIR" "$SDK/lib/aarch64-android"
touch "$SDK/lib/aarch64-android/libQnnHtp.so"

# Stub qnn-onnx-converter: records the flags it was given, and writes a side file
# describing the quantization it "applied" so downstream stubs can propagate it.
cat >"$BINDIR/qnn-onnx-converter" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
out_path=""
prev=""
for arg in "$@"; do
	[[ "$prev" == "--output_path" ]] && out_path="$arg"
	prev="$arg"
done
[[ -n "$out_path" ]] || { echo "stub: --output_path missing" >&2; exit 1; }
quant=""; prev=""
for arg in "$@"; do
	case "$prev" in
	--param_quantizer | --act_quantizer | --weights_bitwidth | --act_bitwidth | --input_list)
		quant+="$prev=$arg "
		;;
	esac
	prev="$arg"
done
[[ -n "$quant" ]] || quant="(none)"
printf '%s\n' "$*" >>"${CONVERTER_LOG:-/dev/null}"
printf '%s\n' "$quant" >"${out_path}.quant"
: >"${out_path}.cpp"
: >"${out_path}_net.json"
STUB

# Stub qnn-model-lib-generator: -n <name> -o <dir> → <dir>/aarch64-android/lib<name>.so
cat >"$BINDIR/qnn-model-lib-generator" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
name=""; out=""
while [[ $# -gt 0 ]]; do
	case "$1" in
	-n) name="$2"; shift 2 ;;
	-o) out="$2"; shift 2 ;;
	*) shift ;;
	esac
done
[[ -n "$name" && -n "$out" ]] || { echo "stub: -n/-o missing" >&2; exit 1; }
mkdir -p "$out/aarch64-android"
: >"$out/aarch64-android/lib${name}.so"
STUB

# Stub qnn-context-binary-generator: embeds the quant stamp from step 1 into the
# .bin, so two arms that truly differ produce two different binaries.
# The stamp is located next to the model .so: <out>/<name>.quant, derived from
# --model <out>/aarch64-android/lib<name>.so.
cat >"$BINDIR/qnn-context-binary-generator" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
bin=""; model=""
while [[ $# -gt 0 ]]; do
	case "$1" in
	--binary_file) bin="$2"; shift 2 ;;
	--model) model="$2"; shift 2 ;;
	*) shift ;;
	esac
done
[[ -n "$bin" ]] || { echo "stub: --binary_file missing" >&2; exit 1; }
printf 'QNNCTXBIN\n' >"$bin"
# Propagate the step-1 quant stamp so the two A/B arms yield different bytes.
# Candidates: <out>/<name>.quant (step-1 dir) or its parent (when the .so lives
# under <out>/<name>_libs/aarch64-android/).
if [[ -n "$model" ]]; then
	name="${model##*/lib}"; name="${name%.so}"
	libdir="$(dirname "$(dirname "$model")")"
	for cand in "$libdir/$name.quant" "$(dirname "$libdir")/$name.quant"; do
		if [[ -f "$cand" ]]; then cat "$cand" >>"$bin"; break; fi
	done
fi
exit 0
STUB

chmod +x "$BINDIR"/*

# ── fixtures ─────────────────────────────────────────────────────────────────

ONNX="$TMP/encoder_model.onnx"
: >"$ONNX"
CALIB="$TMP/opusmt_input_list.txt"
for i in $(seq 1 8); do echo "$TMP/calib_$i.raw" >>"$CALIB"; done
CONVERTER_LOG="$TMP/converter.log"
: >"$CONVERTER_LOG"
export CONVERTER_LOG

run_convert() {
	QAIRT_SDK_ROOT="$SDK" ANDROID_NDK_ROOT="" \
		bash "$CONVERT" --onnx "$ONNX" \
		--input-name input_ids --input-dims "1,128" "$@"
}

# ──────────────────────────────────────────────────────────────────────────────

section "1. Static checks"
if bash -n "$CONVERT" 2>/dev/null; then ok "bash -n: syntax clean"; else no "bash -n: syntax clean"; fi

HELP="$(bash "$CONVERT" --help 2>&1)"
for flag in --quantization --weights-bitwidth --act-bitwidth --param-quantizer --act-quantizer --require-input-list --force-rebuild; do
	if [[ "$HELP" == *"$flag"* ]]; then ok "--help documents $flag"; else no "--help documents $flag"; fi
done

section "2. Validation rejects bad input"
expect_die "rejects malformed preset (w8)" "--quantization expects" \
	run_convert --quantization w8 --output-dir "$TMP/v1" --name m
expect_die "rejects non-numeric preset" "--quantization expects" \
	run_convert --quantization eight --output-dir "$TMP/v2" --name m
expect_die "rejects 4-bit weights" "--weights-bitwidth must be 8 or 16" \
	run_convert --weights-bitwidth 4 --output-dir "$TMP/v3" --name m
expect_die "rejects 32-bit activations" "--act-bitwidth must be 8 or 16" \
	run_convert --act-bitwidth 32 --output-dir "$TMP/v4" --name m
expect_die "rejects unknown quantizer" "Unknown --act-quantizer" \
	run_convert --act-quantizer bogus --output-dir "$TMP/v5" --name m
expect_die "rejects --require-input-list without a list" "--require-input-list" \
	run_convert --require-input-list --output-dir "$TMP/v6" --name m
expect_die "rejects --require-input-list with a missing list file" "not found" \
	run_convert --require-input-list --input-list "$TMP/nope.txt" --output-dir "$TMP/v7" --name m
expect_die "rejects preset mixed with explicit bit-width" "conflicts with" \
	run_convert --quantization w8a8 --act-bitwidth 8 --output-dir "$TMP/v8" --name m

section "3. Default arm stays w8a16 (back-compat)"
OUT="$TMP/default"
if run_convert --output-dir "$OUT" --name enc >/dev/null 2>&1; then
	if grep -q -- "--act_bitwidth 16" "$CONVERTER_LOG"; then ok "default passes --act_bitwidth 16"; else no "default passes --act_bitwidth 16"; fi
	if grep -q -- "--param_quantizer tf" "$CONVERTER_LOG"; then ok "default passes --param_quantizer tf"; else no "default passes --param_quantizer tf"; fi
else
	no "default build succeeds"
fi

section "4. Both A/B arms are selectable"
: >"$CONVERTER_LOG"
run_convert --quantization w8a16 --require-input-list --input-list "$CALIB" \
	--output-dir "$TMP/ab" --name enc_w8a16 >/dev/null 2>&1
if grep -q -- "--act_bitwidth 16" "$CONVERTER_LOG"; then ok "arm w8a16 → --act_bitwidth 16"; else no "arm w8a16 → --act_bitwidth 16"; fi

: >"$CONVERTER_LOG"
run_convert --quantization w8a8 --require-input-list --input-list "$CALIB" \
	--output-dir "$TMP/ab" --name enc_w8a8 >/dev/null 2>&1
if grep -q -- "--act_bitwidth 8" "$CONVERTER_LOG"; then ok "arm w8a8 → --act_bitwidth 8"; else no "arm w8a8 → --act_bitwidth 8"; fi
if grep -q -- "--weights_bitwidth 8" "$CONVERTER_LOG"; then ok "both arms keep --weights_bitwidth 8"; else no "both arms keep --weights_bitwidth 8"; fi
if grep -q -- "--input_list $CALIB" "$CONVERTER_LOG"; then ok "calibration list forwarded to converter"; else no "calibration list forwarded to converter"; fi

section "5. Arms produce different context binaries"
BIN16="$TMP/ab/enc_w8a16_ctx/enc_w8a16_v73.bin"
BIN8="$TMP/ab/enc_w8a8_ctx/enc_w8a8_v73.bin"
if [[ -f "$BIN16" && -f "$BIN8" ]]; then
	if [[ "$(sha_of "$BIN16")" != "$(sha_of "$BIN8")" ]]; then
		ok "w8a16 and w8a8 context binaries differ (flag took effect)"
	else
		no "w8a16 and w8a8 context binaries differ" "identical hash — the bit-width flag is being ignored"
	fi
else
	no "both context binaries generated"
fi

section "6. Build-stamp guard"
expect_die "refuses same --name with a different bit-width" "different settings" \
	run_convert --quantization w8a16 --input-list "$CALIB" --output-dir "$TMP/ab" --name enc_w8a8
expect_die "refuses same --name with different calibration data" "different settings" \
	run_convert --quantization w8a8 --input-list "$ONNX" --output-dir "$TMP/ab" --name enc_w8a8
expect_ok "re-running identical settings is idempotent" \
	run_convert --quantization w8a8 --input-list "$CALIB" --output-dir "$TMP/ab" --name enc_w8a8
expect_die "--force-rebuild does not weaken the guard's *other* checks" "not found" \
	run_convert --quantization w8a8 --input-list "$TMP/nope.txt" --output-dir "$TMP/ab" --name enc_force --force-rebuild
expect_ok "--force-rebuild overrides the guard" \
	run_convert --quantization w8a16 --input-list "$CALIB" --output-dir "$TMP/ab" --name enc_force --force-rebuild
if grep -q "act_bitwidth=16" "$TMP/ab/enc_force_qconv_meta.txt" 2>/dev/null; then
	ok "forced rebuild re-stamps the new bit-width"
else
	no "forced rebuild re-stamps the new bit-width"
fi

if [[ -f "$TMP/ab/enc_w8a8_qconv_meta.txt" ]]; then
	META="$(cat "$TMP/ab/enc_w8a8_qconv_meta.txt")"
	if [[ "$META" == *"act_bitwidth=8"* && "$META" == *"input_list_sha256="* && "$META" != *"input_list_sha256=-"* ]]; then
		ok "build stamp records bit-width + calibration hash"
	else
		no "build stamp records bit-width + calibration hash" "$(printf '%s' "$META" | head -c 300)"
	fi
else
	no "build stamp file written"
fi

# --- the two ways a rerun used to overwrite an arm silently -------------------
# Each uses its own output dir so no earlier build interferes.

GUARD_A="$TMP/guard_drop_calib"
run_convert --input-list "$CALIB" --output-dir "$GUARD_A" --name enc >/dev/null 2>&1
expect_die "refuses a rerun that drops --input-list" "input_list_sha256" \
	run_convert --output-dir "$GUARD_A" --name enc

GUARD_B="$TMP/guard_add_calib"
run_convert --output-dir "$GUARD_B" --name enc >/dev/null 2>&1
expect_die "refuses a rerun that adds --input-list to an uncalibrated build" "input_list_sha256" \
	run_convert --input-list "$CALIB" --output-dir "$GUARD_B" --name enc

GUARD_C="$TMP/guard_float_to_quant"
run_convert --no-quantize --output-dir "$GUARD_C" --name enc >/dev/null 2>&1
expect_die "refuses --no-quantize then quantized on one --name" "quantize" \
	run_convert --output-dir "$GUARD_C" --name enc

GUARD_D="$TMP/guard_quant_to_float"
run_convert --output-dir "$GUARD_D" --name enc >/dev/null 2>&1
expect_die "refuses quantized then --no-quantize on one --name" "quantize" \
	run_convert --no-quantize --output-dir "$GUARD_D" --name enc

if grep -qx "quantize=true" "$GUARD_D/enc_qconv_meta.txt" 2>/dev/null &&
	grep -qx "quantize=false" "$GUARD_C/enc_qconv_meta.txt" 2>/dev/null; then
	ok "build stamp records the quantize state of both kinds"
else
	no "build stamp records the quantize state of both kinds" "quantize= missing from one of the stamps"
fi

# The unconditional hash comparison must not block a legitimate repeat: a
# rebuild with byte-identical settings stays allowed in every shape.
GUARD_E="$TMP/guard_idem_nocalib"
run_convert --output-dir "$GUARD_E" --name enc >/dev/null 2>&1
expect_ok "repeat build without calibration is still idempotent" \
	run_convert --output-dir "$GUARD_E" --name enc
GUARD_F="$TMP/guard_idem_float"
run_convert --no-quantize --output-dir "$GUARD_F" --name enc >/dev/null 2>&1
expect_ok "repeat --no-quantize build is still idempotent" \
	run_convert --no-quantize --output-dir "$GUARD_F" --name enc

section "7. Float path unaffected"
: >"$CONVERTER_LOG"
run_convert --no-quantize --output-dir "$TMP/float" --name enc_float >/dev/null 2>&1
if [[ ! -s "$CONVERTER_LOG" ]] || ! grep -q -- "act_bitwidth" "$CONVERTER_LOG"; then
	ok "--no-quantize sends no quantizer flags"
else
	no "--no-quantize sends no quantizer flags" "$(tail -1 "$CONVERTER_LOG")"
fi

# ─────────────────────────────────────────���────────────────────────────────────

section "8. Skipped steps do not crash the summary"
# Regression guard: the summary block read $MODEL_SO / $CTX_BIN / $LIB_SO, which
# only exist when steps 2 and 3 ran. Under `set -u` a skipped step turned a
# finished build into exit 1 with "unbound variable" — after every artifact had
# already been written.
SKIP_OUT="$(run_convert --skip-ctx --output-dir "$TMP/skipctx" --name enc 2>&1)"
if [[ $? -eq 0 && "$SKIP_OUT" != *"unbound variable"* ]]; then
	ok "--skip-ctx exits 0 with no unbound variable"
else
	no "--skip-ctx exits 0 with no unbound variable" "$(printf '%s' "$SKIP_OUT" | tail -2 | tr '\n' ' ')"
fi
if [[ "$SKIP_OUT" == *"On-device verification: skipped"* ]]; then
	ok "--skip-ctx says the verification hint was skipped"
else
	no "--skip-ctx says the verification hint was skipped"
fi

SKIP_BOTH="$(run_convert --skip-lib --skip-ctx --output-dir "$TMP/skipboth" --name enc 2>&1)"
if [[ $? -eq 0 && "$SKIP_BOTH" != *"unbound variable"* ]]; then
	ok "--skip-lib --skip-ctx exits 0 with no unbound variable"
else
	no "--skip-lib --skip-ctx exits 0 with no unbound variable" "$(printf '%s' "$SKIP_BOTH" | tail -2 | tr '\n' ' ')"
fi

# Step 3 genuinely cannot run without the .so step 2 builds, so --skip-lib on
# its own must fail loudly with guidance, not crash.
SKIP_LIB="$(run_convert --skip-lib --output-dir "$TMP/skiplib" --name enc 2>&1)"
if [[ "$SKIP_LIB" == *"No model .so available"* && "$SKIP_LIB" != *"unbound variable"* ]]; then
	ok "--skip-lib alone fails with a clear message, not a crash"
else
	no "--skip-lib alone fails with a clear message, not a crash" "$(printf '%s' "$SKIP_LIB" | tail -2 | tr '\n' ' ')"
fi

# ─────────────────────────────────────────���────────────────────────────────────

section "9. An unusable hasher fails closed"
# Regression guard: sha256_of yields "-" both for "no file" and for "no hashing
# tool". A supplied list that cannot be hashed would be stamped exactly like an
# uncalibrated build, and the next calibration-less run would match that stamp
# and overwrite the arm. A broken sha256um on PATH stands in for the absent
# tool -- same effect on the hash, and portable enough to test.
BADHASH="$TMP/badhash-bin"
mkdir -p "$BADHASH"
printf '#!/usr/bin/env bash\nexit 1\n' >"$BADHASH/sha256sum"
chmod +x "$BADHASH/sha256sum"
BAD_OUT="$(PATH="$BADHASH:$PATH" run_convert --input-list "$CALIB" \
	--output-dir "$TMP/badhash" --name enc 2>&1)"
if [[ "$BAD_OUT" == *"Cannot hash the calibration list"* ]]; then
	ok "a supplied list that cannot be hashed is refused with a reason"
else
	no "a supplied list that cannot be hashed is refused with a reason" "$(printf '%s' "$BAD_OUT" | tail -2 | tr '\n' ' ')"
fi
if [[ "$BAD_OUT" != *"Conversion complete"* ]]; then
	ok "no artifact is produced when the calibration cannot be identified"
else
	no "no artifact is produced when the calibration cannot be identified"
fi

# ──────────────────────────────────────────────────────────────────────────────

printf '\n\033[1mResult:\033[0m %d passed, %d failed\n' "$PASS" "$FAIL"
[[ $FAIL -eq 0 ]] || exit 1
