#!/bin/bash
# Denoising evaluation pipeline for Issue #111 (ADR-018)
# Run via ADB on Meizu 21 Note (SD8 Gen 2 / Android 16 / HTP v73)

echo "=== Denoising Gate Evaluation (ADR-018) ==="
echo "Device: Meizu 21 Note (SD8 Gen 2)"
echo "Pipeline: GTCRN vs Wiener vs VAD-only"
echo ""
echo "=== Step 1: Verify ADB connection ==="
adb devices

echo ""
echo "=== Step 2: Push manifest and script to device ==="
adb push eval_manifest_v1.json /sdcard/

# Note: The actual evaluation requires the APK with GTCRN and Zipformer ASR
# The script can be run through instrumented test or Termux

echo ""
echo "=== Step 3: Launch evaluation ==="
echo "Option A: Use instrumented test (recommended)"
echo "  adb shell am instrument -w -e manifest /sdcard/eval_manifest_v1.json ..."
echo ""
echo "Option B: Use Termux Python (simpler, no build)"
echo "  pip install numpy soundfile jiwer noisereduce"
echo "  python eval_denoising.py --manifest /sdcard/eval_manifest_v1.json"

echo ""
echo "=== Step 4: Pull results ==="
echo "  adb pull /sdcard/denoising_results ./"
echo ""
echo "=== Expected output ==="
echo "  - WER (raw, wiener, gtcrn) per SNR condition"
echo "  - RTF measurements"
echo "  - Gate decision: ADOPT / REJECT / VAD-only"

echo ""
echo "=== Issue #111 Decision Criteria ==="
echo "  If GTCRN WER < raw WER and RTF < budget → Adopt GTCRN"
echo "  If Wiener WER < raw WER and RTF < budget → Adopt Wiener"
echo "  If both ≥ raw WER → Reject denoising (VAD-only pipeline)"
