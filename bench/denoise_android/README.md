# Denoising Evaluation Pipeline — Complete Guide

## Overview
This directory contains everything needed to run the **Denoising Gate Evaluation (ADR-018)** on Meizu 21 Note (SD8 Gen 2 / Android 16 / HTP v73) via ADB.

## Files & Their Roles

| File | Purpose |
|------|---------|
| `README.md` | Setup instructions and workflow |
| `run_denoising.sh` | ADB pipeline script |
| `eval_denoising.py` | Core evaluation logic (host-side) |
| `eval_manifest_v1.json` | Test data manifest |
| `denoising_results.json` | Generated output with WER/RTF per denoiser |

## Pipeline: 3 Options

### Option A: GTCRN (sherpa-onnx OfflineDenoise)
- **Model**: GTCRN TFLite (sherpa-onnx)
- **Implementation**: JNI native via sherpa-onnx `OfflineDenoise`
- **Pros**: Fastest on-device, native TFLite, low latency
- **Cons**: Heavier binary, requires JNI bindings

### Option B: Wiener (noisereduce)
- **Model**: Wiener filter (Python `noisereduce`, `prop_decrease=0.5`)
- **Implementation**: Ported to Android via JNI or Termux Python
- **Pros**: Lightweight, pure Python, easy to implement
- **Cons**: Slower than GTCRN, requires porting

### Option C: VAD-only (no denoiser)
- **Model**: None (raw audio)
- **Implementation**: Skip denoising, go directly to ASR
- **Pros**: Fastest, no model overhead
- **Cons**: Noisy WER may be worse

## Quick Start

```bash
# 1. Connect Meizu via USB, enable USB debugging
adb devices

# 2. Push manifest to device
adb push eval_manifest_v1.json /sdcard/

# 3. Run evaluation
./run_denoising.sh

# 4. Pull results
adb pull /sdcard/denoising_results ./denoising_results
cat denoising_results.json
```

## Expected Output Format
```json
{
  "gate_decision": "ADOPT denoiser: gtcrn (noisy WER 0.14 vs raw 0.18)",
  "adopt_denoiser": "gtcrn",
  "raw_noisy_wer": 0.18,
  "wiener_noisy_wer": 0.15,
  "gtcrn_noisy_wer": 0.14,
  "rtf_raw": 0.85,
  "rtf_wiener": 1.32,
  "rtf_gtcrn": 0.72,
  "per_condition": { ... }
}
```

## Decision Criteria (ADR-018 Gate Logic)
- **ADOPT GTCRN**: if GTCRN_WER < raw_WER AND GTCRN_RTF < 2.0s
- **ADOPT Wiener**: if Wiener_WER < raw_WER AND Wiener_RTF < 2.0s
- **REJECT denoising**: if raw_WER ≤ all denoiser_WER → VAD-only pipeline